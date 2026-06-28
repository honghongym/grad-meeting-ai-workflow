from app.services.chunker import append_context, chunk_transcript


def test_chunk_transcript_generates_stable_segment_ids() -> None:
    transcript = "\n".join(
        [
            "[00:00:01] [张三]: 第一段讨论实验。",
            "[00:00:10] [李四]: 第二段讨论论文。",
            "[00:00:20] [导师]: 下周继续。",
        ]
    )

    chunks = chunk_transcript("mtg-20260628", transcript, target_tokens=5, hard_limit_tokens=20)

    assert chunks
    assert chunks[0].segment_id == "mtg-20260628-seg-001"
    assert chunks[0].position == 1


def test_append_context_limits_next_segment_chars() -> None:
    combined = append_context("A", "B" * 600, max_chars=10)

    assert "[追加上下文]" in combined
    assert combined.endswith("B" * 10)

