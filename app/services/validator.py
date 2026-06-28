import re

from app.schemas import ExtractedTask, ExtractorResult, ValidatedBundle


def normalize_task_name(task_name: str) -> str:
    return re.sub(r"\s+", "", task_name).strip().lower()


def has_direct_assignee_evidence(task: ExtractedTask) -> bool:
    if not task.assignee:
        return False
    evidence = task.evidence or ""
    expected = task.expected_output or ""
    return task.assignee in evidence or task.assignee in expected


def validate_segments(results: list[ExtractorResult]) -> ValidatedBundle:
    seen: set[tuple[str, str]] = set()
    tasks: list[ExtractedTask] = []
    warnings: list[str] = []
    summaries: list[str] = []

    for result in results:
        summaries.append(result.content_summary)
        if result.warning:
            warnings.append(f"{result.segment_id}: {result.warning}")
        if result.status == "closed_with_warning":
            warnings.append(f"{result.segment_id}: 语义未完全闭合，请人工复核。")

        for task in result.mentioned_tasks:
            key = (normalize_task_name(task.task_name), task.assignee or "unknown")
            if key in seen:
                continue
            seen.add(key)

            if not task.assignee:
                task.assignee_confidence = "low"
                warnings.append(f"{task.task_name}: 缺失负责人。")
            elif result.speaker_switch_count > 6 and not has_direct_assignee_evidence(task):
                task.assignee_confidence = "low"
                warnings.append(f"{task.task_name}: 说话人切换较多且证据中缺少负责人确认。")
            tasks.append(task)

    if tasks:
        low_count = sum(1 for task in tasks if task.assignee_confidence == "low")
        if low_count / len(tasks) > 0.3:
            warnings.append("低置信度任务超过 30%，发布前建议人工全量复核负责人。")

    return ValidatedBundle(content_summaries=summaries, tasks=tasks, warnings=warnings)
