"""Tests for PlanRefiner — plan convergence orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backends.types import AgentResponse, BackendCapabilities
from src.config import ArtifactConfig, BackendsConfig, ExecutionConfig, PlanConfig, ProviderConfig
from src.implement.plan_loop import PlanCycleState
from src.implement.plan_refiner import EXIT_HUMAN_REQUIRED, PlanRefiner


# ---------------------------------------------------------------------------
# Audit-trail helpers
# ---------------------------------------------------------------------------

def _read_audit_events(output_dir: Path) -> list[dict]:
    path = output_dir / "audit_trail.jsonl"
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def _workflow_transitions(output_dir: Path) -> list[dict]:
    return [e for e in _read_audit_events(output_dir) if e.get("event") == "workflow_transition"]


def _make_config(**kwargs) -> PlanConfig:
    defaults = dict(
        topic="Test Plan",
        goal="Test goal",
        primary_artifact="PLAN.md",
        convergence_cycles=1,
        max_cycles=5,
        backends=BackendsConfig(primary="claude-cli", research=["claude-cli", "gemini-cli"]),
        execution=ExecutionConfig(),
    )
    defaults.update(kwargs)
    return PlanConfig(**defaults)


def _make_backend(text: str = "# Generated Plan") -> MagicMock:
    backend = MagicMock()
    backend.invoke.return_value = AgentResponse(
        text=text, cost_usd=0.01, is_error=False,
        input_tokens=100, output_tokens=50,
    )
    return backend


def _make_backends(text: str = "# Generated Plan") -> dict:
    return {
        "claude-cli": _make_backend(text),
        "gemini-cli": _make_backend(text),
    }


def _converged_state() -> PlanCycleState:
    state = PlanCycleState(plan="# Plan\n\nContent.")
    state.consecutive_clean_cycles = 1
    state.cycle = 1
    return state


class TestPhase1Convergence:
    def test_run_returns_zero_on_success(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.implement.plan_refiner._plan_should_stop", side_effect=[False, True]),
        ):
            code = refiner.run(interactive=True)

        assert code == 0

    def test_primary_artifact_written_after_convergence(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.implement.plan_refiner.PlanStrategy") as mock_strat_cls,
            patch("src.implement.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.implement.plan_refiner._plan_should_stop", side_effect=[False, True]),
        ):
            mock_strat = mock_strat_cls.return_value
            mock_strat.run_builder.return_value = "# Final Plan"
            refiner._state = _converged_state()
            refiner._state.plan = "# Final Plan"
            refiner.run(interactive=True)

        plan_path = tmp_path / "PLAN.md"
        assert plan_path.exists()

    def test_run_returns_2_on_hitl_pause_non_interactive(self, tmp_path):
        from src.policy.hitl import HumanInputRequest
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        def _cycle_with_hitl(state, ctx, strategy, *, interactive):
            state.pending_human_inputs = [
                HumanInputRequest(
                    issue_id="I-01", question="Q?", context="Task 1",
                    suggested_answer="A", cycle=1,
                )
            ]
            return (0, 0, 1)

        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", side_effect=_cycle_with_hitl),
            patch("src.implement.plan_refiner._plan_should_stop", return_value=False),
        ):
            code = refiner.run(interactive=False)

        assert code == EXIT_HUMAN_REQUIRED

    def test_run_manifest_written(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.implement.plan_refiner._plan_should_stop", side_effect=[False, True]),
        ):
            refiner.run(interactive=True)

        manifest_path = tmp_path / ".run" / "run_manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["topic"] == "Test Plan"
        assert "cycles" in data
        assert "finished_at" in data


class TestPhase2Expansion:
    def test_phase2_writes_artifact(self, tmp_path):
        config = _make_config(
            artifacts=(ArtifactConfig(name="RISK_REGISTER.md", layer="companion", review=False),)
        )
        refiner = PlanRefiner(config, tmp_path, _make_backends("# Risk Register"))

        def _side_effect(prompt_file, **kwargs):
            if prompt_file in ("generate_readme.md", "generate_docs_index.md"):
                return "# Index"
            if prompt_file == "artifact_risk_register.md":
                raise FileNotFoundError(prompt_file)
            return "content"

        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.implement.plan_refiner._plan_should_stop", side_effect=[False, True]),
            patch("src.implement.plan_refiner.render", side_effect=_side_effect),
        ):
            refiner.run(interactive=True)

        artifact = tmp_path / "RISK_REGISTER.md"
        assert artifact.exists()


class TestPhase3Indexing:
    def test_phase3_writes_readme_and_docs_index(self, tmp_path):
        config = _make_config()
        refiner = PlanRefiner(config, tmp_path, _make_backends())

        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.implement.plan_refiner._plan_should_stop", side_effect=[False, True]),
            patch("src.implement.plan_refiner.render", return_value="# Generated"),
        ):
            refiner.run(interactive=True)

        assert (tmp_path / "README.md").exists()
        assert (tmp_path / "DOCS_INDEX.md").exists()


class TestBackendInvocation:
    def test_invoke_uses_configured_execution_options(self, tmp_path):
        config = _make_config(
            execution=ExecutionConfig(
                model="opus",
                allowed_tools="Read,Bash",
                max_turns=9,
                timeout_seconds=456,
            )
        )
        backend = _make_backend()
        refiner = PlanRefiner(config, tmp_path, {"claude-cli": backend, "gemini-cli": _make_backend()})

        resp = refiner._invoke("prompt", backend, "claude-cli")

        assert resp.text == "# Generated Plan"
        backend.invoke.assert_called_once()
        call_args = backend.invoke.call_args
        assert call_args.args[0] == "prompt"
        opts = call_args.args[1]
        assert opts.model == "opus"
        assert opts.allowed_tools == "Read,Bash"
        assert opts.max_turns == 9
        assert call_args.kwargs["timeout"] == 456

    def test_invoke_applies_provider_model_override(self, tmp_path):
        config = _make_config(
            execution=ExecutionConfig(model="sonnet", allowed_tools="Read", max_turns=9, timeout_seconds=456),
            providers={"planner_main": ProviderConfig(adapter="claude-cli", model="opus")},
            backends=BackendsConfig(primary="planner_main", research=["planner_main"]),
        )
        backend = _make_backend()
        backend.instance_name = "planner_main"
        backend.provider_config = config.providers["planner_main"]
        refiner = PlanRefiner(config, tmp_path, {"planner_main": backend})

        refiner._invoke("prompt", backend, "planner_main")

        opts = backend.invoke.call_args.args[1]
        assert opts.model == "opus"

    def test_invoke_strips_tools_for_backend_without_tool_support(self, tmp_path):
        config = _make_config(
            execution=ExecutionConfig(model="openai/gpt-4.1-mini", allowed_tools="Read,Bash", timeout_seconds=456),
        )
        backend = _make_backend()
        backend.capabilities = BackendCapabilities(
            transport="api",
            provider_kind="aggregator",
            supports_tools=False,
            default_model="openai/gpt-4.1-mini",
        )
        refiner = PlanRefiner(config, tmp_path, {"litellm-api": backend})

        refiner._invoke("prompt", backend, "litellm-api")

        opts = backend.invoke.call_args.args[1]
        assert opts.allowed_tools == ""



# ---------------------------------------------------------------------------
# Workflow terminal transitions
# ---------------------------------------------------------------------------

class TestPlanWorkflowTerminalTransitions:
    def test_converged_emitted_on_successful_run(self, tmp_path):
        refiner = PlanRefiner(_make_config(), tmp_path, _make_backends())
        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.implement.plan_refiner._plan_should_stop", side_effect=[False, True]),
        ):
            refiner.run(interactive=True)

        transitions = _workflow_transitions(tmp_path)
        assert any(t.get("to_state") == "converged" for t in transitions), (
            f"Expected 'converged' in workflow transitions, got: {[t.get('to_state') for t in transitions]}"
        )
        assert all(t.get("workflow") == "plan" for t in transitions)

    def test_interrupted_emitted_on_exception_during_phase1(self, tmp_path):
        refiner = PlanRefiner(_make_config(), tmp_path, _make_backends())
        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", side_effect=RuntimeError("backend crash")),
            patch("src.implement.plan_refiner._plan_should_stop", return_value=False),
            pytest.raises(RuntimeError),
        ):
            refiner.run(interactive=True)

        transitions = _workflow_transitions(tmp_path)
        assert any(t.get("to_state") == "interrupted" for t in transitions), (
            f"Expected 'interrupted' in workflow transitions, got: {[t.get('to_state') for t in transitions]}"
        )
        assert all(t.get("workflow") == "plan" for t in transitions)

    def test_interrupted_emitted_on_later_phase_failure(self, tmp_path):
        refiner = PlanRefiner(_make_config(), tmp_path, _make_backends())
        with (
            patch("src.implement.plan_refiner.PlanStrategy"),
            patch("src.implement.plan_refiner.run_plan_cycle", return_value=(0, 0, 0)),
            patch("src.implement.plan_refiner._plan_should_stop", side_effect=[False, True]),
            patch.object(refiner, "_run_phase2", side_effect=RuntimeError("phase2 crash")),
            pytest.raises(RuntimeError),
        ):
            refiner.run(interactive=True)

        transitions = _workflow_transitions(tmp_path)
        to_states = [t.get("to_state") for t in transitions]
        assert "interrupted" in to_states, f"Expected 'interrupted', got: {to_states}"
        assert "converged" not in to_states, f"'converged' must not appear when run crashed: {to_states}"
