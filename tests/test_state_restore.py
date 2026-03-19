from __future__ import annotations

import pytest

from state_restore import (
    TrackStateError,
    enable_all_audio_tracks,
    restore_track_states,
    set_video_track_exclusive,
    set_video_tracks_with_upper_layers_disabled,
    snapshot_track_states,
)


class _FakeTimeline:
    def __init__(self):
        self.video = {1: True, 2: False, 3: True}
        self.audio = {1: False, 2: True}
        self.fail_on_set = set()

    def GetTrackCount(self, media_type):
        return len(self.video) if media_type == "video" else len(self.audio)

    def GetIsTrackEnabled(self, media_type, track_index):
        source = self.video if media_type == "video" else self.audio
        return source[track_index]

    def SetTrackEnable(self, media_type, track_index, enabled):
        if (media_type, track_index) in self.fail_on_set:
            return False
        source = self.video if media_type == "video" else self.audio
        source[track_index] = bool(enabled)
        return True


def test_snapshot_and_restore_track_states():
    timeline = _FakeTimeline()
    snapshot = snapshot_track_states(timeline)

    set_video_track_exclusive(timeline, total_video_tracks=3, target_video_track=2)
    enable_all_audio_tracks(timeline, total_audio_tracks=2)
    assert timeline.video == {1: False, 2: True, 3: False}
    assert timeline.audio == {1: True, 2: True}

    restore_track_states(timeline, snapshot)
    assert timeline.video == {1: True, 2: False, 3: True}
    assert timeline.audio == {1: False, 2: True}


def test_restore_track_states_raises_if_set_fails():
    timeline = _FakeTimeline()
    snapshot = snapshot_track_states(timeline)
    timeline.fail_on_set.add(("video", 1))
    with pytest.raises(TrackStateError, match="Failed restoring track states"):
        restore_track_states(timeline, snapshot)


def test_set_video_tracks_with_upper_layers_disabled():
    timeline = _FakeTimeline()
    set_video_tracks_with_upper_layers_disabled(timeline, total_video_tracks=3, target_video_track=2)
    assert timeline.video == {1: True, 2: True, 3: False}
