from app.schemas import ExtractedTask, ExtractorResult
from app.services.validator import validate_segments


def test_validator_dedupes_and_marks_missing_assignee_low() -> None:
    results = [
        ExtractorResult(
            segment_id="seg-1",
            status="closed",
            content_summary="summary",
            speaker_switch_count=0,
            mentioned_tasks=[
                ExtractedTask(task_name="整理实验结果", assignee="张三"),
                ExtractedTask(task_name="整理实验结果", assignee="张三"),
                ExtractedTask(task_name="补充对比实验", assignee=None),
            ],
        )
    ]

    bundle = validate_segments(results)

    assert len(bundle.tasks) == 2
    assert bundle.tasks[1].assignee_confidence == "low"
    assert any("缺失负责人" in warning for warning in bundle.warnings)


def test_validator_marks_noisy_speaker_low() -> None:
    results = [
        ExtractorResult(
            segment_id="seg-1",
            status="closed",
            content_summary="summary",
            speaker_switch_count=8,
            mentioned_tasks=[ExtractedTask(task_name="读论文", assignee="李四")],
        )
    ]

    bundle = validate_segments(results)

    assert bundle.tasks[0].assignee_confidence == "low"


def test_validator_keeps_confidence_when_assignee_has_evidence() -> None:
    results = [
        ExtractorResult(
            segment_id="seg-1",
            status="closed",
            content_summary="summary",
            speaker_switch_count=8,
            mentioned_tasks=[
                ExtractedTask(
                    task_name="整理实验结果",
                    assignee="老杨",
                    evidence="[00:01:00] [老杨]: 我来整理实验结果。",
                )
            ],
        )
    ]

    bundle = validate_segments(results)

    assert bundle.tasks[0].assignee_confidence == "high"
