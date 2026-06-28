from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_create_meeting_api_returns_pending() -> None:
    settings.use_fake_llm = True
    client = TestClient(app)

    response = client.post(
        "/meetings",
        data={
            "meeting_date": "2026-06-28",
            "meeting_type": "paper_reading",
            "topic": "测试组会",
            "attendees": "张三, 李四",
            "transcript": "[00:00:01] [张三]: 本周完成实验，下周整理结果。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meeting_id"].startswith("mtg-20260628")
    assert payload["status"] == "pending"


def test_progress_api_returns_progress_payload() -> None:
    settings.use_fake_llm = True
    client = TestClient(app)

    create_response = client.post(
        "/meetings",
        data={
            "meeting_date": "2026-06-29",
            "meeting_type": "progress_meeting",
            "topic": "进度测试",
            "attendees": "老杨",
            "transcript": "[00:00:01] [老杨]: 下周整理实验结果。",
        },
    )
    meeting_id = create_response.json()["meeting_id"]

    response = client.get(f"/api/meetings/{meeting_id}/progress")

    assert response.status_code == 200
    payload = response.json()
    assert {"status", "label", "percent", "is_running"}.issubset(payload)


def test_json_api_create_result_and_markdown() -> None:
    settings.use_fake_llm = True
    client = TestClient(app)

    response = client.post(
        "/api/meetings",
        json={
            "meeting_date": "2026-07-10",
            "meeting_type": "paper_reading",
            "topic": "插件测试会议",
            "attendees": ["老杨", "老秦"],
            "transcript": "[00:00:01] [老杨]: 这篇论文的方法值得整理。",
        },
    )

    assert response.status_code == 200
    meeting_id = response.json()["meeting_id"]

    result = client.get(f"/api/meetings/{meeting_id}/result")
    assert result.status_code == 200
    assert result.json()["meeting_type"] == "paper_reading"

    markdown = client.get(f"/api/meetings/{meeting_id}/markdown")
    assert markdown.status_code == 200
    assert "插件测试会议" in markdown.text
