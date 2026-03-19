from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List

from export_runner import run_export_jobs
from logging_utils import configure_logger
from models import RunSummary
from resolve_client import ResolveConnectionError, connect_to_resolve
from timeline_reader import VALID_SELECTION_MODES, TimelineReadError, build_clip_plan

DEFAULT_OUTPUT_DIR = "/Volumes/Leverett/Downloads/test_video_clips"
DEFAULT_MAX_CLIPS = 3
DEFAULT_FORMAT = "MP4"
DEFAULT_CODEC = "H264"
DEFAULT_TIMEOUT_SECONDS = 600
ASSUMED_START_TIMECODE = "01:00:00:00"


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export selected timeline clips from DaVinci Resolve.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory to write exported files and summary.")
    parser.add_argument("--max-clips", type=int, default=DEFAULT_MAX_CLIPS, help="Required minimum clips and export count.")
    parser.add_argument(
        "--selection-mode",
        choices=VALID_SELECTION_MODES,
        default=VALID_SELECTION_MODES[0],
        help="Clip selection strategy per video track.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print export plan only; do not render.")
    parser.add_argument("--format", default=DEFAULT_FORMAT, help="Render container format key (default: MP4).")
    parser.add_argument("--codec", default=DEFAULT_CODEC, help="Render codec key (default: H264).")
    parser.add_argument(
        "--top-track-is",
        choices=["lowest-index", "highest-index"],
        default="highest-index",
        help="Track index direction for visual stacking. Determines layer-peel order.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-job timeout before marking render as failed.",
    )
    parser.add_argument("--json-logs", action="store_true", help="Emit structured JSON logs.")
    return parser.parse_args(argv)


def _write_summary(summary: RunSummary, output_dir: Path) -> None:
    serialized = json.dumps(summary.to_dict(), indent=2, sort_keys=False)
    print(serialized)
    summary_path = output_dir / "export_summary.json"
    summary_path.write_text(serialized + "\n", encoding="utf-8")


def _collect_existing_outputs(summary: RunSummary) -> List[str]:
    files = []
    for clip in summary.clip_plan:
        path = Path(clip.output_path)
        if path.exists():
            files.append(str(path))
    return files


def _run(args: argparse.Namespace, logger: logging.Logger) -> int:
    warnings: List[str] = []
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    context = connect_to_resolve()
    project_name = str(context.project.GetName() or "")
    metadata, clips = build_clip_plan(
        timeline=context.timeline,
        output_dir=output_dir,
        selection_mode=args.selection_mode,
        max_clips=args.max_clips,
        container_format=args.format,
    )

    if metadata.start_timecode != ASSUMED_START_TIMECODE:
        mismatch_warning = (
            "Timeline start timecode mismatch. "
            f"expected={ASSUMED_START_TIMECODE} detected={metadata.start_timecode}. "
            "Continuing with Resolve-reported frame values."
        )
        warnings.append(mismatch_warning)
        logger.warning(mismatch_warning)

    if args.dry_run:
        summary = RunSummary(
            project=project_name,
            timeline=metadata.name,
            detected_start_timecode=metadata.start_timecode,
            detected_start_frame=metadata.start_frame,
            assumed_start_timecode=ASSUMED_START_TIMECODE,
            render_format=args.format,
            render_codec=args.codec,
            output_dir=str(output_dir),
            selection_mode=args.selection_mode,
            top_track_is=args.top_track_is,
            max_clips=args.max_clips,
            dry_run=True,
            clip_plan=clips,
            job_results=[],
            created_files=[],
            warnings=warnings,
            overall_success=True,
        )
        _write_summary(summary, output_dir)
        return 0

    try:
        job_results, runtime_warnings = run_export_jobs(
            resolve=context.resolve,
            project=context.project,
            timeline=context.timeline,
            clips=clips,
            output_dir=output_dir,
            render_format=args.format,
            codec=args.codec,
            top_track_is=args.top_track_is,
            timeout_seconds=args.timeout_seconds,
            logger=logger,
        )
        warnings.extend(runtime_warnings)
    except Exception as exc:
        warnings.append(str(exc))
        job_results = []
        logger.error(str(exc))

    success = bool(job_results) and all(result.success for result in job_results)

    summary = RunSummary(
        project=project_name,
        timeline=metadata.name,
        detected_start_timecode=metadata.start_timecode,
        detected_start_frame=metadata.start_frame,
        assumed_start_timecode=ASSUMED_START_TIMECODE,
        render_format=args.format,
        render_codec=args.codec,
        output_dir=str(output_dir),
        selection_mode=args.selection_mode,
        top_track_is=args.top_track_is,
        max_clips=args.max_clips,
        dry_run=False,
        clip_plan=clips,
        job_results=job_results,
        created_files=[],
        warnings=warnings,
        overall_success=success,
    )
    summary.created_files = _collect_existing_outputs(summary)
    _write_summary(summary, output_dir)
    return 0 if success else 1


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    logger = configure_logger(json_logs=args.json_logs)
    try:
        return _run(args, logger)
    except (ResolveConnectionError, TimelineReadError, RuntimeError, ValueError) as exc:
        logger.error(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
