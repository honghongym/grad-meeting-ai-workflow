import json
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from openai import APIError, AsyncOpenAI, BadRequestError
from pydantic import BaseModel

from app.config import settings
from app.schemas import ExtractorResult, PlannerResult, PlannerSummary, RouteValidationResult

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    @abstractmethod
    async def structured_response(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        raise NotImplementedError


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
    if fenced:
        stripped = fenced.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return stripped
    return stripped[start : end + 1]


class BailianLLMClient(LLMClient):
    def __init__(self, api_key: str | None = None) -> None:
        self.client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    async def structured_response(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        messages = [
            {
                "role": "system",
                "content": (
                    f"{system_prompt}\n\n"
                    "你必须只输出一个 JSON 对象，不要输出 Markdown、代码块或解释文字。"
                    f"JSON 必须符合这个 schema：{schema_json}"
                ),
            },
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
        except (BadRequestError, APIError, TypeError):
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
            )
        raw = response.choices[0].message.content or ""
        return schema.model_validate_json(extract_json_object(raw))


class OpenAILLMClient(BailianLLMClient):
    def __init__(self, api_key: str | None = None) -> None:
        self.client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)

    async def structured_response(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        messages = [
            {
                "role": "system",
                "content": (
                    f"{system_prompt}\n\n"
                    "You must output only one JSON object and no Markdown."
                    f"The JSON must satisfy this schema: {schema_json}"
                ),
            },
            {"role": "user", "content": user_prompt},
        ]
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = response.choices[0].message.content or ""
        return schema.model_validate_json(extract_json_object(raw))


class FakeLLMClient(LLMClient):
    async def structured_response(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[T],
    ) -> T:
        if schema is ExtractorResult:
            segment_id = "unknown-seg"
            marker = '"segment_id": "'
            if marker in user_prompt:
                segment_id = user_prompt.split(marker, 1)[1].split('"', 1)[0]
            payload = {
                "segment_id": segment_id,
                "status": "closed",
                "content_summary": "本片段讨论了实验进展和下周任务。",
                "speaker_switch_count": 1,
                "mentioned_tasks": [
                    {
                        "task_name": "整理本周实验结果",
                        "assignee": "张三",
                        "assignee_confidence": "high",
                        "expected_output": "实验结果表",
                        "due_hint": "下次组会前",
                        "evidence": "会议中提到需要整理实验结果",
                    }
                ],
            }
            return schema.model_validate(payload)
        if schema is PlannerResult:
            payload = {
                "summary": PlannerSummary(
                    paper_discussion=["讨论了相关论文和实验设计。"],
                    experiment_progress=["同步了本周实验进展。"],
                    decisions=["下周继续补充对比实验。"],
                    risks=["负责人归属需人工确认。"],
                ).model_dump(),
                "tracking_table": [],
                "work_plan": [
                    {
                        "task_name": "整理本周实验结果",
                        "assignee": "张三",
                        "assignee_confidence": "high",
                        "expected_output": "实验结果表",
                        "deadline": "下次组会前",
                        "evidence": "Extractor 汇总任务",
                    }
                ],
                "review_notes": [],
                "type_specific": {
                    "paper_core_claims": ["示例核心主张"],
                    "method_notes": ["示例方法笔记"],
                    "limitations": [],
                    "open_questions": [],
                },
            }
            return schema.model_validate(payload)
        if schema is RouteValidationResult:
            return schema.model_validate(
                {
                    "suggested_type": "progress_meeting",
                    "confidence": "high",
                    "is_user_choice_reasonable": True,
                    "reason": "测试模式默认认为用户选择合理。",
                }
            )
        return schema.model_validate(json.loads("{}"))


def build_llm_client() -> LLMClient:
    if settings.use_fake_llm or not settings.openai_api_key:
        return FakeLLMClient()
    if settings.llm_provider.lower() in {"bailian", "dashscope", "aliyun"}:
        return BailianLLMClient()
    return OpenAILLMClient()
