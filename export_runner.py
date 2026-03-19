from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from models import ClipSpec, RenderJobResult
from render_config import apply_render_setup, build_render_settings
from state_restore import (
    enable_all_audio_tracks,
    restore_track_states,
    set_video_track_mask,
    snapshot_track_states,
)


class ExportRunError(RuntimeError):
    pass


class _ClipMaskContext:
    def __init__(self, items_by_track: Dict[int, List[Any]], original_clip_states: List[Tuple[Any, bool]]):
        self.items_by_track = items_by_track
        self.original_clip_states = original_clip_states


def _get_current_page(resolve: Any) -> str:
    method = getattr(resolve, "GetCurrentPage", None)
    if not callable(method):
        return ""
    value = method()
    return str(value or "")


def _open_page(resolve: Any, page_name: str) -> bool:
    method = getattr(resolve, "OpenPage", None)
    if not callable(method):
        return False
    return bool(method(page_name))


def _extract_status(job_status: Any) -> Tuple[str, int]:
    if not isinstance(job_status, dict):
        return "Unknown", 0
    status = str(job_status.get("JobStatus") or job_status.get("Status") or "Unknown")
    raw_progress = job_status.get("CompletionPercentage", job_status.get("Progress", 0))
    try:
        progress = int(float(raw_progress))
    except (TypeError, ValueError):
        progress = 0
    return status, progress


def _failed_result(
    clip: ClipSpec,
    status: str,
    elapsed_seconds: float,
    error: str,
    job_id: str = "",
    progress: int = 0,
) -> RenderJobResult:
    return RenderJobResult(
        job_id=job_id,
        clip_name=clip.custom_name,
        status=status,
        progress=progress,
        elapsed_seconds=elapsed_seconds,
        output_file=clip.output_path,
        success=False,
        error=error,
    )


def _normalize_track_items(raw_items: Any) -> List[Any]:
    if raw_items is None:
        return []
    if isinstance(raw_items, dict):
        return list(raw_items.values())
    if isinstance(raw_items, (list, tuple)):
        return list(raw_items)
    return list(raw_items)


def _build_clip_mask_context(timeline: Any, total_video_tracks: int) -> _ClipMaskContext | None:
    get_items = getattr(timeline, "GetItemListInTrack", None)
    if not callable(get_items):
        return None

    items_by_track: Dict[int, List[Any]] = {}
    original_clip_states: List[Tuple[Any, bool]] = []
    for track_index in range(1, total_video_tracks + 1):
        items = _normalize_track_items(get_items("video", track_index))
        items_by_track[track_index] = items
        for item in items:
            get_enabled = getattr(item, "GetClipEnabled", None)
            set_enabled = getattr(item, "SetClipEnabled", None)
            if not callable(get_enabled) or not callable(set_enabled):
                return None
            original_clip_states.append((item, bool(get_enabled())))

    return _ClipMaskContext(items_by_track=items_by_track, original_clip_states=original_clip_states)


def _apply_clip_mask(context: _ClipMaskContext, enabled_video_tracks: Set[int]) -> None:
    for track_index, items in context.items_by_track.items():
        enabled = track_index in enabled_video_tracks
        for item in items:
            success = item.SetClipEnabled(enabled)
            if success is False:
                raise ExportRunError(
                    f"TimelineItem.SetClipEnabled({enabled}) failed for track {track_index} during clip masking."
                )


def _restore_clip_mask(context: _ClipMaskContext) -> None:
    errors = []
    for item, enabled in context.original_clip_states:
        try:
            success = item.SetClipEnabled(enabled)
            if success is False:
                errors.append("SetClipEnabled returned False")
        except Exception as exc:  # pragma: no cover - defensive path
            errors.append(str(exc))
    if errors:
        raise ExportRunError(f"Failed restoring clip enabled states: {'; '.join(errors)}")


def _render_one_clip(
    project: Any,
    timeline: Any,
    clip: ClipSpec,
    output_dir: Path,
    enabled_video_tracks: Set[int],
    clip_mask_context: _ClipMaskContext | None,
    total_video_tracks: int,
    total_audio_tracks: int,
    timeout_seconds: int,
    poll_seconds: float,
) -> RenderJobResult:
    started_at = time.monotonic()
    try:
        set_video_track_mask(timeline, total_video_tracks, enabled_video_tracks)
        if clip_mask_context is not None:
            _apply_clip_mask(clip_mask_context, enabled_video_tracks)
        enable_all_audio_tracks(timeline, total_audio_tracks)
    except Exception as exc:
        return _failed_result(
            clip=clip,
            status="TrackStateError",
            elapsed_seconds=time.monotonic() - started_at,
            error=f"Track enable operation failed for clip {clip.custom_name!r}: {exc}",
        )

    settings = build_render_settings(clip, output_dir)
    set_render_settings = getattr(project, "SetRenderSettings", None)
    add_render_job = getattr(project, "AddRenderJob", None)
    start_rendering = getattr(project, "StartRendering", None)
    is_rendering_in_progress = getattr(project, "IsRenderingInProgress", None)
    get_render_job_status = getattr(project, "GetRenderJobStatus", None)
    stop_rendering = getattr(project, "StopRendering", None)

    if not callable(set_render_settings):
        return _failed_result(
            clip=clip,
            status="SetupError",
            elapsed_seconds=time.monotonic() - started_at,
            error="Project object missing SetRenderSettings(settings).",
        )
    if not callable(add_render_job):
        return _failed_result(
            clip=clip,
            status="SetupError",
            elapsed_seconds=time.monotonic() - started_at,
            error="Project object missing AddRenderJob().",
        )
    if not callable(start_rendering):
        return _failed_result(
            clip=clip,
            status="SetupError",
            elapsed_seconds=time.monotonic() - started_at,
            error="Project object missing StartRendering(job_ids, interactive).",
        )
    if not callable(is_rendering_in_progress):
        return _failed_result(
            clip=clip,
            status="SetupError",
            elapsed_seconds=time.monotonic() - started_at,
            error="Project object missing IsRenderingInProgress().",
        )
    if not callable(get_render_job_status):
        return _failed_result(
            clip=clip,
            status="SetupError",
            elapsed_seconds=time.monotonic() - started_at,
            error="Project object missing GetRenderJobStatus(job_id).",
        )

    if not set_render_settings(settings):
        return _failed_result(
            clip=clip,
            status="ConfigError",
            elapsed_seconds=time.monotonic() - started_at,
            error=f"SetRenderSettings failed for clip {clip.custom_name!r}.",
        )

    job_id = add_render_job()
    if not job_id:
        return _failed_result(
            clip=clip,
            status="QueueError",
            elapsed_seconds=time.monotonic() - started_at,
            error=f"AddRenderJob failed for clip {clip.custom_name!r}.",
        )
    job_id_str = str(job_id)

    if not start_rendering([job_id], False):
        return _failed_result(
            clip=clip,
            status="StartError",
            job_id=job_id_str,
            elapsed_seconds=time.monotonic() - started_at,
            error=f"StartRendering([{job_id!r}], False) failed for clip {clip.custom_name!r}.",
        )

    deadline = started_at + timeout_seconds
    while True:
        in_progress = bool(is_rendering_in_progress())
        if not in_progress:
            break
        if time.monotonic() > deadline:
            if callable(stop_rendering):
                stop_rendering()
            return _failed_result(
                clip=clip,
                status="Timeout",
                job_id=job_id_str,
                elapsed_seconds=time.monotonic() - started_at,
                error=f"Render job {job_id_str} for clip {clip.custom_name!r} timed out after {timeout_seconds}s.",
            )
        time.sleep(poll_seconds)

    status_payload = get_render_job_status(job_id)
    status, progress = _extract_status(status_payload)
    success = "complete" in status.lower()
    error = ""
    if not success:
        error = f"GetRenderJobStatus({job_id_str}) returned status={status!r}, progress={progress}."

    return RenderJobResult(
        job_id=job_id_str,
        clip_name=clip.custom_name,
        status=status,
        progress=progress,
        elapsed_seconds=time.monotonic() - started_at,
        output_file=clip.output_path,
        success=success,
        error=error,
    )


def run_export_jobs(
    resolve: Any,
    project: Any,
    timeline: Any,
    clips: List[ClipSpec],
    output_dir: Path,
    render_format: str,
    codec: str,
    top_track_is: str = "lowest-index",
    timeout_seconds: int = 600,
    poll_seconds: float = 0.5,
    logger: logging.Logger | None = None,
) -> Tuple[List[RenderJobResult], List[str]]:
    warnings: List[str] = []
    results: List[RenderJobResult] = []

    snapshot = snapshot_track_states(timeline)
    original_page = _get_current_page(resolve)

    try:
        if not _open_page(resolve, "deliver"):
            raise ExportRunError("OpenPage('deliver') failed.")
        apply_render_setup(project, render_format, codec)

        total_video_tracks = len(snapshot.video_states)
        total_audio_tracks = len(snapshot.audio_states)
        clip_mask_context = _build_clip_mask_context(timeline, total_video_tracks)
        if top_track_is not in ("lowest-index", "highest-index"):
            raise ExportRunError(f"Invalid top_track_is value: {top_track_is!r}.")
        reverse = top_track_is == "highest-index"
        render_sequence = sorted(clips, key=lambda clip: clip.track_index, reverse=reverse)
        disabled_tracks: Set[int] = set()
        for clip in render_sequence:
            enabled_video_tracks = set(range(1, total_video_tracks + 1)) - disabled_tracks
            result = _render_one_clip(
                project=project,
                timeline=timeline,
                clip=clip,
                output_dir=output_dir,
                enabled_video_tracks=enabled_video_tracks,
                clip_mask_context=clip_mask_context,
                total_video_tracks=total_video_tracks,
                total_audio_tracks=total_audio_tracks,
                timeout_seconds=timeout_seconds,
                poll_seconds=poll_seconds,
            )
            results.append(result)
            disabled_tracks.add(clip.track_index)
            if logger:
                logger.info(
                    "clip=%s job_id=%s status=%s progress=%s elapsed=%.2fs enabled_video_tracks=%s",
                    result.clip_name,
                    result.job_id or "-",
                    result.status,
                    result.progress,
                    result.elapsed_seconds,
                    sorted(enabled_video_tracks),
                )
    finally:
        if "clip_mask_context" in locals() and clip_mask_context is not None:
            try:
                _restore_clip_mask(clip_mask_context)
            except Exception as exc:
                warnings.append(str(exc))
                if logger:
                    logger.error("Clip-state restore failed: %s", exc)
        try:
            restore_track_states(timeline, snapshot)
        except Exception as exc:
            warnings.append(str(exc))
            if logger:
                logger.error("Track restore failed: %s", exc)

        if original_page:
            if not _open_page(resolve, original_page):
                message = f"Failed to restore Resolve page to {original_page!r}."
                warnings.append(message)
                if logger:
                    logger.warning(message)

    return results, warnings
