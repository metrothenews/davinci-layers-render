from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from typing import Any


class ResolveConnectionError(RuntimeError):
    pass


@dataclass
class ResolveContext:
    resolve: Any
    project_manager: Any
    project: Any
    timeline: Any


def _maybe_add_resolve_modules_path() -> None:
    script_api_root = os.getenv("RESOLVE_SCRIPT_API", "").strip()
    if not script_api_root:
        return
    modules_path = os.path.join(script_api_root, "Modules")
    if modules_path and modules_path not in sys.path:
        sys.path.append(modules_path)


def load_resolve_module() -> Any:
    _maybe_add_resolve_modules_path()
    try:
        return importlib.import_module("DaVinciResolveScript")
    except ModuleNotFoundError as exc:
        script_api_root = os.getenv("RESOLVE_SCRIPT_API", "")
        script_lib = os.getenv("RESOLVE_SCRIPT_LIB", "")
        raise ResolveConnectionError(
            "import DaVinciResolveScript failed. "
            "Verify RESOLVE_SCRIPT_API and RESOLVE_SCRIPT_LIB are set and "
            "PYTHONPATH includes $RESOLVE_SCRIPT_API/Modules. "
            f"RESOLVE_SCRIPT_API={script_api_root!r} RESOLVE_SCRIPT_LIB={script_lib!r}"
        ) from exc


def _require_callable(target: Any, method_name: str) -> Any:
    method = getattr(target, method_name, None)
    if not callable(method):
        raise ResolveConnectionError(f"{method_name} is unavailable on Resolve scripting object.")
    return method


def connect_to_resolve() -> ResolveContext:
    module = load_resolve_module()
    scriptapp = getattr(module, "scriptapp", None)
    if not callable(scriptapp):
        raise ResolveConnectionError("DaVinciResolveScript.scriptapp is unavailable.")

    resolve = scriptapp("Resolve")
    if resolve is None:
        raise ResolveConnectionError(
            "scriptapp('Resolve') returned None. Ensure Resolve is running and scripting is enabled."
        )

    get_project_manager = _require_callable(resolve, "GetProjectManager")
    project_manager = get_project_manager()
    if project_manager is None:
        raise ResolveConnectionError("GetProjectManager() returned None.")

    get_current_project = _require_callable(project_manager, "GetCurrentProject")
    project = get_current_project()
    if project is None:
        raise ResolveConnectionError("GetCurrentProject() returned None. Open a project in Resolve.")

    get_current_timeline = _require_callable(project, "GetCurrentTimeline")
    timeline = get_current_timeline()
    if timeline is None:
        raise ResolveConnectionError("GetCurrentTimeline() returned None. Open a timeline in Resolve.")

    return ResolveContext(
        resolve=resolve,
        project_manager=project_manager,
        project=project,
        timeline=timeline,
    )
