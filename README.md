# resolve-clip-exporter

**Exports each layer of a stacked DaVinci Resolve timeline to its own MP4, automatically.**

When footage is stacked across several video tracks, Resolve has no one-click way to render each layer by itself. This CLI drives Resolve's scripting API to do it. It finds one clip per track, then "peels" the stack top-down: for each render it turns tracks and clips on and off so only the target layer shows, queues a render job, waits for it, and moves on. Afterwards it puts the timeline back exactly as it was.

**Highlights**

- **Safe by construction.** Track and clip enable states are recorded up front and restored in a `finally` block, even if a render fails or times out. It only touches render jobs it created itself.
- **Works within API limits.** The public API can't move timeline items, so layers are isolated by masking tracks and clips cumulatively instead.
- **Plan before acting.** `--dry-run` prints the clip plan without rendering. Every run writes a JSON summary of what was rendered, with paths and per-clip results.
- **Tested without Resolve.** The Resolve API is behind a thin client, so selection, masking, state restore and render-config logic are unit-tested with fakes (`pytest`, 18 tests).

**Stack:** Python 3.9+ · DaVinci Resolve scripting API · pytest

## Applications at scale

- **Asset preparation for compositing and VFX.** Per-layer renders are the handoff format for motion-graphics and compositing pipelines. This removes a manual, error-prone step from every delivery.
- **Paired data for generative video.** An isolated layer alongside the full composite is the kind of aligned pair used to train and evaluate matting, layer-decomposition and inpainting models. This tool produces those pairs straight from real editing projects.
- **A building block for agents.** It's one deterministic, self-restoring operation with a dry-run mode and a JSON result, which is the shape an AI agent needs for a tool it can call unattended.

**What it demonstrates:** stateful automation with guaranteed cleanup, dependency inversion for testability, CLI and structured-output design.

## Requirements

- DaVinci Resolve running with a project and timeline open, and external scripting enabled
- Environment variables (macOS paths shown):
  - `RESOLVE_SCRIPT_API=/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting`
  - `RESOLVE_SCRIPT_LIB=/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so`
  - `PYTHONPATH` includes `$RESOLVE_SCRIPT_API/Modules`

## Usage

```bash
python app.py \
  --output-dir ./exports \
  --max-clips 3 \
  --selection-mode first-per-track \
  --top-track-is highest-index \
  --format MP4 \
  --codec H264 \
  --timeout-seconds 600
```

Preview the plan without rendering:

```bash
python app.py --dry-run
```

| Option | Meaning |
|---|---|
| `--selection-mode first-per-track` | First clip (by start frame) on each video track |
| `--selection-mode at-timeline-start` | Clips that start exactly at the timeline start |
| `--top-track-is highest-index` | Higher track numbers are upper layers (default) |
| `--top-track-is lowest-index` | Lower track numbers are upper layers |
| `--json-logs` | Structured JSON log output |

## Behavior

- Fails early if fewer than `--max-clips` eligible clips are found.
- Renders layers top to bottom, with cumulative masks. For three tracks: `[1,2,3]`, then `[1,2]`, then `[1]`.
- Restores video and audio track states, clip states, and (best effort) the Resolve page you were on.
- Writes a JSON summary to stdout and to `<output-dir>/export_summary.json`.

## Code layout

| File | Responsibility |
|---|---|
| `app.py` | CLI, logging, summary output |
| `resolve_client.py` | Connection to the Resolve scripting API |
| `timeline_reader.py` | Reads tracks and items and picks clips |
| `export_runner.py` | Masks layers, queues render jobs, waits with a timeout |
| `state_restore.py` | Snapshots and restores track and clip enable state |
| `render_config.py`, `models.py` | Render settings and typed results |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

`tests/integration_manual.py --output-dir ./exports` runs an end-to-end check against a live Resolve session.

Note: if `scriptapp("Resolve")` returns `None` inside a sandboxed shell, the sandbox is blocking the local Resolve scripting socket. Run it from a normal terminal.
