# resolve-clip-exporter

Python CLI for exporting selected DaVinci Resolve timeline clips to individual H.264 MP4 files with audio.

This README is the handoff/state file for future sessions.

## Requirements

- Python 3.9+
- DaVinci Resolve running with a project and timeline open
- Resolve scripting enabled
- Environment variables configured:
  - `RESOLVE_SCRIPT_API=/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting`
  - `RESOLVE_SCRIPT_LIB=/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so`
  - `PYTHONPATH` includes `$RESOLVE_SCRIPT_API/Modules`

## Usage

```bash
.venv/bin/python app.py \
  --output-dir /Volumes/Leverett/Downloads/test_video_clips \
  --max-clips 3 \
  --selection-mode first-per-track \
  --top-track-is highest-index \
  --format MP4 \
  --codec H264 \
  --timeout-seconds 600
```

### Dry run

```bash
.venv/bin/python app.py --dry-run
```

### Selection modes

- `first-per-track`: first clip by start frame on each video track
- `at-timeline-start`: first clip whose start frame exactly matches timeline start frame

### Layer peel direction

- `--top-track-is lowest-index`: treat smaller track numbers as higher layers
- `--top-track-is highest-index`: treat larger track numbers as higher layers

## Behavior notes

- Fails if fewer than `--max-clips` eligible clips are found.
- Uses only jobs created by this script.
- Restores video/audio track enable state in `finally`.
- Best-effort restores Resolve page after export.
- Writes JSON summary to stdout and `output_dir/export_summary.json`.

## Current state (2026-03-19)

- Core app and tests are implemented and passing.
- Default layer peel direction is top-to-bottom (`--top-track-is highest-index`).
- Latest validated run order was:
  - `03_C0060_MP4`
  - `02_C0061_MP4`
  - `01_C0063_MP4`
- Latest validated enabled-track masks were:
  - first render: `[1, 2, 3]`
  - second render: `[1, 2]`
  - third render: `[1]`
- Latest output folder in active use:
  - `/Volumes/Leverett/Downloads/test_video_clips`

## Important implementation decisions

- Isolation is done by cumulative per-render masking of video tracks.
- Isolation also applies clip-level enable/disable masking for timeline items on non-target tracks, then restores clip states in `finally`.
- The "move clips out of range" strategy is intentionally not used because the public Resolve scripting API does not expose timeline position as a supported writable TimelineItem property.

## Operational notes for future sessions

- In Codex sandboxed runs, Resolve scripting socket access can fail even when Resolve is running.
- If `scriptapp("Resolve")` returns `None` from sandbox, rerun the command with escalated permissions.
- Keep these env vars set for external Python runs:
  - `RESOLVE_SCRIPT_API`
  - `RESOLVE_SCRIPT_LIB`
  - `PYTHONPATH` with `$RESOLVE_SCRIPT_API/Modules`

## Testing

```bash
.venv/bin/python -m pytest -q
```

Manual integration helper:

```bash
.venv/bin/python tests/integration_manual.py --output-dir /Volumes/Leverett/Downloads/test_video_clips
```

## Resume checklist

1. Run dry run and inspect clip plan:
   - `.venv/bin/python app.py --dry-run --selection-mode at-timeline-start`
2. Run full export:
   - `.venv/bin/python app.py --output-dir /Volumes/Leverett/Downloads/test_video_clips --selection-mode at-timeline-start`
3. Check summary:
   - `/Volumes/Leverett/Downloads/test_video_clips/export_summary.json`
4. Confirm masks/order from log lines (`enabled_video_tracks=...`) if behavior is in doubt.
