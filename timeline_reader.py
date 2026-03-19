from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, List, Set, Tuple

from models import ClipSpec, TimelineMetadata

SELECTION_FIRST_PER_TRACK = "first-per-track"
SELECTION_AT_TIMELINE_START = "at-timeline-start"
VALID_SELECTION_MODES = (SELECTION_FIRST_PER_TRACK, SELECTION_AT_TIMELINE_START)


class TimelineReadError(RuntimeError):
    pass


def _to_int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TimelineReadError(f"{label} returned non-integer value: {value!r}") from exc


def _safe_clip_name(item: Any, track_index: int) -> str:
    get_name = getattr(item, "GetName", None)
    if callable(get_name):
        raw_name = get_name()
        if isinstance(raw_name, str) and raw_name.strip():
            return raw_name.strip()
    return f"track_{track_index}_clip"


def _normalize_track_items(raw_items: Any) -> List[Any]:
    if raw_items is None:
        return []
    if isinstance(raw_items, dict):
        return list(raw_items.values())
    if isinstance(raw_items, (list, tuple)):
        return list(raw_items)
    if isinstance(raw_items, Iterable):
        return list(raw_items)
    return []


def _format_extension(container_format: str) -> str:
    normalized = (container_format or "").strip().upper()
    if normalized == "MP4":
        return "mp4"
    return normalized.lower() if normalized else "mp4"


def sanitize_clip_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "").strip())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized or "clip"


def read_timeline_metadata(timeline: Any) -> TimelineMetadata:
    get_name = getattr(timeline, "GetName", None)
    get_start_timecode = getattr(timeline, "GetStartTimecode", None)
    get_start_frame = getattr(timeline, "GetStartFrame", None)
    get_track_count = getattr(timeline, "GetTrackCount", None)
    if not callable(get_name) or not callable(get_start_timecode) or not callable(get_start_frame) or not callable(
        get_track_count
    ):
        raise TimelineReadError("Timeline object is missing required metadata methods.")

    name = str(get_name() or "")
    start_timecode = str(get_start_timecode() or "")
    start_frame = _to_int(get_start_frame(), "GetStartFrame")
    video_track_count = _to_int(get_track_count("video"), 'GetTrackCount("video")')
    audio_track_count = _to_int(get_track_count("audio"), 'GetTrackCount("audio")')

    return TimelineMetadata(
        name=name,
        start_timecode=start_timecode,
        start_frame=start_frame,
        video_track_count=video_track_count,
        audio_track_count=audio_track_count,
    )


def _select_clip_for_track(items: List[Any], selection_mode: str, start_frame: int) -> Any:
    ordered = sorted(items, key=lambda item: _to_int(item.GetStart(), "GetStart"))
    if not ordered:
        return None

    if selection_mode == SELECTION_FIRST_PER_TRACK:
        return ordered[0]
    if selection_mode == SELECTION_AT_TIMELINE_START:
        for item in ordered:
            if _to_int(item.GetStart(), "GetStart") == start_frame:
                return item
        return None
    raise TimelineReadError(f"Unknown selection_mode={selection_mode!r}.")


def _build_unique_name(base_name: str, used_names: Set[str]) -> str:
    if base_name not in used_names:
        used_names.add(base_name)
        return base_name

    suffix = 2
    while True:
        candidate = f"{base_name}_{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        suffix += 1


def build_clip_plan(
    timeline: Any,
    output_dir: Path,
    selection_mode: str,
    max_clips: int,
    container_format: str,
) -> Tuple[TimelineMetadata, List[ClipSpec]]:
    if selection_mode not in VALID_SELECTION_MODES:
        raise TimelineReadError(f"Invalid selection mode: {selection_mode!r}. Expected one of {VALID_SELECTION_MODES}.")
    if max_clips < 1:
        raise TimelineReadError(f"--max-clips must be >= 1, got {max_clips}.")

    metadata = read_timeline_metadata(timeline)
    extension = _format_extension(container_format)
    used_names: Set[str] = set()
    planned: List[ClipSpec] = []
    get_items_in_track = getattr(timeline, "GetItemListInTrack", None)
    if not callable(get_items_in_track):
        raise TimelineReadError("Timeline object is missing GetItemListInTrack(media_type, track_index).")

    for track_index in range(1, metadata.video_track_count + 1):
        raw_items = get_items_in_track("video", track_index)
        items = _normalize_track_items(raw_items)
        if not items:
            continue

        target_item = _select_clip_for_track(items, selection_mode, metadata.start_frame)
        if target_item is None:
            continue

        start_frame = _to_int(target_item.GetStart(), f"GetStart track={track_index}")
        end_frame = _to_int(target_item.GetEnd(), f"GetEnd track={track_index}")
        if end_frame <= start_frame:
            raise TimelineReadError(
                f"Clip on track {track_index} has invalid range: start={start_frame} end={end_frame}."
            )

        source_name = _safe_clip_name(target_item, track_index)
        sanitized_name = sanitize_clip_name(source_name)
        base_custom_name = f"{track_index:02d}_{sanitized_name}"
        custom_name = _build_unique_name(base_custom_name, used_names)
        output_path = str(output_dir / f"{custom_name}.{extension}")
        planned.append(
            ClipSpec(
                track_index=track_index,
                source_name=source_name,
                sanitized_name=sanitized_name,
                custom_name=custom_name,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=end_frame - start_frame,
                output_path=output_path,
            )
        )

    if len(planned) < max_clips:
        raise TimelineReadError(
            f"Found {len(planned)} eligible clips across video tracks, but --max-clips={max_clips} requires at least {max_clips}."
        )

    return metadata, planned[:max_clips]
