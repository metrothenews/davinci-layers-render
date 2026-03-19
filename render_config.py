from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from models import ClipSpec


class RenderConfigError(RuntimeError):
    pass


SUPPORTED_FORMAT_CODECS = {
    "MP4": {"H264"},
}


def validate_render_format_and_codec(render_format: str, codec: str) -> None:
    if render_format not in SUPPORTED_FORMAT_CODECS:
        supported_formats = ", ".join(sorted(SUPPORTED_FORMAT_CODECS.keys()))
        raise RenderConfigError(
            f"Unsupported render format {render_format!r}. Use one of: {supported_formats}. "
            "Note: format key must be uppercase (e.g. MP4, not mp4)."
        )
    if codec not in SUPPORTED_FORMAT_CODECS[render_format]:
        supported_codecs = ", ".join(sorted(SUPPORTED_FORMAT_CODECS[render_format]))
        raise RenderConfigError(
            f"Unsupported codec {codec!r} for format {render_format!r}. Use one of: {supported_codecs}."
        )


def apply_render_setup(project: Any, render_format: str, codec: str) -> None:
    validate_render_format_and_codec(render_format, codec)
    set_format_codec = getattr(project, "SetCurrentRenderFormatAndCodec", None)
    set_render_mode = getattr(project, "SetCurrentRenderMode", None)
    if not callable(set_format_codec):
        raise RenderConfigError("Project object is missing SetCurrentRenderFormatAndCodec(format, codec).")
    if not callable(set_render_mode):
        raise RenderConfigError("Project object is missing SetCurrentRenderMode(mode).")

    if not set_format_codec(render_format, codec):
        raise RenderConfigError(
            f"SetCurrentRenderFormatAndCodec({render_format!r}, {codec!r}) failed for current project/timeline."
        )
    if not set_render_mode(1):
        raise RenderConfigError("SetCurrentRenderMode(1) failed. Required for single-clip output.")


def build_render_settings(clip: ClipSpec, target_dir: Path) -> Dict[str, Any]:
    mark_in = clip.start_frame
    mark_out = clip.end_frame - 1
    if mark_out < mark_in:
        raise RenderConfigError(
            f"Invalid mark range for clip {clip.custom_name!r}: MarkIn={mark_in} MarkOut={mark_out}."
        )

    return {
        "SelectAllFrames": 0,
        "MarkIn": mark_in,
        "MarkOut": mark_out,
        "TargetDir": str(target_dir),
        "CustomName": clip.custom_name,
        "ExportVideo": 1,
        "ExportAudio": 1,
        "ReplaceExistingFilesInPlace": 1,
    }
