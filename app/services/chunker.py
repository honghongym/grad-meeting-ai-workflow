import re

from app.schemas import SegmentInput

SPEAKER_LINE = re.compile(r"^\s*(\[[0-9]{2}:[0-9]{2}(?::[0-9]{2})?\])?\s*\[[^\]]+\]:")


def estimate_tokens(text: str) -> int:
    # Good enough for chunk sizing in Chinese-heavy transcripts.
    ascii_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    non_ascii = len(re.findall(r"[^\x00-\x7F]", text))
    punctuation = len(re.findall(r"[，。！？；：,.!?;:]", text))
    return max(1, ascii_words + non_ascii // 2 + punctuation // 4)


def split_turns(transcript: str) -> list[str]:
    turns: list[str] = []
    current: list[str] = []
    for line in transcript.splitlines():
        if SPEAKER_LINE.search(line) and current:
            turns.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        turns.append("\n".join(current).strip())
    return [turn for turn in turns if turn]


def chunk_transcript(
    meeting_id: str,
    transcript: str,
    target_tokens: int = 1800,
    hard_limit_tokens: int = 2200,
) -> list[SegmentInput]:
    turns = split_turns(transcript)
    if not turns:
        turns = [transcript]

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for turn in turns:
        turn_tokens = estimate_tokens(turn)
        should_flush = current and (
            current_tokens + turn_tokens > hard_limit_tokens or current_tokens >= target_tokens
        )
        if should_flush:
            chunks.append("\n".join(current).strip())
            current = []
            current_tokens = 0

        current.append(turn)
        current_tokens += turn_tokens

    if current:
        chunks.append("\n".join(current).strip())

    return [
        SegmentInput(
            segment_id=f"{meeting_id}-seg-{index:03d}",
            position=index,
            text=chunk,
            token_estimate=estimate_tokens(chunk),
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


def append_context(text: str, next_text: str, max_chars: int = 500) -> str:
    if not next_text:
        return text
    return f"{text}\n\n[追加上下文]\n{next_text[:max_chars]}"

