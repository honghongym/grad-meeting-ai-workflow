import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import date
from collections.abc import AsyncIterator

from fastapi import BackgroundTasks, Depends, Form, Header, HTTPException, Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, init_db
from app.models import ErrorLog, Meeting, Segment, WorkflowRun
from app.schemas import MeetingConfirmJson, MeetingCreateJson, MeetingCreated, MeetingDetail
from app.services import orchestrator
from app.services.embeddings import reindex_meeting
from app.services.persistence import confirm_meeting
from app.services.profiles import get_profile, profile_options


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=True,
    )
    init_db()
    yield


app = FastAPI(title="研究生组会 AI 协同引擎", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allow_origins.split(",") if origin.strip()],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="app/templates")


def make_meeting_id(meeting_date: date) -> str:
    return f"mtg-{meeting_date.strftime('%Y%m%d')}"


def run_background(meeting_id: str) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        logging.getLogger(__name__).info("[%s] background task submitted", meeting_id)
        asyncio.run(orchestrator.run(meeting_id, db))
    finally:
        db.close()


def verify_api_token(x_api_token: str | None = Header(default=None)) -> None:
    if settings.api_token and x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="invalid API token")


def create_meeting_record(
    db: Session,
    meeting_date: date,
    meeting_type: str,
    topic: str,
    attendees: list[str],
    transcript: str,
) -> Meeting:
    base_id = make_meeting_id(meeting_date)
    meeting_id = base_id
    suffix = 2
    while db.get(Meeting, meeting_id) is not None:
        meeting_id = f"{base_id}-{suffix}"
        suffix += 1

    meeting = Meeting(
        id=meeting_id,
        meeting_date=meeting_date,
        meeting_type=meeting_type,
        topic=topic,
        attendees=attendees,
        raw_transcript=transcript,
        status="pending",
    )
    db.add(meeting)
    db.commit()
    return meeting


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse(url="/meetings", status_code=303)


@app.get("/meetings", response_class=HTMLResponse)
def meetings_index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    meetings = db.scalars(select(Meeting).order_by(Meeting.meeting_date.desc(), Meeting.created_at.desc())).all()
    memory_state = build_memory_state(db)
    status_counts = {
        status: sum(1 for meeting in meetings if meeting.status == status)
        for status in ["pending", "draft_ready", "confirmed", "needs_review"]
    }
    return templates.TemplateResponse(
        "meetings_index.html",
        {
            "request": request,
            "meetings": meetings,
            "memory_state": memory_state,
            "status_counts": status_counts,
            "get_profile": get_profile,
        },
    )


@app.get("/meetings/new", response_class=HTMLResponse)
def new_meeting(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "meetings_new.html",
        {"request": request, "profiles": profile_options()},
    )


@app.post("/meetings", response_model=MeetingCreated)
def create_meeting(
    background_tasks: BackgroundTasks,
    meeting_date: date = Form(...),
    meeting_type: str = Form("progress_meeting"),
    topic: str = Form(...),
    attendees: str = Form(""),
    transcript: str = Form(...),
    db: Session = Depends(get_db),
):
    attendee_list = [item.strip() for item in attendees.replace("，", ",").split(",") if item.strip()]
    meeting = create_meeting_record(db, meeting_date, meeting_type, topic, attendee_list, transcript)
    background_tasks.add_task(run_background, meeting.id)

    return MeetingCreated(meeting_id=meeting.id, status="pending")


@app.post("/meetings/form", include_in_schema=False)
def create_meeting_form(
    background_tasks: BackgroundTasks,
    meeting_date: date = Form(...),
    meeting_type: str = Form("progress_meeting"),
    topic: str = Form(...),
    attendees: str = Form(""),
    transcript: str = Form(...),
    db: Session = Depends(get_db),
):
    result = create_meeting(background_tasks, meeting_date, meeting_type, topic, attendees, transcript, db)
    return RedirectResponse(url=f"/meetings/{result.meeting_id}", status_code=303)


@app.get("/meetings/{meeting_id}", response_class=HTMLResponse)
def meeting_detail(request: Request, meeting_id: str, db: Session = Depends(get_db)) -> HTMLResponse:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    errors = db.scalars(
        select(ErrorLog).where(ErrorLog.meeting_id == meeting_id).order_by(ErrorLog.created_at.desc())
    ).all()
    summary_json = json.dumps(meeting.final_summary or {}, ensure_ascii=False, indent=2)
    progress = build_progress(db, meeting)
    workflow_runs = db.scalars(
        select(WorkflowRun).where(WorkflowRun.meeting_id == meeting_id).order_by(WorkflowRun.created_at.desc())
    ).all()
    memory_state = build_memory_state(db)
    return templates.TemplateResponse(
        "meetings_detail.html",
        {
            "request": request,
            "meeting": meeting,
            "errors": errors,
            "summary_json": summary_json,
            "summary": meeting.final_summary or {},
            "progress": progress,
            "workflow_runs": workflow_runs,
            "memory_state": memory_state,
            "profile": get_profile(meeting.meeting_type),
            "get_profile": get_profile,
            "task_status_options": ["planned", "completed", "blocked", "delayed", "cancelled", "transferred"],
            "tracking_status_options": ["completed", "blocked", "delayed", "cancelled", "unknown"],
        },
    )


@app.post("/meetings/{meeting_id}/confirm")
async def confirm(
    meeting_id: str,
    final_summary: str | None = Form(None),
    edited_payload: str | None = Form(None),
    db: Session = Depends(get_db),
):
    payload = None
    source = edited_payload or final_summary
    if source:
        try:
            payload = json.loads(source)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc
    try:
        await confirm_meeting(db, meeting_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/meetings/{meeting_id}", status_code=303)


@app.post("/meetings/{meeting_id}/rerun")
def rerun(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if db.get(Meeting, meeting_id) is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    background_tasks.add_task(run_background, meeting_id)
    return RedirectResponse(url=f"/meetings/{meeting_id}", status_code=303)


@app.post("/meetings/{meeting_id}/reindex")
async def reindex(meeting_id: str, db: Session = Depends(get_db)):
    try:
        await reindex_meeting(db, meeting_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/meetings/{meeting_id}", status_code=303)


def build_progress(db: Session, meeting: Meeting) -> dict:
    total_segments = db.scalar(
        select(func.count()).select_from(Segment).where(Segment.meeting_id == meeting.id)
    ) or 0
    done_segments = db.scalar(
        select(func.count())
        .select_from(Segment)
        .where(
            Segment.meeting_id == meeting.id,
            Segment.status.in_(["closed", "open", "closed_with_warning"]),
        )
    ) or 0
    status_rank = {
        "pending": 5,
        "chunking": 12,
        "routing": 16,
        "extracting": 20,
        "validating": 62,
        "retrieving_memory": 72,
        "planning": 82,
        "draft_ready": 100,
        "confirmed": 100,
        "needs_review": 100,
    }
    percent = status_rank.get(meeting.status, 0)
    if meeting.status == "extracting" and total_segments:
        percent = 20 + int(40 * done_segments / total_segments)
    labels = {
        "pending": "等待处理",
        "chunking": "正在切分转写文本",
        "routing": "正在校验会议类型",
        "extracting": f"正在提取片段任务 {done_segments}/{total_segments}",
        "validating": "正在进行确定性校验",
        "retrieving_memory": "正在检索历史任务",
        "planning": "正在生成纪要和 Work Plan",
        "draft_ready": "草稿已生成，等待人工确认",
        "confirmed": "已确认发布",
        "needs_review": "处理失败或需要人工复核",
    }
    return {
        "status": meeting.status,
        "label": labels.get(meeting.status, meeting.status),
        "percent": percent,
        "total_segments": total_segments,
        "done_segments": done_segments,
        "is_running": meeting.status
        in {"pending", "chunking", "routing", "extracting", "validating", "retrieving_memory", "planning"},
    }


def build_memory_state(db: Session) -> dict:
    confirmed_count = db.scalar(
        select(func.count()).select_from(Meeting).where(Meeting.status == "confirmed")
    ) or 0
    if confirmed_count == 0:
        phase = "第 1 次会议：无历史任务"
        vector_enabled = False
    elif confirmed_count < 3:
        phase = f"冷启动阶段：已有 {confirmed_count} 次确认会议，仅使用上周任务"
        vector_enabled = False
    else:
        phase = f"稳定记忆阶段：已有 {confirmed_count} 次确认会议，启用历史 Top-3 检索"
        vector_enabled = True
    return {
        "confirmed_count": confirmed_count,
        "phase": phase,
        "vector_enabled": vector_enabled,
    }


@app.get("/api/meetings/{meeting_id}/progress")
def api_meeting_progress(meeting_id: str, db: Session = Depends(get_db)) -> dict:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return build_progress(db, meeting)


@app.post("/api/meetings", response_model=MeetingCreated, dependencies=[Depends(verify_api_token)])
def api_create_meeting(
    payload: MeetingCreateJson,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> MeetingCreated:
    meeting = create_meeting_record(
        db,
        payload.meeting_date,
        payload.meeting_type,
        payload.topic,
        payload.attendees,
        payload.transcript,
    )
    background_tasks.add_task(run_background, meeting.id)
    return MeetingCreated(meeting_id=meeting.id, status=meeting.status)


@app.get("/api/meetings", dependencies=[Depends(verify_api_token)])
def api_list_meetings(db: Session = Depends(get_db)) -> dict:
    meetings = db.scalars(select(Meeting).order_by(Meeting.meeting_date.desc(), Meeting.created_at.desc())).all()
    return {
        "meetings": [
            {
                "id": meeting.id,
                "meeting_date": meeting.meeting_date.isoformat(),
                "meeting_type": meeting.meeting_type,
                "meeting_type_label": get_profile(meeting.meeting_type).display_name,
                "topic": meeting.topic,
                "attendees": meeting.attendees,
                "status": meeting.status,
            }
            for meeting in meetings
        ]
    }


@app.post("/api/meetings/{meeting_id}/confirm", dependencies=[Depends(verify_api_token)])
async def api_confirm_meeting(
    meeting_id: str,
    payload: MeetingConfirmJson | None = None,
    db: Session = Depends(get_db),
) -> dict:
    try:
        await confirm_meeting(db, meeting_id, payload.final_summary if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"meeting_id": meeting_id, "status": "confirmed"}


@app.get("/api/meetings/{meeting_id}/result", dependencies=[Depends(verify_api_token)])
def api_meeting_result(meeting_id: str, db: Session = Depends(get_db)) -> dict:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return {
        "id": meeting.id,
        "meeting_date": meeting.meeting_date.isoformat(),
        "meeting_type": meeting.meeting_type,
        "meeting_type_label": get_profile(meeting.meeting_type).display_name,
        "topic": meeting.topic,
        "attendees": meeting.attendees,
        "status": meeting.status,
        "progress": build_progress(db, meeting),
        "route": {
            "suggestion": meeting.route_suggestion,
            "confidence": meeting.route_confidence,
            "reason": meeting.route_reason,
        },
        "final_summary": meeting.final_summary,
        "detail_url": f"/meetings/{meeting.id}",
    }


def render_markdown(meeting: Meeting) -> str:
    summary = meeting.final_summary or {}
    profile = get_profile(meeting.meeting_type)
    lines = [
        f"# {meeting.topic}",
        "",
        f"- 日期：{meeting.meeting_date.isoformat()}",
        f"- 类型：{profile.display_name}",
        f"- 参会人：{', '.join(meeting.attendees)}",
        "",
    ]
    summary_block = summary.get("summary", {})
    for title, key in [
        ("论文/主题讨论", "paper_discussion"),
        ("实验进展", "experiment_progress"),
        ("关键决策", "decisions"),
        ("风险", "risks"),
    ]:
        items = summary_block.get(key) or []
        lines.extend([f"## {title}", ""])
        lines.extend([f"- {item}" for item in items] or ["- 暂无"])
        lines.append("")
    if summary.get("type_specific"):
        lines.extend([f"## {profile.display_name}专属结果", ""])
        for key, label in profile.type_specific_fields.items():
            value = summary["type_specific"].get(key)
            lines.append(f"### {label}")
            if isinstance(value, list):
                lines.extend([f"- {item}" for item in value] or ["- 暂无"])
            elif value:
                lines.append(str(value))
            else:
                lines.append("- 暂无")
            lines.append("")
    lines.extend(["## Work Plan", ""])
    for item in summary.get("work_plan") or []:
        lines.append(f"- **{item.get('task_name')}**")
        lines.append(f"  - 负责人：{item.get('assignee') or '待确认'}")
        lines.append(f"  - 产出：{item.get('expected_output') or '暂无'}")
        lines.append(f"  - 截止：{item.get('deadline') or '待定'}")
    return "\n".join(lines).strip() + "\n"


@app.get("/api/meetings/{meeting_id}/markdown", response_class=PlainTextResponse, dependencies=[Depends(verify_api_token)])
def api_meeting_markdown(meeting_id: str, db: Session = Depends(get_db)) -> str:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return render_markdown(meeting)


@app.get("/api/meetings/{meeting_id}", response_model=MeetingDetail)
def api_meeting_detail(meeting_id: str, db: Session = Depends(get_db)) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting
