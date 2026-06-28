from openai import AsyncOpenAI
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Meeting, MeetingEmbedding


async def embed_text(text: str) -> list[float]:
    if settings.use_fake_llm or not settings.openai_api_key:
        return [0.0] * settings.embedding_dimension
    client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    try:
        result = await client.embeddings.create(
            model=settings.embedding_model,
            input=text,
            dimensions=settings.embedding_dimension,
        )
    except TypeError:
        result = await client.embeddings.create(model=settings.embedding_model, input=text)
    return normalize_embedding(result.data[0].embedding)


def normalize_embedding(embedding: list[float]) -> list[float]:
    if len(embedding) == settings.embedding_dimension:
        return embedding
    if len(embedding) > settings.embedding_dimension:
        return embedding[: settings.embedding_dimension]
    return embedding + [0.0] * (settings.embedding_dimension - len(embedding))


def build_summary_text(final_summary: dict) -> str:
    parts: list[str] = []
    for value in final_summary.values():
        if isinstance(value, dict):
            parts.append(str(value))
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return "\n".join(parts)[:4000]


async def reindex_meeting(db: Session, meeting_id: str) -> None:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None or not meeting.final_summary:
        raise ValueError("meeting has no final summary to index")
    summary_text = build_summary_text(meeting.final_summary)
    embedding = await embed_text(summary_text)
    db.execute(delete(MeetingEmbedding).where(MeetingEmbedding.meeting_id == meeting_id))
    db.add(
        MeetingEmbedding(
            meeting_id=meeting_id,
            summary_text=summary_text,
            source_payload=meeting.final_summary,
            embedding=embedding,
        )
    )
    db.commit()


async def query_embedding_for_meeting(db: Session, meeting_id: str) -> list[float] | None:
    meeting = db.get(Meeting, meeting_id)
    if meeting is None or not meeting.final_summary:
        return None
    return await embed_text(build_summary_text(meeting.final_summary))


def has_embedding(db: Session, meeting_id: str) -> bool:
    return db.scalar(select(MeetingEmbedding.id).where(MeetingEmbedding.meeting_id == meeting_id)) is not None
