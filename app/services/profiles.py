from dataclasses import dataclass


@dataclass(frozen=True)
class MeetingProfile:
    meeting_type: str
    display_name: str
    extractor_instruction: str
    planner_instruction: str
    type_specific_fields: dict[str, str]


PROFILES: dict[str, MeetingProfile] = {
    "progress_meeting": MeetingProfile(
        meeting_type="progress_meeting",
        display_name="周进展组会",
        extractor_instruction="重点提取成员进展、阻塞点、导师决策、下周任务和负责人。",
        planner_instruction="输出会议纪要、跨周任务追踪表和下周 Work Plan，强调任务归属与证据。",
        type_specific_fields={},
    ),
    "paper_reading": MeetingProfile(
        meeting_type="paper_reading",
        display_name="论文精读",
        extractor_instruction="重点提取论文问题、核心方法、实验设计、贡献、局限、疑问和后续阅读任务。",
        planner_instruction="输出论文概览、关键方法、争议点、局限、开放问题和后续阅读计划。",
        type_specific_fields={
            "paper_core_claims": "论文核心主张",
            "method_notes": "方法与实验笔记",
            "limitations": "局限与质疑点",
            "open_questions": "开放问题",
        },
    ),
    "experiment_review": MeetingProfile(
        meeting_type="experiment_review",
        display_name="实验复盘",
        extractor_instruction="重点提取实验现象、异常结果、失败原因假设、修复动作、风险项和负责人。",
        planner_instruction="输出实验现象、根因假设、修复计划、风险项和下一轮验证动作。",
        type_specific_fields={
            "observations": "实验现象",
            "root_cause_hypotheses": "根因假设",
            "fix_plan": "修复计划",
            "risk_items": "风险项",
        },
    ),
    "defense_rehearsal": MeetingProfile(
        meeting_type="defense_rehearsal",
        display_name="开题/答辩预演",
        extractor_instruction="重点提取答辩薄弱点、评委可能追问、回答策略、材料修改任务和负责人。",
        planner_instruction="输出薄弱问题、可能追问、回答策略和材料修改计划。",
        type_specific_fields={
            "weak_points": "薄弱点",
            "likely_questions": "可能追问",
            "answer_strategy": "回答策略",
            "slides_to_fix": "材料修改项",
        },
    ),
}


def get_profile(meeting_type: str | None) -> MeetingProfile:
    return PROFILES.get(meeting_type or "progress_meeting", PROFILES["progress_meeting"])


def profile_options() -> list[MeetingProfile]:
    return list(PROFILES.values())

