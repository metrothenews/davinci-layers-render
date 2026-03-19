from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class TimelineMetadata:
    name: str
    start_timecode: str
    start_frame: int
    video_track_count: int
    audio_track_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClipSpec:
    track_index: int
    source_name: str
    sanitized_name: str
    custom_name: str
    start_frame: int
    end_frame: int
    duration_frames: int
    output_path: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RenderJobResult:
    job_id: str
    clip_name: str
    status: str
    progress: int
    elapsed_seconds: float
    output_file: str
    success: bool
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrackStateSnapshot:
    video_states: Dict[int, bool]
    audio_states: Dict[int, bool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_states": dict(self.video_states),
            "audio_states": dict(self.audio_states),
        }


@dataclass
class RunSummary:
    project: str
    timeline: str
    detected_start_timecode: str
    detected_start_frame: int
    assumed_start_timecode: str
    render_format: str
    render_codec: str
    output_dir: str
    selection_mode: str
    top_track_is: str
    max_clips: int
    dry_run: bool
    clip_plan: List[ClipSpec] = field(default_factory=list)
    job_results: List[RenderJobResult] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    overall_success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": self.project,
            "timeline": self.timeline,
            "detected_start_timecode": self.detected_start_timecode,
            "detected_start_frame": self.detected_start_frame,
            "assumed_start_timecode": self.assumed_start_timecode,
            "render_format": self.render_format,
            "render_codec": self.render_codec,
            "output_dir": self.output_dir,
            "selection_mode": self.selection_mode,
            "top_track_is": self.top_track_is,
            "max_clips": self.max_clips,
            "dry_run": self.dry_run,
            "clip_plan": [clip.to_dict() for clip in self.clip_plan],
            "job_results": [job.to_dict() for job in self.job_results],
            "created_files": list(self.created_files),
            "warnings": list(self.warnings),
            "overall_success": self.overall_success,
        }
