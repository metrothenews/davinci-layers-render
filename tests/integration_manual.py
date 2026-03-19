from __future__ import annotations

import argparse
import json
from pathlib import Path

import app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual integration helper for resolve-clip-exporter.")
    parser.add_argument("--output-dir", default="/Volumes/Leverett/Downloads/test_video_clips")
    parser.add_argument("--max-clips", type=int, default=3)
    parser.add_argument(
        "--selection-mode",
        default="first-per-track",
        choices=["first-per-track", "at-timeline-start"],
    )
    parser.add_argument(
        "--top-track-is",
        default="highest-index",
        choices=["lowest-index", "highest-index"],
    )
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--expected-clips", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _validate_summary(summary_path: Path, expected_clips: int, dry_run: bool) -> bool:
    if not summary_path.exists():
        print("validation_error=missing export_summary.json")
        return False
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    if dry_run:
        return bool(payload.get("dry_run"))

    jobs = payload.get("job_results", [])
    if len(jobs) != expected_clips:
        print(f"validation_error=expected {expected_clips} jobs, found {len(jobs)}")
        return False
    for job in jobs:
        status = str(job.get("status", ""))
        progress = int(job.get("progress", 0))
        if "complete" not in status.lower() or progress < 100:
            print(f"validation_error=incomplete job status={status!r} progress={progress}")
            return False
    return True


def main() -> int:
    args = parse_args()
    argv = [
        "--output-dir",
        args.output_dir,
        "--max-clips",
        str(args.max_clips),
        "--selection-mode",
        args.selection_mode,
        "--top-track-is",
        args.top_track_is,
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.dry_run:
        argv.append("--dry-run")

    exit_code = app.main(argv)
    output_dir = Path(args.output_dir)
    mp4_files = sorted(output_dir.glob("*.mp4"))
    summary_file = output_dir / "export_summary.json"
    summary_ok = _validate_summary(summary_file, args.expected_clips, args.dry_run)
    files_ok = args.dry_run or len(mp4_files) >= args.expected_clips

    print(f"exit_code={exit_code}")
    print(f"output_dir={output_dir}")
    print(f"mp4_count={len(mp4_files)}")
    for file in mp4_files:
        print(f"file={file}")
    print(f"summary_file_exists={summary_file.exists()}")
    print(f"summary_validation={summary_ok}")
    print(f"files_validation={files_ok}")

    if exit_code != 0:
        return exit_code
    return 0 if summary_ok and files_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
