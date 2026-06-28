"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "meetings",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("meeting_type", sa.String(length=48), nullable=False, server_default="progress_meeting"),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("attendees", sa.JSON(), nullable=False),
        sa.Column("raw_transcript", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("route_suggestion", sa.String(length=48), nullable=True),
        sa.Column("route_confidence", sa.String(length=16), nullable=True),
        sa.Column("route_reason", sa.Text(), nullable=True),
        sa.Column("final_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.String(length=64), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("segment_id", sa.String(length=96), nullable=False, unique=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("extractor_output", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "work_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.String(length=64), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("assignee", sa.Text(), nullable=True),
        sa.Column("assignee_confidence", sa.String(length=16), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("deadline", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "meeting_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.String(length=64), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "error_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.String(length=64), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meeting_id", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("error_logs")
    op.drop_table("workflow_runs")
    op.drop_table("meeting_embeddings")
    op.drop_table("work_items")
    op.drop_table("segments")
    op.drop_table("meetings")
