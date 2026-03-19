from __future__ import annotations

from pathlib import Path

import pytest

from timeline_reader import (
    SELECTION_AT_TIMELINE_START,
    SELECTION_FIRST_PER_TRACK,
    TimelineReadError,
    build_clip_plan,
    sanitize_clip_name,
)


class _FakeClip:
    def __init__(self, name: str, start: int, end: int):
        self._name = name
        self._start = start
        self._end = end

    def GetName(self):
        return self._name

    def GetStart(self):
        return self._start

    def GetEnd(self):
        return self._end


class _FakeTimeline:
    def __init__(self, start_frame: int, tracks: dict[int, list[_FakeClip]], start_timecode: str = "01:00:00:00"):
        self._start_frame = start_frame
        self._tracks = tracks
        self._start_timecode = start_timecode

    def GetName(self):
        return "Timeline 1"

    def GetStartTimecode(self):
        return self._start_timecode

    def GetStartFrame(self):
        return self._start_frame

    def GetTrackCount(self, media_type: str):
        if media_type == "video":
            return len(self._tracks)
        if media_type == "audio":
            return 2
        return 0

    def GetItemListInTrack(self, media_type: str, track_index: int):
        if media_type != "video":
            return []
        return self._tracks.get(track_index, [])


def test_sanitize_clip_name():
    assert sanitize_clip_name("Hello World!.mov") == "Hello_World_mov"
    assert sanitize_clip_name("  @@  ") == "clip"
    assert sanitize_clip_name("A-B_C") == "A-B_C"


def test_build_clip_plan_first_per_track_sorts_items():
    timeline = _FakeTimeline(
        start_frame=100,
        tracks={
            1: [_FakeClip("late", 120, 180), _FakeClip("early", 100, 150)],
            2: [_FakeClip("two", 105, 200)],
            3: [_FakeClip("three", 110, 210)],
        },
    )
    metadata, clips = build_clip_plan(
        timeline=timeline,
        output_dir=Path("/tmp/out"),
        selection_mode=SELECTION_FIRST_PER_TRACK,
        max_clips=3,
        container_format="MP4",
    )
    assert metadata.start_frame == 100
    assert [c.custom_name for c in clips] == ["01_early", "02_two", "03_three"]
    assert clips[0].start_frame == 100


def test_build_clip_plan_timeline_start_mode():
    timeline = _FakeTimeline(
        start_frame=100,
        tracks={
            1: [_FakeClip("clip_a", 100, 130), _FakeClip("clip_b", 120, 170)],
            2: [_FakeClip("clip_c", 105, 150), _FakeClip("clip_d", 100, 140)],
            3: [_FakeClip("clip_e", 100, 160)],
        },
    )
    _metadata, clips = build_clip_plan(
        timeline=timeline,
        output_dir=Path("/tmp/out"),
        selection_mode=SELECTION_AT_TIMELINE_START,
        max_clips=3,
        container_format="MP4",
    )
    assert [clip.start_frame for clip in clips] == [100, 100, 100]


def test_build_clip_plan_fails_if_less_than_required():
    timeline = _FakeTimeline(
        start_frame=100,
        tracks={1: [_FakeClip("only", 100, 120)], 2: [], 3: []},
    )
    with pytest.raises(TimelineReadError, match="Found 1 eligible clips"):
        build_clip_plan(
            timeline=timeline,
            output_dir=Path("/tmp/out"),
            selection_mode=SELECTION_FIRST_PER_TRACK,
            max_clips=3,
            container_format="MP4",
        )
