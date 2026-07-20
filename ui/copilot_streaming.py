from __future__ import annotations

COPILOT_STREAM_MAX_CHUNKS = 8


def stream_chunks(text: str) -> list[str]:
    """Build deterministic progressive text snapshots for the Copilot UI."""

    normalized = str(text or "").strip()
    if not normalized:
        return [""]
    segments = stream_segments(normalized)
    if len(segments) > 1:
        chunk_count = min(COPILOT_STREAM_MAX_CHUNKS, len(segments))
        chunks = []
        for step in range(1, chunk_count + 1):
            boundary = (len(segments) * step + chunk_count - 1) // chunk_count
            chunks.append("".join(segments[:boundary]).strip())
        return deduplicate_stream_chunks(chunks, normalized)
    chunk_count = min(
        COPILOT_STREAM_MAX_CHUNKS,
        max(2, min(6, (len(normalized) + 23) // 24)),
    )
    chunks = [
        normalized[: (len(normalized) * step + chunk_count - 1) // chunk_count]
        for step in range(1, chunk_count + 1)
    ]
    return deduplicate_stream_chunks(chunks, normalized)


def stream_segments(text: str) -> list[str]:
    sentence_segments = split_stream_segments(text, "。！？!?\n")
    if len(sentence_segments) > 1:
        return sentence_segments
    phrase_segments = split_stream_segments(text, "、，,;；:")
    return phrase_segments if len(phrase_segments) > 1 else [text]


def split_stream_segments(text: str, break_chars: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    for character in text:
        current.append(character)
        if character in break_chars:
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
    tail = "".join(current).strip()
    if tail:
        segments.append(tail)
    return segments


def deduplicate_stream_chunks(chunks: list[str], final_text: str) -> list[str]:
    deduplicated: list[str] = []
    for chunk in chunks:
        if chunk and (not deduplicated or chunk != deduplicated[-1]):
            deduplicated.append(chunk)
    if not deduplicated or deduplicated[-1] != final_text:
        deduplicated.append(final_text)
    return deduplicated
