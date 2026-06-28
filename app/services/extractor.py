from pydantic import ValidationError

from app.config import settings
from app.schemas import ExtractorResult, SegmentInput
from app.services.llm import LLMClient
from app.services.profiles import MeetingProfile, get_profile

SYSTEM_PROMPT = """你是科研组会转写片段提取器。
只输出符合 JSON Schema 的结构化结果。
判断片段语义是否闭合：闭合输出 closed，明显缺少后文输出 open。
提取任务时必须给出证据，无法确认负责人时 assignee 为空且 assignee_confidence 为 low。
"""


def build_user_prompt(segment: SegmentInput | dict, profile: MeetingProfile | None = None) -> str:
    if isinstance(segment, SegmentInput):
        payload = segment.model_dump()
    else:
        payload = segment
    profile = profile or get_profile("progress_meeting")
    return f"""请提取该会议片段中的摘要和任务。

会议类型：{profile.display_name}
类型化提取要求：{profile.extractor_instruction}

片段 JSON：
{payload}
"""


async def extract_segment(
    llm: LLMClient,
    segment: SegmentInput,
    profile: MeetingProfile | None = None,
) -> ExtractorResult:
    prompt = build_user_prompt(segment, profile)
    try:
        return await llm.structured_response(
            model=settings.extractor_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=ExtractorResult,
        )
    except ValidationError:
        repair_prompt = f"{prompt}\n\n上次输出无法解析。请重新输出严格 JSON，不要添加解释。"
        return await llm.structured_response(
            model=settings.extractor_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=repair_prompt,
            schema=ExtractorResult,
        )
