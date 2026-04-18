"""Tests for DocumentRefiner — orchestrator for document convergence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backends.types import AgentResponse
from src.config import ArtifactConfig, BackendsConfig, DocumentConfig, PersonaConfig
from src.document_loop import CycleState, Issue
from src.document_refiner import EXIT_HUMAN_REQUIRED, DocumentRefiner
from src.hitl import HumanInputRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs) -> DocumentConfig:
    defaults = dict(
        topic="Test Topic",
        goal="Test goal",
        primary_artifact="PRD.md",
        convergence_cycles=1,
        max_cycles=5,
        backends=BackendsConfig(primary="claude", research=["claude", "gemini"]),
    )
    defaults.update(kwargs)
    return DocumentConfig(**defaults)


def _make_backend(text: str = "generated content") -> MagicMock:
    backend = MagicMock()
    backend.run.return_value = AgentResponse(
        text=text, cost_usd=0.01, is_error=False,
        input_tokens=100, output_tokens=50,
    )
    return backend


def _make_backends(text: str = "generated content") -> dict:
    return {
        "claude": _make_backend(text),
        "gemini": _make_backend(text),
    }


def _clean_state() -> CycleState:
    state = CycleState(prd="# PRD\n\nContent here.")
    state.consecutive_clean_cycles = 1
    state.cycle = 1
    return state


# ---------------------------------------------------------------------------
# Phase 1 — Convergence
# ---------------------------------------------------------------------------

class TestPhase1Convergence:
    def test_run_returns_zero_on_success(self, tmp_path):
        config = _make_config()
        backends = _make_backends()
        refiner = DocumentRefiner(config, tmp_path, backends)

        clean_state = _clean_state()
        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
        ):
            code = refiner.run(interactive=True)

        assert code == 0

    def test_primary_artifact_written_after_convergence(self, tmp_path):
        config = _make_config()
        backends = _make_backends("# PRD body")
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
        ):
            refiner.run(interactive=True)

        prd_path = tmp_path / "PRD.md"
        assert prd_path.exists()

    def test_cycle_snapshot_written(self, tmp_path):
        config = _make_config()
        backends = _make_backends()
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
        ):
            refiner.run(interactive=True)

        cycles_dir = tmp_path / ".run" / "cycles"
        assert cycles_dir.exists()

    def test_issue_registry_written(self, tmp_path):
        config = _make_config()
        backends = _make_backends()
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
        ):
            refiner.run(interactive=True)

        registry_path = tmp_path / ".run" / "issue_registry.json"
        assert registry_path.exists()
        data = json.loads(registry_path.read_text())
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Phase 1 — HITL pause
# ---------------------------------------------------------------------------

class TestHITLPause:
    def test_non_interactive_returns_exit_code_2_when_pending(self, tmp_path):
        config = _make_config()
        backends = _make_backends()
        refiner = DocumentRefiner(config, tmp_path, backends)

        def inject_pending(state, ctx, strategy, *, interactive):
            state.pending_human_inputs.append(
                HumanInputRequest(
                    issue_id="I-01", question="Q?", context="ctx",
                    suggested_answer="A", cycle=1,
                )
            )
            return (1, 0, 0)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", side_effect=inject_pending),
            patch("src.document_refiner._should_stop", return_value=False),
        ):
            code = refiner.run(interactive=False)

        assert code == EXIT_HUMAN_REQUIRED

    def test_non_interactive_writes_pending_questions_file(self, tmp_path):
        config = _make_config()
        backends = _make_backends()
        refiner = DocumentRefiner(config, tmp_path, backends)

        def inject_pending(state, ctx, strategy, *, interactive):
            state.pending_human_inputs.append(
                HumanInputRequest(
                    issue_id="I-01", question="Q?", context="ctx",
                    suggested_answer="A", cycle=1,
                )
            )
            return (1, 0, 0)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", side_effect=inject_pending),
            patch("src.document_refiner._should_stop", return_value=False),
        ):
            refiner.run(interactive=False)

        pending_path = tmp_path / ".run" / "pending_questions.json"
        assert pending_path.exists()


# ---------------------------------------------------------------------------
# Phase 2 — Artifact expansion
# ---------------------------------------------------------------------------

class TestPhase2Expansion:
    def test_artifacts_written_to_output_dir(self, tmp_path):
        artifact = ArtifactConfig(name="ARCH.md", layer="execution", review=False)
        config = _make_config(artifacts=(artifact,))
        backends = _make_backends("# Architecture")
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", return_value="prompt text"),
        ):
            refiner.run(interactive=True)

        assert (tmp_path / "ARCH.md").exists()

    def test_artifact_skipped_when_prompt_file_missing(self, tmp_path):
        artifact = ArtifactConfig(name="MISSING.md", layer="execution", review=False)
        config = _make_config(artifacts=(artifact,))
        backends = _make_backends()
        refiner = DocumentRefiner(config, tmp_path, backends)

        def _render_side_effect(name, **_kwargs):
            if name in ("generate_readme.md", "generate_docs_index.md"):
                return "prompt"
            raise FileNotFoundError(name)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", side_effect=_render_side_effect),
        ):
            refiner.run(interactive=True)

        content = (tmp_path / "MISSING.md").read_text()
        assert "prompt not configured" in content

    def test_artifact_with_review_applies_adversarial_loop(self, tmp_path):
        artifact = ArtifactConfig(name="REVIEWED.md", layer="execution", review=True)
        config = _make_config(artifacts=(artifact,))
        backends = _make_backends("# Reviewed Content")
        refiner = DocumentRefiner(config, tmp_path, backends)

        mock_strategy = MagicMock()
        mock_strategy.run_challenger.return_value = "raw critiques"
        mock_strategy.run_verifier.return_value = []
        mock_strategy.run_arbitrator.return_value = []

        with (
            patch("src.document_refiner.ConvergeStrategy", return_value=mock_strategy),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", return_value="prompt text"),
        ):
            refiner.run(interactive=True)

        mock_strategy.run_challenger.assert_called_once()


# ---------------------------------------------------------------------------
# Phase 3 — Indexing
# ---------------------------------------------------------------------------

class TestPhase3Indexing:
    def test_readme_written(self, tmp_path):
        config = _make_config()
        backends = _make_backends("# README")
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", return_value="prompt"),
        ):
            refiner.run(interactive=True)

        assert (tmp_path / "README.md").exists()

    def test_docs_index_written(self, tmp_path):
        config = _make_config()
        backends = _make_backends("# DOCS_INDEX")
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", return_value="prompt"),
        ):
            refiner.run(interactive=True)

        assert (tmp_path / "DOCS_INDEX.md").exists()


# ---------------------------------------------------------------------------
# Run manifest
# ---------------------------------------------------------------------------

class TestRunManifest:
    def test_manifest_written_with_correct_fields(self, tmp_path):
        config = _make_config()
        backends = _make_backends()
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", return_value="prompt"),
        ):
            refiner.run(interactive=True)

        manifest_path = tmp_path / ".run" / "run_manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert data["topic"] == "Test Topic"
        assert data["primary_artifact"] == "PRD.md"
        assert "total_cost_usd" in data
        assert "finished_at" in data

    def test_token_tracking_accumulates(self, tmp_path):
        config = _make_config()
        backend = _make_backend()
        backend.run.return_value = AgentResponse(
            text="content", cost_usd=0.05, is_error=False,
            input_tokens=200, output_tokens=100,
        )
        backends = {"claude": backend, "gemini": backend}
        refiner = DocumentRefiner(config, tmp_path, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", return_value="prompt"),
        ):
            refiner.run(interactive=True)

        assert refiner._total_cost > 0
        assert refiner._total_input_tokens > 0
        assert refiner._total_output_tokens > 0


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

class TestDirectorySetup:
    def test_creates_output_and_run_dirs(self, tmp_path):
        out = tmp_path / "nested" / "output"
        config = _make_config()
        backends = _make_backends()
        refiner = DocumentRefiner(config, out, backends)

        with (
            patch("src.document_refiner.ConvergeStrategy"),
            patch("src.document_refiner.run_cycle", return_value=(0, 0, 0)),
            patch("src.document_refiner._should_stop", side_effect=[False, True]),
            patch("src.document_refiner.render", return_value="prompt"),
        ):
            refiner.run(interactive=True)

        assert out.exists()
        assert (out / ".run").exists()
        assert (out / ".run" / "cycles").exists()
