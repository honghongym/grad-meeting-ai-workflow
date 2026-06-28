from pydantic import ValidationError

from app.config import settings
from app.models import Meeting
from app.schemas import RouteValidationResult
from app.services.llm import LLMClient
from app.services.profiles import PROFILES, get_profile

SYSTEM_PROMPT = """你是会议类型路由校验器。
你只判断用户选择的会议类型是否合理，并给出建议类型、置信度和简短理由。
不要覆盖用户选择；只输出 JSON。
"""


def build_route_prompt(meeting: Meeting) -> str:
    choices = {key: profile.display_name for key, profile in PROFILES.items()}
    profile = get_profile(meeting.meeting_type)
    return f"""用户选择的会议类型：{meeting.meeting_type}（{profile.display_name}）
可选会议类型：{choices}

会议主题：{meeting.topic}
参会人：{meeting.attendees}
转写开头：
{meeting.raw_transcript[:2000]}
"""


async def validate_route(llm: LLMClient, meeting: Meeting) -> RouteValidationResult:
    prompt = build_route_prompt(meeting)
    try:
        return await llm.structured_response(
            model=settings.extractor_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=RouteValidationResult,
        )
    except ValidationError:
        repair_prompt = f"{prompt}\n\n上次输出无法解析。请重新输出严格 JSON。"
        return await llm.structured_response(
            model=settings.extractor_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=repair_prompt,
            schema=RouteValidationResult,
        )

