from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import ErrorLog, Meeting, WorkItem, WorkflowRun
from app.schemas import PlannerResult
from app.services.embeddings import reindex_meeting


def log_error(
    db: Session,
    meeting_id: str | None,
    stage: str,
    error_message: str,
    payload: dict | None = None,
) -> None:
    db.add(
        ErrorLog(
            meeting_id=meeting_id,
            stage=stage,
            error_message=error_message,
            payload=payload,
        )
    )
    db.commit()


def log_workflow_stage(
    db: Session,
    meeting_id: str,
    stage: str,
    status: str = "ok",
    detail: dict | None = None,
    duration_ms: int | None = None,
) -> None:
    db.add(
        WorkflowRun(
            meeting_id=meeting_id,
            stage=stage,
            status=status,
            detail=detail,
            duration_ms=duration_ms,
        )
    )
    db.commit()


def save_draft(db: Session, meeting: Meeting, result: PlannerResult, warnings: list[str]) -> None:
    payload = result.model_dump()
    payload["warnings"] = warnings
    meeting.final_summary = payload
    meeting.status = "draft_ready"
    db.commit()


async def confirm_meeting(db: Session, meeting_id: str, final_summary: dict | None = None) -> None:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise ValueError("meeting not found")
    if final_summary is not None:
        meeting.final_summary = final_summary
    if not meeting.final_summary:
        raise ValueError("meeting has no draft to confirm")

    parsed = PlannerResult.model_validate(meeting.final_summary)
    raw_work_plan = meeting.final_summary.get("work_plan", [])
    meeting.final_summary = parsed.model_dump()
    for index, raw_item in enumerate(raw_work_plan):
        if index < len(meeting.final_summary["work_plan"]) and isinstance(raw_item, dict):
            meeting.final_summary["work_plan"][index]["status"] = raw_item.get("status", "planned")
    db.execute(delete(WorkItem).where(WorkItem.meeting_id == meeting_id))
    for index, item in enumerate(parsed.work_plan):
        raw_status = "planned"
        if index < len(raw_work_plan) and isinstance(raw_work_plan[index], dict):
            raw_status = raw_work_plan[index].get("status") or "planned"
        db.add(
            WorkItem(
                meeting_id=meeting_id,
                task_name=item.task_name,
                assignee=item.assignee,
                assignee_confidence=item.assignee_confidence,
                expected_output=item.expected_output,
                deadline=item.deadline,
                status=raw_status,
                evidence=item.evidence,
            )
        )
    meeting.status = "confirmed"
    db.commit()

    try:
        await reindex_meeting(db, meeting_id)
    except Exception as exc:
        log_error(
            db,
            meeting_id,
            "reindex",
            str(exc),
            {"final_summary": meeting.final_summary},
        )
