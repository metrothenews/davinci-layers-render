from __future__ import annotations

from pathlib import Path

from export_runner import run_export_jobs
from models import ClipSpec


class _FakeTimeline:
    def __init__(self):
        self.video = {1: True, 2: False, 3: True}
        self.audio = {1: False, 2: True}
        self.video_snapshots_at_render_start = []

    def GetTrackCount(self, media_type):
        return len(self.video) if media_type == "video" else len(self.audio)

    def GetIsTrackEnabled(self, media_type, track_index):
        source = self.video if media_type == "video" else self.audio
        return source[track_index]

    def SetTrackEnable(self, media_type, track_index, enabled):
        source = self.video if media_type == "video" else self.audio
        source[track_index] = bool(enabled)
        return True


class _FakeResolve:
    def __init__(self):
        self.current_page = "edit"
        self.opened_pages = []

    def GetCurrentPage(self):
        return self.current_page

    def OpenPage(self, page):
        self.current_page = page
        self.opened_pages.append(page)
        return True


class _SuccessProject:
    def __init__(self, timeline):
        self.next_job = 1
        self.progress_ticks = 0
        self.active_job = None
        self.timeline = timeline

    def SetCurrentRenderFormatAndCodec(self, render_format, codec):
        return render_format == "MP4" and codec == "H264"

    def SetCurrentRenderMode(self, mode):
        return mode == 1

    def SetRenderSettings(self, _settings):
        return True

    def AddRenderJob(self):
        job_id = str(self.next_job)
        self.next_job += 1
        return job_id

    def StartRendering(self, job_ids, _interactive):
        self.active_job = job_ids[0]
        self.timeline.video_snapshots_at_render_start.append(dict(self.timeline.video))
        self.progress_ticks = 1
        return True

    def IsRenderingInProgress(self):
        if self.progress_ticks > 0:
            self.progress_ticks -= 1
            return True
        return False

    def GetRenderJobStatus(self, _job_id):
        return {"JobStatus": "Complete", "CompletionPercentage": 100}


class _TimeoutProject(_SuccessProject):
    def StartRendering(self, job_ids, _interactive):
        self.active_job = job_ids[0]
        return True

    def IsRenderingInProgress(self):
        return True

    def StopRendering(self):
        return True


def _sample_clips():
    return [
        ClipSpec(
            track_index=1,
            source_name="clip1",
            sanitized_name="clip1",
            custom_name="01_clip1",
            start_frame=100,
            end_frame=120,
            duration_frames=20,
            output_path="/tmp/out/01_clip1.mp4",
        ),
        ClipSpec(
            track_index=2,
            source_name="clip2",
            sanitized_name="clip2",
            custom_name="02_clip2",
            start_frame=100,
            end_frame=130,
            duration_frames=30,
            output_path="/tmp/out/02_clip2.mp4",
        ),
        ClipSpec(
            track_index=3,
            source_name="clip3",
            sanitized_name="clip3",
            custom_name="03_clip3",
            start_frame=100,
            end_frame=130,
            duration_frames=30,
            output_path="/tmp/out/03_clip3.mp4",
        ),
    ]


def test_run_export_jobs_success_restores_state_and_page():
    resolve = _FakeResolve()
    timeline = _FakeTimeline()
    project = _SuccessProject(timeline)
    initial_video = dict(timeline.video)
    initial_audio = dict(timeline.audio)

    results, warnings = run_export_jobs(
        resolve=resolve,
        project=project,
        timeline=timeline,
        clips=_sample_clips(),
        output_dir=Path("/tmp/out"),
        render_format="MP4",
        codec="H264",
        timeout_seconds=10,
        poll_seconds=0.0,
    )

    assert len(results) == 3
    assert all(result.success for result in results)
    assert warnings == []
    assert [result.clip_name for result in results] == ["01_clip1", "02_clip2", "03_clip3"]
    assert timeline.video_snapshots_at_render_start == [
        {1: True, 2: True, 3: True},
        {1: False, 2: True, 3: True},
        {1: False, 2: False, 3: True},
    ]
    assert timeline.video == initial_video
    assert timeline.audio == initial_audio
    assert "deliver" in resolve.opened_pages
    assert resolve.current_page == "edit"


def test_run_export_jobs_timeout_marks_failed_clip():
    resolve = _FakeResolve()
    timeline = _FakeTimeline()
    project = _TimeoutProject(timeline)
    clips = _sample_clips()[:1]

    results, warnings = run_export_jobs(
        resolve=resolve,
        project=project,
        timeline=timeline,
        clips=clips,
        output_dir=Path("/tmp/out"),
        render_format="MP4",
        codec="H264",
        timeout_seconds=0,
        poll_seconds=0.0,
    )

    assert len(results) == 1
    assert not results[0].success
    assert results[0].status == "Timeout"
    assert "timed out" in results[0].error
    assert warnings == []


def test_run_export_jobs_highest_index_top_order():
    resolve = _FakeResolve()
    timeline = _FakeTimeline()
    project = _SuccessProject(timeline)

    results, _warnings = run_export_jobs(
        resolve=resolve,
        project=project,
        timeline=timeline,
        clips=_sample_clips(),
        output_dir=Path("/tmp/out"),
        render_format="MP4",
        codec="H264",
        top_track_is="highest-index",
        timeout_seconds=10,
        poll_seconds=0.0,
    )

    assert [result.clip_name for result in results] == ["03_clip3", "02_clip2", "01_clip1"]
    assert timeline.video_snapshots_at_render_start == [
        {1: True, 2: True, 3: True},
        {1: True, 2: True, 3: False},
        {1: True, 2: False, 3: False},
    ]
