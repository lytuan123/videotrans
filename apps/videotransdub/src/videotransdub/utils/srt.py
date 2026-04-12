from __future__ import annotations

import re
from pathlib import Path

from ..models import SubtitleSegment, SubtitleWord


_TIME_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2}),(?P<ms>\d{3})"
)


def srt_timestamp_to_seconds(value: str) -> float:
    match = _TIME_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {value}")
    parts = {key: int(raw) for key, raw in match.groupdict().items()}
    return parts["h"] * 3600 + parts["m"] * 60 + parts["s"] + parts["ms"] / 1000


def seconds_to_srt(value: float) -> str:
    total_ms = int(round(max(0.0, value) * 1000))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def write_srt(path: Path, segments: list[SubtitleSegment], translated: bool = False) -> None:
    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = segment.translated_text if translated and segment.translated_text else segment.text
        lines.extend([
            str(index),
            f"{seconds_to_srt(segment.start)} --> {seconds_to_srt(segment.end)}",
            text,
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def read_srt(path: Path) -> list[SubtitleSegment]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    blocks = re.split(r"\n\s*\n", raw)
    segments: list[SubtitleSegment] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        timerange = lines[1]
        start_raw, end_raw = [part.strip() for part in timerange.split("-->")]
        text = "\n".join(lines[2:])
        segments.append(
            SubtitleSegment(
                id=len(segments),
                start=srt_timestamp_to_seconds(start_raw),
                end=srt_timestamp_to_seconds(end_raw),
                text=text,
                words=[SubtitleWord(word=word, start=0.0, end=0.0) for word in text.split()],
            )
        )
    return segments
