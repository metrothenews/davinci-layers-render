from __future__ import annotations

from pathlib import Path

import pytest

from models import ClipSpec
from render_config import RenderConfigError, apply_render_setup, build_render_settings


class _FakeProject:
    def __init__(self, allow_format: bool = True, allow_mode: bool = True):
        self.allow_format = allow_format
        self.allow_mode = allow_mode
        self.last_format = None
        self.last_mode = None

    def SetCurrentRenderFormatAndCodec(self, render_format, codec):
        self.last_format = (render_format, codec)
        return self.allow_format

    def SetCurrentRenderMode(self, mode):
        self.last_mode = mode
        return self.allow_mode


def test_apply_render_setup_success():
    project = _FakeProject()
    apply_render_setup(project, "MP4", "H264")
    assert project.last_format == ("MP4", "H264")
    assert project.last_mode == 1


def test_apply_render_setup_format_regression_lowercase_mp4_rejected():
    project = _FakeProject()
    with pytest.raises(RenderConfigError, match="must be uppercase"):
        apply_render_setup(project, "mp4", "H264")


def test_build_render_settings_mark_out_is_end_minus_one():
    clip = ClipSpec(
        track_index=1,
        source_name="source",
        sanitized_name="source",
        custom_name="01_source",
        start_frame=100,
        end_frame=120,
        duration_frames=20,
        output_path="/tmp/out/01_source.mp4",
    )
    settings = build_render_settings(clip, Path("/tmp/out"))
    assert settings["MarkIn"] == 100
    assert settings["MarkOut"] == 119
    assert settings["ExportVideo"] == 1
    assert settings["ExportAudio"] == 1
