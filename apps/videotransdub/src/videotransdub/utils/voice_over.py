from __future__ import annotations

import re

from ..models import SubtitleSegment


_SENTENCE_END_RE = re.compile(r"[.!?;:。！？；:]$")
_SPACE_RE = re.compile(r"\s+")


def normalize_voice_text(value: str) -> str:
    return _SPACE_RE.sub(" ", value.replace("\n", " ").strip())


def join_voice_text(current: str, new_text: str) -> str:
    new_text = normalize_voice_text(new_text)
    if not current:
        return new_text
    separator = " " if _SENTENCE_END_RE.search(current) else ". "
    return f"{current}{separator}{new_text}"


def build_voice_over_segments(
    segments: list[SubtitleSegment],
    *,
    max_chunk_chars: int,
    max_gap_seconds: float,
    min_chunk_seconds: float,
) -> list[SubtitleSegment]:
    narration_segments: list[SubtitleSegment] = []
    current: list[SubtitleSegment] = []
    current_text = ""

    def flush() -> None:
        nonlocal current, current_text
        if not current:
            return
        start = current[0].start
        end = max(current[-1].end, start + min_chunk_seconds)
        narration_segments.append(
            SubtitleSegment(
                id=len(narration_segments),
                start=start,
                end=end,
                text=current_text,
                metadata={
                    "mode": "voice_over",
                    "source_segment_ids": [segment.id for segment in current],
                },
            )
        )
        current = []
        current_text = ""

    for segment in segments:
        source_text = segment.translated_text or segment.text
        source_text = normalize_voice_text(source_text)
        if not source_text:
            continue

        if not current:
            current = [segment]
            current_text = source_text
            continue

        gap = max(0.0, segment.start - current[-1].end)
        candidate_text = join_voice_text(current_text, source_text)
        if gap > max_gap_seconds or len(candidate_text) > max_chunk_chars:
            flush()
            current = [segment]
            current_text = source_text
            continue

        current.append(segment)
        current_text = candidate_text

    flush()
    return narration_segments
