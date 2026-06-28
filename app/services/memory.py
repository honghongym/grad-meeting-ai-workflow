from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Meeting, MeetingEmbedding, WorkItem


def get_previous_work_items(db: Session, meeting_id: str) -> list[dict]:
    current = db.get(Meeting, meeting_id)
    if current is None:
        return []
    previous = db.scalars(
        select(Meeting)
        .where(Meeting.meeting_date < current.meeting_date, Meeting.status == "confirmed")
        .order_by(Meeting.meeting_date.desc())
        .limit(1)
    ).first()
    if previous is None:
        return []
    items = db.scalars(select(WorkItem).where(WorkItem.meeting_id == previous.id)).all()
    return [
        {
            "task_name": item.task_name,
            "assignee": item.assignee,
            "status": item.status,
            "expected_output": item.expected_output,
            "deadline": item.deadline,
        }
        for item in items
    ]


def should_use_vector_memory(db: Session) -> bool:
    confirmed_count = db.scalar(select(func.count()).select_from(Meeting).where(Meeting.status == "confirmed"))
    return (confirmed_count or 0) >= 3


def get_relevant_history(db: Session, query_embedding: list[float] | None, limit: int = 3) -> list[dict]:
    if query_embedding is None or not should_use_vector_memory(db):
        return []
    # pgvector distance ordering is available when running on PostgreSQL with the pgvector package.
    try:
        rows = db.scalars(
            select(MeetingEmbedding)
            .order_by(MeetingEmbedding.embedding.cosine_distance(query_embedding))  # type: ignore[attr-defined]
            .limit(limit)
        ).all()
    except Exception:
        return []
    return [row.source_payload for row in rows]

