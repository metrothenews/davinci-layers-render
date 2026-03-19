from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Dict

from models import TrackStateSnapshot


class TrackStateError(RuntimeError):
    pass


def _to_bool_state(value: Any, media_type: str, track_index: int) -> bool:
    if value is None:
        raise TrackStateError(
            f"GetIsTrackEnabled({media_type!r}, {track_index}) returned None while snapshotting track state."
        )
    return bool(value)


def snapshot_track_states(timeline: Any) -> TrackStateSnapshot:
    get_track_count = getattr(timeline, "GetTrackCount", None)
    get_track_enabled = getattr(timeline, "GetIsTrackEnabled", None)
    if not callable(get_track_count) or not callable(get_track_enabled):
        raise TrackStateError("Timeline object is missing GetTrackCount/GetIsTrackEnabled methods.")

    video_count = int(get_track_count("video"))
    audio_count = int(get_track_count("audio"))

    video_states: Dict[int, bool] = {}
    audio_states: Dict[int, bool] = {}
    for track_index in range(1, video_count + 1):
        video_states[track_index] = _to_bool_state(get_track_enabled("video", track_index), "video", track_index)
    for track_index in range(1, audio_count + 1):
        audio_states[track_index] = _to_bool_state(get_track_enabled("audio", track_index), "audio", track_index)

    return TrackStateSnapshot(video_states=video_states, audio_states=audio_states)


def set_track_enabled(timeline: Any, media_type: str, track_index: int, enabled: bool) -> None:
    set_track_enable = getattr(timeline, "SetTrackEnable", None)
    if not callable(set_track_enable):
        raise TrackStateError("Timeline object is missing SetTrackEnable(media_type, track_index, enabled).")
    success = set_track_enable(media_type, track_index, bool(enabled))
    if success is False:
        raise TrackStateError(
            f"SetTrackEnable({media_type!r}, {track_index}, {bool(enabled)}) returned False."
        )


def set_video_track_exclusive(timeline: Any, total_video_tracks: int, target_video_track: int) -> None:
    for track_index in range(1, total_video_tracks + 1):
        set_track_enabled(timeline, "video", track_index, track_index == target_video_track)


def set_video_tracks_with_upper_layers_disabled(
    timeline: Any,
    total_video_tracks: int,
    target_video_track: int,
) -> None:
    # Resolve video track indices increase from bottom to top; disable tracks above target only.
    for track_index in range(1, total_video_tracks + 1):
        set_track_enabled(timeline, "video", track_index, track_index <= target_video_track)


def set_video_track_mask(timeline: Any, total_video_tracks: int, enabled_video_tracks: Iterable[int]) -> None:
    enabled = set(int(track) for track in enabled_video_tracks)
    for track_index in range(1, total_video_tracks + 1):
        set_track_enabled(timeline, "video", track_index, track_index in enabled)


def enable_all_audio_tracks(timeline: Any, total_audio_tracks: int) -> None:
    for track_index in range(1, total_audio_tracks + 1):
        set_track_enabled(timeline, "audio", track_index, True)


def restore_track_states(timeline: Any, snapshot: TrackStateSnapshot) -> None:
    errors = []
    for track_index, enabled in snapshot.video_states.items():
        try:
            set_track_enabled(timeline, "video", track_index, enabled)
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(str(exc))
    for track_index, enabled in snapshot.audio_states.items():
        try:
            set_track_enabled(timeline, "audio", track_index, enabled)
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(str(exc))

    if errors:
        joined = "; ".join(errors)
        raise TrackStateError(f"Failed restoring track states: {joined}")
