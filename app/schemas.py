from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


MeetingType = Literal["progress_meeting", "paper_reading", "experiment_review", "defense_rehearsal"]


class MeetingCreate(BaseModel):
    meeting_date: date
    meeting_type: MeetingType = "progress_meeting"
    topic: str = Field(min_length=1)
    attendees: list[str] = Field(default_factory=list)
    transcript: str = Field(min_length=1)


class MeetingCreated(BaseModel):
    meeting_id: str
    status: str


class MeetingCreateJson(BaseModel):
    meeting_date: date
    meeting_type: MeetingType = "progress_meeting"
    topic: str = Field(min_length=1)
    attendees: list[str] = Field(default_factory=list)
    transcript: str = Field(min_length=1)


class MeetingConfirmJson(BaseModel):
    final_summary: dict | None = None


class SegmentInput(BaseModel):
    segment_id: str
    position: int
    text: str
    token_estimate: int


class ExtractedTask(BaseModel):
    task_name: str
    assignee: str | None = None
    assignee_confidence: Literal["high", "low"] = "high"
    expected_output: str | None = None
    due_hint: str | None = None
    evidence: str | None = None


class ExtractorResult(BaseModel):
    segment_id: str
    status: Literal["open", "closed", "closed_with_warning"]
    content_summary: str
    speaker_switch_count: int = 0
    mentioned_tasks: list[ExtractedTask] = Field(default_factory=list)
    warning: str | None = None


class ValidatedBundle(BaseModel):
    content_summaries: list[str] = Field(default_factory=list)
    tasks: list[ExtractedTask] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TrackingItem(BaseModel):
    previous_task: str
    owner: str | None = None
    status: Literal["completed", "blocked", "delayed", "cancelled", "unknown"]
    evidence: str | None = None


class PlannedWorkItem(BaseModel):
    task_name: str
    assignee: str | None = None
    assignee_confidence: Literal["high", "low"] = "high"
    expected_output: str | None = None
    deadline: str | None = None
    evidence: str | None = None


class PlannerSummary(BaseModel):
    paper_discussion: list[str] = Field(default_factory=list)
    experiment_progress: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class PlannerResult(BaseModel):
    summary: PlannerSummary
    tracking_table: list[TrackingItem] = Field(default_factory=list)
    work_plan: list[PlannedWorkItem] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
    type_specific: dict = Field(default_factory=dict)


class RouteValidationResult(BaseModel):
    suggested_type: MeetingType
    confidence: Literal["high", "medium", "low"] = "medium"
    is_user_choice_reasonable: bool = True
    reason: str


class MeetingDetail(BaseModel):
    id: str
    meeting_date: date
    meeting_type: str = "progress_meeting"
    topic: str
    attendees: list[str]
    status: str
    final_summary: dict | None = None
