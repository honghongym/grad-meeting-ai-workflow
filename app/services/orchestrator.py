import asyncio
import logging
import time

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Meeting, Segment
from app.schemas import ExtractorResult, SegmentInput
from app.services.chunker import append_context, chunk_transcript
from app.services.embeddings import embed_text
from app.services.extractor import extract_segment
from app.services.llm import LLMClient, build_llm_client
from app.services.memory import get_previous_work_items, get_relevant_history, should_use_vector_memory
from app.services.persistence import log_error, log_workflow_stage, save_draft
from app.services.planner import plan_meeting
from app.services.profiles import get_profile
from app.services.router import validate_route
from app.services.validator import validate_segments

logger = logging.getLogger(__name__)


def stage_log(
    db: Session,
    meeting_id: str,
    stage: str,
    started_at: float,
    detail: dict | None = None,
    status: str = "ok",
) -> None:
    log_workflow_stage(
        db,
        meeting_id,
        stage,
        status=status,
        detail=detail,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
    )


async def _extract_with_open_handling(
    llm: LLMClient,
    segment: SegmentInput,
    next_segment: SegmentInput | None,
    profile=None,
) -> ExtractorResult:
    result = await extract_segment(llm, segment, profile)
    if result.status != "open" or next_segment is None or settings.max_append_depth < 1:
        return result

    appended = SegmentInput(
        segment_id=segment.segment_id,
        position=segment.position,
        text=append_context(segment.text, next_segment.text),
        token_estimate=segment.token_estimate + min(next_segment.token_estimate, 250),
    )
    retry = await extract_segment(llm, appended, profile)
    if retry.status == "open":
        retry.status = "closed_with_warning"
        retry.warning = "语义跨片段延续，已达到最大追加深度，请人工复核。"
    return retry


async def run(meeting_id: str, db: Session, llm: LLMClient | None = None) -> None:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise ValueError("meeting not found")

    llm = llm or build_llm_client()
    logger.info("[%s] workflow started", meeting_id)
    workflow_started = time.perf_counter()
    meeting.status = "chunking"
    meeting.final_summary = None
    db.execute(delete(Segment).where(Segment.meeting_id == meeting_id))
    db.commit()

    segments = chunk_transcript(meeting_id, meeting.raw_transcript)
    logger.info("[%s] chunked transcript into %s segment(s)", meeting_id, len(segments))
    stage_log(
        db,
        meeting_id,
        "chunking",
        workflow_started,
        {"segments": len(segments), "transcript_chars": len(meeting.raw_transcript)},
    )
    for segment in segments:
        db.add(
            Segment(
                meeting_id=meeting_id,
                segment_id=segment.segment_id,
                position=segment.position,
                text=segment.text,
                token_estimate=segment.token_estimate,
                status="pending",
            )
        )
    db.commit()

    routing_started = time.perf_counter()
    meeting.status = "routing"
    db.commit()
    route_result = await validate_route(llm, meeting)
    meeting.route_suggestion = route_result.suggested_type
    meeting.route_confidence = route_result.confidence
    meeting.route_reason = route_result.reason
    db.commit()
    stage_log(
        db,
        meeting_id,
        "routing",
        routing_started,
        {
            "selected_type": meeting.meeting_type,
            "suggested_type": route_result.suggested_type,
            "confidence": route_result.confidence,
            "reasonable": route_result.is_user_choice_reasonable,
        },
    )
    logger.info(
        "[%s] route validated: selected=%s suggested=%s confidence=%s",
        meeting_id,
        meeting.meeting_type,
        route_result.suggested_type,
        route_result.confidence,
    )

    profile = get_profile(meeting.meeting_type)
    meeting.status = "extracting"
    db.commit()
    semaphore = asyncio.Semaphore(settings.extractor_concurrency)

    async def guarded_extract(index: int, segment: SegmentInput) -> tuple[str, ExtractorResult]:
        async with semaphore:
            next_segment = segments[index + 1] if index + 1 < len(segments) else None
            logger.info("[%s] extractor started: %s", meeting_id, segment.segment_id)
            result = await _extract_with_open_handling(llm, segment, next_segment, profile)
            logger.info(
                "[%s] extractor finished: %s status=%s tasks=%s",
                meeting_id,
                segment.segment_id,
                result.status,
                len(result.mentioned_tasks),
            )
            return segment.segment_id, result

    try:
        extract_started = time.perf_counter()
        tasks = [guarded_extract(index, segment) for index, segment in enumerate(segments)]
        results: list[ExtractorResult] = []
        for completed in asyncio.as_completed(tasks):
            segment_id, result = await completed
            results.append(result)
            row = db.scalar(select(Segment).where(Segment.segment_id == segment_id))
            if row:
                row.status = result.status
                row.extractor_output = result.model_dump()
                row.error_message = result.warning
            db.commit()
            logger.info("[%s] extraction progress: %s/%s", meeting_id, len(results), len(segments))
        stage_log(
            db,
            meeting_id,
            "extracting",
            extract_started,
            {
                "segments": len(results),
                "tasks": sum(len(result.mentioned_tasks) for result in results),
                "model": settings.extractor_model,
            },
        )

        validate_started = time.perf_counter()
        meeting.status = "validating"
        db.commit()
        bundle = validate_segments(results)
        logger.info(
            "[%s] validation finished: summaries=%s tasks=%s warnings=%s",
            meeting_id,
            len(bundle.content_summaries),
            len(bundle.tasks),
            len(bundle.warnings),
        )
        stage_log(
            db,
            meeting_id,
            "validating",
            validate_started,
            {
                "summaries": len(bundle.content_summaries),
                "tasks": len(bundle.tasks),
                "warnings": len(bundle.warnings),
            },
        )

        memory_started = time.perf_counter()
        meeting.status = "retrieving_memory"
        db.commit()
        previous_work = get_previous_work_items(db, meeting_id)
        query_embedding = None
        if should_use_vector_memory(db):
            logger.info("[%s] vector memory enabled, embedding current summary", meeting_id)
            query_embedding = await embed_text("\n".join(bundle.content_summaries))
        history = get_relevant_history(db, query_embedding)
        logger.info(
            "[%s] memory loaded: previous_work=%s history=%s",
            meeting_id,
            len(previous_work),
            len(history),
        )
        stage_log(
            db,
            meeting_id,
            "retrieving_memory",
            memory_started,
            {"previous_work": len(previous_work), "history": len(history)},
        )

        planner_started = time.perf_counter()
        meeting.status = "planning"
        db.commit()
        logger.info("[%s] planner started", meeting_id)
        planner_result = await plan_meeting(llm, bundle, previous_work, history, profile)
        logger.info(
            "[%s] planner finished: work_plan=%s review_notes=%s",
            meeting_id,
            len(planner_result.work_plan),
            len(planner_result.review_notes),
        )
        stage_log(
            db,
            meeting_id,
            "planning",
            planner_started,
            {
                "work_plan": len(planner_result.work_plan),
                "review_notes": len(planner_result.review_notes),
                "model": settings.planner_model,
            },
        )
        save_draft(db, meeting, planner_result, bundle.warnings)
        logger.info("[%s] draft ready", meeting_id)
        stage_log(db, meeting_id, "workflow", workflow_started, {"status": "draft_ready"})
    except Exception as exc:
        meeting.status = "needs_review"
        db.commit()
        log_error(db, meeting_id, "orchestrator", str(exc))
        stage_log(db, meeting_id, "workflow", workflow_started, {"error": str(exc)}, status="failed")
        logger.exception("[%s] workflow failed", meeting_id)
        raise
