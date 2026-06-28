from app.schemas import PlannerResult
from app.services.embeddings import normalize_embedding
from app.services.llm import BailianLLMClient, extract_json_object


def test_extract_json_object_from_fenced_text() -> None:
    raw = '```json\n{"summary": {"paper_discussion": [], "experiment_progress": [], "decisions": [], "risks": []}}\n```'

    assert extract_json_object(raw).startswith("{")


def test_planner_schema_validates_extracted_json() -> None:
    payload = extract_json_object(
        """
        这里是结果：
        {
          "summary": {
            "paper_discussion": [],
            "experiment_progress": [],
            "decisions": [],
            "risks": []
          },
          "tracking_table": [],
          "work_plan": [],
          "review_notes": [],
          "type_specific": {"paper_core_claims": []}
        }
        """
    )

    result = PlannerResult.model_validate_json(payload)

    assert result.summary.decisions == []


def test_normalize_embedding_to_configured_dimension() -> None:
    assert len(normalize_embedding([1.0, 2.0])) == 1536
    assert normalize_embedding([1.0] * 2000) == [1.0] * 1536


def test_bailian_client_uses_compatible_base_url() -> None:
    client = BailianLLMClient(api_key="test-key")

    assert "dashscope.aliyuncs.com/compatible-mode/v1" in str(client.client.base_url)
