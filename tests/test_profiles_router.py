import asyncio
from datetime import date

from app.models import Meeting
from app.schemas import RouteValidationResult
from app.services.llm import FakeLLMClient
from app.services.planner import build_user_prompt
from app.services.profiles import get_profile, profile_options
from app.services.router import validate_route
from app.schemas import ValidatedBundle


def test_all_meeting_profiles_are_available() -> None:
    types = {profile.meeting_type for profile in profile_options()}

    assert {
        "progress_meeting",
        "paper_reading",
        "experiment_review",
        "defense_rehearsal",
    }.issubset(types)


def test_planner_prompt_includes_profile_instruction() -> None:
    profile = get_profile("paper_reading")

    prompt = build_user_prompt(ValidatedBundle(), [], [], profile)

    assert "论文精读" in prompt
    assert "paper_core_claims" in prompt


def test_router_result_shape_with_fake_llm() -> None:
    meeting = Meeting(
        id="mtg-test",
        meeting_date=date(2026, 6, 28),
        meeting_type="paper_reading",
        topic="论文精读",
        attendees=["老杨"],
        raw_transcript="[00:00:01] [老杨]: 这篇论文的方法是 cross-attention。",
    )

    result = asyncio.run(validate_route(FakeLLMClient(), meeting))

    assert isinstance(result, RouteValidationResult)
