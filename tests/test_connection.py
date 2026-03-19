from __future__ import annotations

import types

import pytest

import resolve_client


class _FakeProject:
    def __init__(self, timeline):
        self._timeline = timeline

    def GetCurrentTimeline(self):
        return self._timeline


class _FakeProjectManager:
    def __init__(self, project):
        self._project = project

    def GetCurrentProject(self):
        return self._project


class _FakeResolve:
    def __init__(self, project_manager):
        self._project_manager = project_manager

    def GetProjectManager(self):
        return self._project_manager


def test_load_resolve_module_missing(monkeypatch):
    def _raise(_name):
        raise ModuleNotFoundError("No module named DaVinciResolveScript")

    monkeypatch.setattr(resolve_client.importlib, "import_module", _raise)
    with pytest.raises(resolve_client.ResolveConnectionError, match="import DaVinciResolveScript failed"):
        resolve_client.load_resolve_module()


def test_connect_to_resolve_scriptapp_missing(monkeypatch):
    module = types.SimpleNamespace()
    monkeypatch.setattr(resolve_client, "load_resolve_module", lambda: module)
    with pytest.raises(resolve_client.ResolveConnectionError, match="scriptapp is unavailable"):
        resolve_client.connect_to_resolve()


def test_connect_to_resolve_no_project(monkeypatch):
    resolve = _FakeResolve(_FakeProjectManager(None))
    module = types.SimpleNamespace(scriptapp=lambda name: resolve if name == "Resolve" else None)
    monkeypatch.setattr(resolve_client, "load_resolve_module", lambda: module)
    with pytest.raises(resolve_client.ResolveConnectionError, match="GetCurrentProject"):
        resolve_client.connect_to_resolve()


def test_connect_to_resolve_no_timeline(monkeypatch):
    project = _FakeProject(None)
    resolve = _FakeResolve(_FakeProjectManager(project))
    module = types.SimpleNamespace(scriptapp=lambda name: resolve if name == "Resolve" else None)
    monkeypatch.setattr(resolve_client, "load_resolve_module", lambda: module)
    with pytest.raises(resolve_client.ResolveConnectionError, match="GetCurrentTimeline"):
        resolve_client.connect_to_resolve()


def test_connect_to_resolve_success(monkeypatch):
    timeline = object()
    project = _FakeProject(timeline)
    pm = _FakeProjectManager(project)
    resolve = _FakeResolve(pm)
    module = types.SimpleNamespace(scriptapp=lambda name: resolve if name == "Resolve" else None)
    monkeypatch.setattr(resolve_client, "load_resolve_module", lambda: module)

    context = resolve_client.connect_to_resolve()
    assert context.resolve is resolve
    assert context.project_manager is pm
    assert context.project is project
    assert context.timeline is timeline
