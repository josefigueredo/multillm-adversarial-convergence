"""Unit tests for src.explain."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import (
    BackendsConfig,
    EvaluationConfig,
    ExecutionConfig,
    ReportingConfig,
    ResearchConfig,
    SandboxConfig,
    ScoringConfig,
    SecurityConfig,
)
from src.explain import explain_config_text


def _make_config(**kwargs) -> ResearchConfig:
    defaults = dict(
        topic="Compare API gateways",
        goal="Architect-level decision",
        dimensions=("REST vs HTTP", "Auth options"),
        evaluation=EvaluationConfig(),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            strategy="ensemble",
            backends=BackendsConfig(
                primary="claude-cli",
                research=["claude-cli", "codex-cli"],
            ),
        ),
        security=SecurityConfig(
            content_trust="permissive",
            tool_execution_mode="sandboxed",
            sandbox=SandboxConfig(
                mode="tool_calls",
                network_access="web_only",
            ),
        ),
    )
    defaults.update(kwargs)
    return ResearchConfig(**defaults)


class TestExplainConfigText:
    def test_returns_nonempty_string(self):
        result = explain_config_text(_make_config())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_topic_and_goal(self):
        result = explain_config_text(_make_config())
        assert "Compare API gateways" in result
        assert "Architect-level decision" in result

    def test_contains_dimensions(self):
        result = explain_config_text(_make_config())
        assert "REST vs HTTP" in result
        assert "Auth options" in result

    def test_contains_strategy(self):
        result = explain_config_text(_make_config())
        assert "ensemble" in result

    def test_contains_backend_role_mapping(self):
        result = explain_config_text(_make_config())
        assert "claude-cli" in result
        assert "codex-cli" in result

    def test_contains_security_policy_section(self):
        result = explain_config_text(_make_config())
        assert "SECURITY POLICY" in result

    def test_contains_content_trust(self):
        result = explain_config_text(_make_config())
        assert "permissive" in result

    def test_contains_tool_execution_mode(self):
        result = explain_config_text(_make_config())
        assert "sandboxed" in result

    def test_contains_sandbox_mode(self):
        result = explain_config_text(_make_config())
        assert "tool_calls" in result

    def test_contains_sandbox_network(self):
        result = explain_config_text(_make_config())
        assert "web_only" in result

    def test_contains_output_style(self):
        result = explain_config_text(
            _make_config(reporting=ReportingConfig(output_style="paper"))
        )
        assert "paper" in result

    def test_contains_artifacts_section(self):
        result = explain_config_text(_make_config())
        assert "ARTIFACTS" in result
        assert "effective_config" in result
        assert "manifest" in result

    def test_config_path_shown_when_provided(self, tmp_path: Path):
        cfg_path = tmp_path / "my_research.yaml"
        result = explain_config_text(_make_config(), config_path=cfg_path)
        assert "my_research" in result

    def test_no_dims_shows_none_configured(self):
        result = explain_config_text(_make_config(dimensions=()))
        assert "none configured" in result

    def test_providers_section_shown_when_present(self):
        cfg = _make_config()
        result = explain_config_text(cfg)
        if cfg.providers:
            assert "PROVIDERS" in result

    def test_does_not_create_output_dirs(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        explain_config_text(_make_config())
        assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------------------
# explain_resume_text
# ---------------------------------------------------------------------------

from src.explain import explain_resume_text  # noqa: E402


class TestExplainResumeText:
    def test_nonexistent_dir_returns_error_text(self, tmp_path: Path):
        result = explain_resume_text(tmp_path / "no-such-dir")
        assert "not found" in result.lower() or "does not exist" in result.lower()

    def test_empty_dir_reports_no_iterations(self, tmp_path: Path):
        d = tmp_path / "empty-run"
        d.mkdir()
        result = explain_resume_text(d)
        assert "0" in result

    def test_partial_run_shows_iteration_count(self, tmp_path: Path):
        d = tmp_path / "partial"
        iters = d / "iterations"
        iters.mkdir(parents=True)
        for i in range(1, 4):
            (iters / f"iter_00{i}.md").write_text("x", encoding="utf-8")
        result = explain_resume_text(d)
        assert "3" in result

    def test_partial_run_shows_resumable(self, tmp_path: Path):
        d = tmp_path / "partial"
        iters = d / "iterations"
        iters.mkdir(parents=True)
        (iters / "iter_001.md").write_text("x", encoding="utf-8")
        result = explain_resume_text(d)
        assert "yes" in result.lower() or "resumable" in result.lower()

    def test_completed_run_shows_synthesis_present(self, tmp_path: Path):
        d = tmp_path / "done"
        iters = d / "iterations"
        iters.mkdir(parents=True)
        (iters / "iter_001.md").write_text("x", encoding="utf-8")
        (d / "synthesis.md").write_text("# S\n", encoding="utf-8")
        result = explain_resume_text(d)
        assert "synthesis" in result.lower()

    def test_metrics_best_score_included_when_available(self, tmp_path: Path):
        import json
        d = tmp_path / "scored"
        iters = d / "iterations"
        iters.mkdir(parents=True)
        (iters / "iter_001.md").write_text("x", encoding="utf-8")
        (d / "metrics.json").write_text(
            json.dumps({"best_score": 77.3, "run_status": "running"}), encoding="utf-8"
        )
        result = explain_resume_text(d)
        assert "77.3" in result

    def test_includes_reuse_section(self, tmp_path: Path):
        d = tmp_path / "partial"
        iters = d / "iterations"
        iters.mkdir(parents=True)
        (iters / "iter_001.md").write_text("x", encoding="utf-8")
        (d / "knowledge_base.md").write_text("# KB", encoding="utf-8")
        result = explain_resume_text(d)
        assert "reused" in result.lower() or "reuse" in result.lower()

    def test_includes_regenerated_section(self, tmp_path: Path):
        d = tmp_path / "partial"
        iters = d / "iterations"
        iters.mkdir(parents=True)
        (iters / "iter_001.md").write_text("x", encoding="utf-8")
        result = explain_resume_text(d)
        assert "regenerated" in result.lower() or "regenerate" in result.lower()

    def test_does_not_create_files(self, tmp_path: Path):
        d = tmp_path / "partial"
        iters = d / "iterations"
        iters.mkdir(parents=True)
        (iters / "iter_001.md").write_text("x", encoding="utf-8")
        before = set(d.rglob("*"))
        explain_resume_text(d)
        assert set(d.rglob("*")) == before


class TestExplainWorkflowContracts:
    """Step 5: explain config surfaces workflow contracts."""

    def test_contains_workflow_contracts_section(self):
        result = explain_config_text(_make_config())
        assert "WORKFLOW CONTRACTS" in result

    def test_shows_research_mode_label(self):
        result = explain_config_text(_make_config())
        assert "research" in result.lower()

    def test_shows_hypothesis_phase(self):
        result = explain_config_text(_make_config())
        assert "hypothesis" in result

    def test_shows_execute_phase(self):
        result = explain_config_text(_make_config())
        assert "execute" in result

    def test_shows_score_phase(self):
        result = explain_config_text(_make_config())
        assert "score" in result

    def test_shows_decide_phase(self):
        result = explain_config_text(_make_config())
        assert "decide" in result

    def test_shows_merge_phase(self):
        result = explain_config_text(_make_config())
        assert "merge" in result

    def test_shows_recovery_mode_for_hypothesis(self):
        result = explain_config_text(_make_config())
        # hypothesis uses outer_loop_continue
        assert "outer_loop_continue" in result

    def test_shows_recovery_mode_none_for_score(self):
        result = explain_config_text(_make_config())
        assert "none" in result.lower()

    def test_shows_human_gate_field(self):
        result = explain_config_text(_make_config())
        assert "gate" in result.lower() or "human_gate" in result.lower()


# ---------------------------------------------------------------------------
# HITL policy — explain config
# ---------------------------------------------------------------------------

class TestExplainHitlPolicy:
    def test_hitl_policy_section_present(self):
        result = explain_config_text(_make_config())
        assert "HITL" in result

    def test_shows_intervention_mode(self):
        result = explain_config_text(_make_config())
        # default is full_auto
        assert "full_auto" in result

    def test_full_auto_shows_no_gates_note(self):
        result = explain_config_text(_make_config())
        assert "no human gates" in result or "fully automated" in result or "none" in result.lower()

    def test_non_full_auto_shows_gate_summary(self):
        from src.config import HitlConfig
        config = _make_config(hitl=HitlConfig(intervention_mode="co_pilot"))
        result = explain_config_text(config)
        assert "co_pilot" in result
        assert "gate" in result.lower()

    def test_decision_only_shows_in_explain(self):
        from src.config import HitlConfig
        config = _make_config(hitl=HitlConfig(intervention_mode="decision_only"))
        result = explain_config_text(config)
        assert "decision_only" in result


# ---------------------------------------------------------------------------
# MM09 Step 5 — explain_implement_config_text
# ---------------------------------------------------------------------------

from pathlib import Path as _Path

from src.implement.implement_loop import ImplementConfig, ImplementTarget


def _make_impl_config(tmp_path: _Path, **kwargs) -> ImplementConfig:
    target = ImplementTarget(path=tmp_path, execution_level="patch_only", allowed_roots=(_Path("src"),))
    defaults = dict(target=target, task_description="Add retry logic", max_cycles=3, convergence_cycles=1)
    defaults.update(kwargs)
    return ImplementConfig(**defaults)


class TestExplainImplementConfigText:
    def test_returns_string(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert isinstance(explain_implement_config_text(cfg), str)

    def test_shows_target_path(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert str(tmp_path) in explain_implement_config_text(cfg)

    def test_shows_execution_level(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert "patch_only" in explain_implement_config_text(cfg)

    def test_shows_task_description(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert "Add retry logic" in explain_implement_config_text(cfg)

    def test_shows_max_cycles(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert "3" in explain_implement_config_text(cfg)

    def test_shows_allowed_roots(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert "src" in explain_implement_config_text(cfg)

    def test_shows_implement_target_section(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert "TARGET" in explain_implement_config_text(cfg)

    def test_shows_safety_boundaries_section(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert "SAFETY" in explain_implement_config_text(cfg)

    def test_shows_allow_same_repo_false(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path, allow_same_repo=False)
        assert "allow_same_repo" in explain_implement_config_text(cfg)

    def test_shows_allow_same_repo_true(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path, allow_same_repo=True)
        text = explain_implement_config_text(cfg)
        assert "allow_same_repo" in text
        assert "true" in text.lower() or "True" in text

    def test_shows_no_roots_when_empty(self, tmp_path):
        from src.explain import explain_implement_config_text
        target = ImplementTarget(path=tmp_path, allowed_roots=())
        cfg = ImplementConfig(target=target, task_description="t")
        text = explain_implement_config_text(cfg)
        assert "none" in text.lower() or "unrestricted" in text.lower() or "no roots" in text.lower()

    def test_config_path_shown_when_provided(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        fake_path = tmp_path / "my_config.yaml"
        text = explain_implement_config_text(cfg, config_path=fake_path)
        assert "my_config.yaml" in text

    def test_shows_convergence_cycles(self, tmp_path):
        from src.explain import explain_implement_config_text
        cfg = _make_impl_config(tmp_path)
        assert "1" in explain_implement_config_text(cfg)


class TestCliExplainImplement:
    """CLI wiring: explain implement --config."""

    def test_explain_implement_returns_0_for_valid_config(self, tmp_path):
        from src.cli import main

        config_yaml = tmp_path / "impl.yaml"
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        config_yaml.write_text(
            f"target:\n  path: {target_dir}\n  execution_level: patch_only\n  allowed_roots:\n    - src\n"
            "task_description: Do something\nmax_cycles: 2\n"
        )
        rc = main(["explain", "implement", "--config", str(config_yaml)])
        assert rc == 0

    def test_explain_implement_returns_1_for_missing_config(self, tmp_path):
        from src.cli import main

        rc = main(["explain", "implement", "--config", str(tmp_path / "no.yaml")])
        assert rc == 1


class TestCliDoctorImplement:
    """CLI wiring: doctor implement --config."""

    def test_doctor_implement_returns_0_for_healthy_config(self, tmp_path):
        from src.cli import main

        config_yaml = tmp_path / "impl.yaml"
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        config_yaml.write_text(
            f"target:\n  path: {target_dir}\n  execution_level: patch_only\n  allowed_roots:\n    - src\n"
            "task_description: Do something\nmax_cycles: 2\n"
        )
        rc = main(["doctor", "implement", "--config", str(config_yaml)])
        assert rc == 0

    def test_doctor_implement_returns_1_for_missing_config(self, tmp_path):
        from src.cli import main

        rc = main(["doctor", "implement", "--config", str(tmp_path / "no.yaml")])
        assert rc == 1

    def test_doctor_implement_returns_1_for_no_allowed_roots(self, tmp_path):
        from src.cli import main

        config_yaml = tmp_path / "impl.yaml"
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        config_yaml.write_text(
            f"target:\n  path: {target_dir}\n  execution_level: patch_only\n"
            "task_description: Do something\nmax_cycles: 2\n"
        )
        rc = main(["doctor", "implement", "--config", str(config_yaml)])
        assert rc == 1
