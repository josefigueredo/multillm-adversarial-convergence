"""Orchestrator loop wiring + audit events.

TDD tests written before implementation.

Contract:
  scope=run:       _setup() calls prepare_workspace() once; workspace_dir stable across iterations
  scope=iteration: _setup() skips prepare_workspace(); before each iteration N,
                   prepare_workspace(iteration=N) is called; workspace_dir changes each iteration;
                   audit event "sandbox_workspace_prepared" emitted with iteration, workspace_dir, scope
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from src.config import (
    ContainerBackendConfig,
    ExecutionConfig,
    ResearchConfig,
    SandboxConfig,
    ScoringConfig,
    SecurityConfig,
)


# ---------------------------------------------------------------------------
# In-memory audit trail for capturing events
# ---------------------------------------------------------------------------

class CapturingAuditTrail:
    """Records emitted events for assertion."""

    def __init__(self):
        self.events: list[dict] = []

    def emit(self, event: str, **fields) -> None:
        self.events.append({"event": event, **fields})

    def events_named(self, name: str) -> list[dict]:
        return [e for e in self.events if e["event"] == name]

    class _Step:
        def __init__(self, trail, name):
            self._trail = trail
            self._name = name

        def __enter__(self): return self
        def __exit__(self, *_): pass

    def step(self, step_name: str, *, artifact_root=None, **fields):
        return self._Step(self, step_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SETUP_PATCHES = (
    patch("src.orchestrator.git_commit", return_value="abc123"),
    patch("src.orchestrator.cli_version", return_value="1.0"),
    patch("src.orchestrator.package_version", return_value="0.2.0"),
)


def _apply_setup_patches():
    return (
        _SETUP_PATCHES[0],
        _SETUP_PATCHES[1],
        _SETUP_PATCHES[2],
    )


def _make_config(scope: str = "run", *, sandboxed: bool = False) -> ResearchConfig:
    sandbox = SandboxConfig(
        scope=scope,
        mode="tool_calls" if sandboxed else "off",
    )
    return ResearchConfig(
        topic="T",
        goal="G",
        dimensions=("A",),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(max_iterations=2, backend="claude-cli", timeout_seconds=5),
        security=SecurityConfig(
            tool_execution_mode="sandboxed" if sandboxed else "direct",
            sandbox=sandbox,
        ),
    )


def _make_researcher(config: ResearchConfig, tmp_path: Path):
    from tests.test_orchestrator import FakeBackend
    from src.orchestrator import AutoResearcher
    return AutoResearcher(config=config, backend=FakeBackend(), output_dir=tmp_path / "output")


def _run_setup(researcher) -> None:
    p0, p1, p2 = _apply_setup_patches()
    with p0, p1, p2:
        researcher._setup()


# ---------------------------------------------------------------------------
# scope=run: _setup() calls prepare_workspace() once; stable across iterations
# ---------------------------------------------------------------------------

class TestScopeRunSetupBehavior:
    def test_run_scope_prepares_workspace_in_setup(self, tmp_path):
        """Scope=run → _setup() creates workspace dir."""
        researcher = _make_researcher(_make_config(scope="run"), tmp_path)
        _run_setup(researcher)
        assert researcher._sandbox is not None
        assert researcher._sandbox.workspace_dir.exists()

    def test_run_scope_workspace_stable_across_run_iterations(self, tmp_path):
        """Scope=run → workspace_dir stays the same across multiple _run_iteration calls."""
        researcher = _make_researcher(_make_config(scope="run"), tmp_path)
        _run_setup(researcher)
        ws_before = researcher._sandbox.workspace_dir

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            ws_after_1 = researcher._sandbox.workspace_dir
            researcher._run_iteration()
            ws_after_2 = researcher._sandbox.workspace_dir

        assert ws_before == ws_after_1 == ws_after_2

    def test_run_scope_prepare_not_called_per_iteration(self, tmp_path):
        """Scope=run → prepare_workspace is NOT called again inside _run_iteration."""
        researcher = _make_researcher(_make_config(scope="run"), tmp_path)
        _run_setup(researcher)

        with patch.object(researcher._sandbox, "prepare_workspace") as mock_prep, \
             patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        mock_prep.assert_not_called()


# ---------------------------------------------------------------------------
# scope=iteration: _setup() skips prepare_workspace(); prepared per-iteration
# ---------------------------------------------------------------------------

class TestScopeIterationSetupBehavior:
    def test_iteration_scope_skips_workspace_in_setup(self, tmp_path):
        """Scope=iteration (active sandbox) → _setup() does NOT create the workspace dir."""
        researcher = _make_researcher(_make_config(scope="iteration", sandboxed=True), tmp_path)
        _run_setup(researcher)
        assert researcher._sandbox is not None
        # Base workspace dir should NOT exist yet (no prepare_workspace called)
        assert not researcher._sandbox.workspace_dir.exists()

    def test_iteration_scope_workspace_prepared_before_iter1(self, tmp_path):
        """Scope=iteration → prepare_workspace(iteration=1) called before iteration 1."""
        researcher = _make_researcher(_make_config(scope="iteration", sandboxed=True), tmp_path)
        _run_setup(researcher)

        with patch.object(researcher._sandbox, "prepare_workspace") as mock_prep, \
             patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()

        mock_prep.assert_called_once_with(iteration=1)

    def test_iteration_scope_workspace_prepared_before_iter2(self, tmp_path):
        """Scope=iteration → prepare_workspace(iteration=2) called before iteration 2."""
        researcher = _make_researcher(_make_config(scope="iteration", sandboxed=True), tmp_path)
        _run_setup(researcher)

        with patch.object(researcher._sandbox, "prepare_workspace") as mock_prep, \
             patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()   # iter 1
            researcher._run_iteration()   # iter 2

        assert mock_prep.call_count == 2
        mock_prep.assert_any_call(iteration=1)
        mock_prep.assert_any_call(iteration=2)

    def test_iteration_scope_workspace_dir_changes_between_iterations(self, tmp_path):
        """Scope=iteration → workspace_dir updates to iter_0001, iter_0002 path."""
        researcher = _make_researcher(_make_config(scope="iteration", sandboxed=True), tmp_path)
        _run_setup(researcher)

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            ws1 = researcher._sandbox.workspace_dir
            researcher._run_iteration()
            ws2 = researcher._sandbox.workspace_dir

        assert "iter_0001" in str(ws1)
        assert "iter_0002" in str(ws2)
        assert ws1 != ws2

    def test_iteration_scope_iter_dirs_created_on_disk(self, tmp_path):
        """Scope=iteration → iter_0001/ and iter_0002/ dirs exist after two iterations."""
        researcher = _make_researcher(_make_config(scope="iteration", sandboxed=True), tmp_path)
        _run_setup(researcher)

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        base_ws = tmp_path / "output" / ".workspace"
        assert (base_ws / "iter_0001").is_dir()
        assert (base_ws / "iter_0002").is_dir()


# ---------------------------------------------------------------------------
# Audit events: sandbox_workspace_prepared
# ---------------------------------------------------------------------------

class TestSandboxWorkspacePreparedAuditEvent:
    def _make_researcher_with_capturing_trail(self, tmp_path: Path, scope: str = "iteration"):
        researcher = _make_researcher(_make_config(scope=scope, sandboxed=(scope == "iteration")), tmp_path)
        _run_setup(researcher)  # runs first, _sync_paths() inside recreates _audit_trail
        trail = CapturingAuditTrail()
        researcher._audit_trail = trail  # inject AFTER setup so _sync_paths can't overwrite
        return researcher, trail

    def test_audit_event_emitted_per_iteration(self, tmp_path):
        """Scope=iteration → sandbox_workspace_prepared emitted for each iteration."""
        researcher, trail = self._make_researcher_with_capturing_trail(tmp_path, scope="iteration")

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        events = trail.events_named("sandbox_workspace_prepared")
        assert len(events) == 2

    def test_audit_event_has_correct_iteration_field(self, tmp_path):
        """Sandbox_workspace_prepared event has correct iteration number."""
        researcher, trail = self._make_researcher_with_capturing_trail(tmp_path, scope="iteration")

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        events = trail.events_named("sandbox_workspace_prepared")
        assert events[0]["iteration"] == 1
        assert events[1]["iteration"] == 2

    def test_audit_event_has_workspace_dir_field(self, tmp_path):
        """Sandbox_workspace_prepared event contains workspace_dir."""
        researcher, trail = self._make_researcher_with_capturing_trail(tmp_path, scope="iteration")

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()

        events = trail.events_named("sandbox_workspace_prepared")
        assert "workspace_dir" in events[0]
        assert "iter_0001" in events[0]["workspace_dir"]

    def test_audit_event_has_scope_field(self, tmp_path):
        """Sandbox_workspace_prepared event contains scope=iteration."""
        researcher, trail = self._make_researcher_with_capturing_trail(tmp_path, scope="iteration")

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()

        events = trail.events_named("sandbox_workspace_prepared")
        assert events[0]["scope"] == "iteration"

    def test_no_audit_event_for_scope_run(self, tmp_path):
        """Scope=run → no sandbox_workspace_prepared events emitted."""
        researcher, trail = self._make_researcher_with_capturing_trail(tmp_path, scope="run")

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        events = trail.events_named("sandbox_workspace_prepared")
        assert len(events) == 0


# ---------------------------------------------------------------------------
# Direct-mode with scope=iteration: no workspace creation, no audit events
# ---------------------------------------------------------------------------

class TestDirectModeWithIterationScope:
    """When sandbox is not active, scope=iteration must not trigger workspace or events."""

    def _make_direct_config(self) -> ResearchConfig:
        """Config with scope=iteration but tool_execution_mode=direct (sandbox inactive)."""
        sandbox = SandboxConfig(scope="iteration")  # scope set, but mode is direct
        return ResearchConfig(
            topic="T",
            goal="G",
            dimensions=("A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(max_iterations=2, backend="claude-cli", timeout_seconds=5),
            security=SecurityConfig(
                tool_execution_mode="direct",   # sandbox NOT active
                sandbox=sandbox,
            ),
        )

    def test_direct_mode_no_iteration_workspace_created(self, tmp_path):
        """Scope=iteration + direct mode → no iter_* dirs created during _run_iteration."""
        from tests.test_orchestrator import FakeBackend
        from src.orchestrator import AutoResearcher
        researcher = AutoResearcher(
            config=self._make_direct_config(),
            backend=FakeBackend(),
            output_dir=tmp_path / "output",
        )
        _run_setup(researcher)

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        base_ws = tmp_path / "output" / ".workspace"
        assert not (base_ws / "iter_0001").exists()
        assert not (base_ws / "iter_0002").exists()

    def test_direct_mode_no_sandbox_workspace_prepared_event(self, tmp_path):
        """Scope=iteration + direct mode → no sandbox_workspace_prepared audit events."""
        from tests.test_orchestrator import FakeBackend
        from src.orchestrator import AutoResearcher
        researcher = AutoResearcher(
            config=self._make_direct_config(),
            backend=FakeBackend(),
            output_dir=tmp_path / "output",
        )
        _run_setup(researcher)
        trail = CapturingAuditTrail()
        researcher._audit_trail = trail  # inject after setup

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        assert len(trail.events_named("sandbox_workspace_prepared")) == 0

    def test_active_sandbox_iteration_scope_still_prepares(self, tmp_path):
        """Active sandbox + scope=iteration still creates iteration workspaces (regression guard)."""
        from tests.test_orchestrator import FakeBackend
        from src.orchestrator import AutoResearcher
        from src.config import SandboxConfig, SecurityConfig
        sandbox = SandboxConfig(scope="iteration", mode="tool_calls")
        config = ResearchConfig(
            topic="T",
            goal="G",
            dimensions=("A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(max_iterations=2, backend="claude-cli", timeout_seconds=5),
            security=SecurityConfig(
                tool_execution_mode="sandboxed",
                sandbox=sandbox,
            ),
        )
        researcher = AutoResearcher(config=config, backend=FakeBackend(), output_dir=tmp_path / "output")
        _run_setup(researcher)

        with patch("src.research_loop.run_iteration") as mock_iter:
            mock_iter.side_effect = lambda ctx, state: setattr(state, "iteration", state.iteration + 1)
            researcher._run_iteration()
            researcher._run_iteration()

        base_ws = tmp_path / "output" / ".workspace"
        assert (base_ws / "iter_0001").is_dir()
        assert (base_ws / "iter_0002").is_dir()
