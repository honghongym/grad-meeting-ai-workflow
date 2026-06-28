import pytest
import asyncio

from app.schemas import ExtractorResult, PlannerResult, PlannerSummary
from app.services.llm import LLMClient
from app.services.orchestrator import _extract_with_open_handling


class OpenTwiceLLM(LLMClient):
    def __init__(self) -> None:
        self.calls = 0

    async def structured_response(self, model, system_prompt, user_prompt, schema):
        self.calls += 1
        if schema is ExtractorResult:
            return ExtractorResult(
                segment_id="mtg-seg-001",
                status="open",
                content_summary="未闭合",
                speaker_switch_count=0,
                mentioned_tasks=[],
            )
        return PlannerResult(summary=PlannerSummary())


def test_open_segment_retries_once_then_warns() -> None:
    from app.schemas import SegmentInput

    async def scenario() -> None:
        llm = OpenTwiceLLM()
        segment = SegmentInput(segment_id="mtg-seg-001", position=1, text="A", token_estimate=1)
        next_segment = SegmentInput(segment_id="mtg-seg-002", position=2, text="B", token_estimate=1)

        result = await _extract_with_open_handling(llm, segment, next_segment)

        assert llm.calls == 2
        assert result.status == "closed_with_warning"

    asyncio.run(scenario())
