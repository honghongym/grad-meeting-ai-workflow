from pydantic import ValidationError

from app.config import settings
from app.schemas import PlannerResult, ValidatedBundle
from app.services.llm import LLMClient
from app.services.profiles import MeetingProfile, get_profile

SYSTEM_PROMPT = """你是科研组会 Planner。
你会收到本周片段摘要、提取任务、上周任务和少量历史上下文。
请一次性输出 summary、tracking_table、work_plan、review_notes。
不要编造负责人；低置信度任务必须保留 low 标记。
"""


def build_user_prompt(
    bundle: ValidatedBundle,
    previous_work_items: list[dict],
    relevant_history: list[dict],
    profile: MeetingProfile | None = None,
) -> str:
    profile = profile or get_profile("progress_meeting")
    return f"""本周聚合结果：
{bundle.model_dump()}

上周 Work Plan：
{previous_work_items}

历史相关片段 Top-3：
{relevant_history}

会议类型：{profile.display_name}
类型化规划要求：{profile.planner_instruction}
type_specific 需要覆盖这些字段：{profile.type_specific_fields}
"""


async def plan_meeting(
    llm: LLMClient,
    bundle: ValidatedBundle,
    previous_work_items: list[dict],
    relevant_history: list[dict],
    profile: MeetingProfile | None = None,
) -> PlannerResult:
    profile = profile or get_profile("progress_meeting")
    prompt = build_user_prompt(bundle, previous_work_items, relevant_history, profile)
    try:
        return await llm.structured_response(
            model=settings.planner_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=PlannerResult,
        )
    except ValidationError:
        repair_prompt = f"{prompt}\n\n上次输出无法解析。请重新输出严格 JSON。"
        return await llm.structured_response(
            model=settings.planner_model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=repair_prompt,
            schema=PlannerResult,
        )
