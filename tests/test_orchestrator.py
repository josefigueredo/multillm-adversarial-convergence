"""Tests for src.orchestrator — prompt rendering, AutoResearcher."""

import csv
import json
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.backends import AgentResponse, Backend, CallOptions, StreamEvent, get_backend
from src.config import ExecutionConfig, ProviderConfig, ResearchConfig, ScoringConfig
from src.orchestrator import AutoResearcher
from src.prompts import render as _render
from src.scorer import IterationScore
from src.strategy import ResearchCandidate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeBackend(Backend):
    """In-memory backend for testing (no subprocess calls)."""

    name = "fake"

    def cli_executable(self) -> str:
        return "fake-cli"

    def prompt_mode(self):
        from src.backends import PromptMode
        return PromptMode.STDIN

    def build_command(self, opts):
        return ["fake-cli", "-p", "-"]

    def parse_response(self, stdout):
        return AgentResponse(text=stdout, cost_usd=0.0, is_error=False)

    def check_available(self) -> bool:
        return True

    def invoke(self, prompt, opts, timeout=300):
        return AgentResponse(text="fake response", cost_usd=0.01, is_error=False)


class CapturingBackend(FakeBackend):
    name = "capturing"

    def __init__(self):
        self.last_opts = None

    def invoke(self, prompt, opts, timeout=300):
        self.last_opts = opts
        return AgentResponse(text="captured", cost_usd=0.0, is_error=False)


# Remove from registry to avoid polluting other tests
if "fake" in Backend.__dict__.get("_REGISTRY", {}):
    del Backend._REGISTRY["fake"]


@pytest.fixture
def research_config() -> ResearchConfig:
    return ResearchConfig(
        topic="Test topic",
        goal="Test goal",
        dimensions=("Dim A", "Dim B", "Dim C"),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            max_iterations=2,
            backend="claude-cli",
            model="sonnet",
            timeout_seconds=10,
            max_budget_per_call=0.10,
        ),
    )


@pytest.fixture
def fake_backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def researcher(research_config, fake_backend, tmp_path) -> AutoResearcher:
    return AutoResearcher(
        config=research_config,
        backend=fake_backend,
        output_dir=tmp_path / "output",
    )


# ---------------------------------------------------------------------------
# _render
# ---------------------------------------------------------------------------

class TestRender:
    def test_renders_template(self, tmp_path, monkeypatch):
        import src.prompts as prompts_mod
        monkeypatch.setattr(prompts_mod, "PROMPTS_DIR", tmp_path)
        (tmp_path / "test.md").write_text("Hello {name}, topic: {topic}", encoding="utf-8")
        result = _render("test.md", name="Alice", topic="APIs")
        assert result == "Hello Alice, topic: APIs"

    def test_missing_template_raises(self, tmp_path, monkeypatch):
        import src.prompts as prompts_mod
        monkeypatch.setattr(prompts_mod, "PROMPTS_DIR", tmp_path)
        with pytest.raises(FileNotFoundError, match="Prompt template not found"):
            _render("nonexistent.md")


# ---------------------------------------------------------------------------
# AutoResearcher — setup and resume
# ---------------------------------------------------------------------------

class TestAutoResearcherSetup:
    def test_setup_creates_dirs(self, researcher):
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        assert researcher.output_dir.exists()
        assert researcher.iterations_dir.exists()
        assert researcher.results_path.exists()
        assert researcher.manifest_path.exists()
        assert researcher.methods_path.exists()

    def test_setup_writes_audit_trail(self, researcher):
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        audit_trail_path = researcher.output_dir / "audit_trail.jsonl"
        assert audit_trail_path.exists()
        content = audit_trail_path.read_text(encoding="utf-8")
        assert '"step": "setup_run"' in content
        assert '"event": "step_started"' in content
        assert '"event": "step_completed"' in content

    def test_setup_writes_tsv_header(self, researcher):
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        content = researcher.results_path.read_text(encoding="utf-8")
        assert "iteration" in content
        assert "dimension" in content
        assert "total_score" in content

    def test_setup_writes_run_manifest(self, researcher):
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        manifest = json.loads(researcher.manifest_path.read_text(encoding="utf-8"))
        assert manifest["run"]["status"] == "initialized"
        assert manifest["project"]["version"] == "0.2.0"
        assert manifest["environment"]["git_commit"] == "abc123"
        assert manifest["reproducibility"]["prompt_snapshot_path"].endswith("prompt_snapshot.json")
        assert manifest["reproducibility"]["rerun_script_path"].endswith("rerun.sh")

    def test_setup_writes_methods_artifact(self, researcher):
        researcher.config = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            methodology=researcher.config.methodology.__class__(
                question="What is the best option?",
                scope="Architectural decision support",
                search_sources=("official docs", "benchmarks"),
                stopping_criteria=("cover all dimensions",),
                stopping_rationale="Bound cost while preserving quality.",
                scoring_rationale="Reward evidence-backed synthesis.",
                review_type="systematic_review",
            ),
            evaluation=researcher.config.evaluation,
            reporting=researcher.config.reporting,
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        methods = researcher.methods_path.read_text(encoding="utf-8")
        assert "# Research Methods" in methods
        assert "Test goal" in methods
        assert "Review type: systematic_review" in methods
        assert "Search sources:" in methods
        assert "Stopping rationale: Bound cost while preserving quality." in methods
        assert "Scoring rationale: Reward evidence-backed synthesis." in methods

    def test_setup_writes_rerun_script(self, researcher):
        researcher.config_path = Path("configs/example.yaml")
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        rerun_script = researcher.output_dir / "rerun.sh"
        assert rerun_script.exists()
        content = rerun_script.read_text(encoding="utf-8")
        assert "autoresearch run" in content
        assert "--config" in content
        assert "configs/example.yaml" in content
        assert "--output" in content

    def test_setup_writes_effective_config(self, researcher):
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        # Verify file is at the centralized RunPaths location
        assert researcher.paths.effective_config.exists()
        data = json.loads(researcher.paths.effective_config.read_text(encoding="utf-8"))
        assert data["topic"] == "Test topic"
        assert "security" in data
        assert "execution" in data
        assert "reporting" in data
        assert "backends" in data
        assert "dimensions" in data
        assert "methodology" in data
        assert "evaluation" in data
        assert "scoring" in data
        assert "providers" in data


        researcher.config = ResearchConfig(
            topic="What are three pros and cons of Python?",
            goal="A bullet-point list in under 100 words",
            dimensions=("Developer experience",),
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=researcher.config.reporting,
            scoring=researcher.config.scoring,
            execution=ExecutionConfig(
                max_iterations=1,
                backend="claude-cli",
                model="sonnet",
                timeout_seconds=10,
                max_budget_per_call=0.10,
                allowed_tools="",
            ),
        )
        assert researcher._is_lightweight_mode() is True
        constraints = researcher._goal_constraints_summary().lower()
        assert "bullet points" in constraints
        assert "under 100 words" in constraints

    def test_generate_synthesis_uses_goal_constraints_and_lightweight_context(self, researcher):
        researcher.config = ResearchConfig(
            topic="What are three pros and cons of Python?",
            goal="A bullet-point list in under 100 words",
            dimensions=("Developer experience",),
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=researcher.config.reporting,
            scoring=researcher.config.scoring,
            execution=ExecutionConfig(
                max_iterations=1,
                backend="claude-cli",
                model="sonnet",
                timeout_seconds=10,
                max_budget_per_call=0.10,
                allowed_tools="",
            ),
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.knowledge_base = "word " * 2000
        researcher.results = [
            {"iteration": "001", "dimension": "Developer experience", "total_score": "80.0", "status": "keep"}
        ]

        captured: dict[str, str] = {}

        def fake_call(backend, prompt, **kwargs):
            captured["prompt"] = prompt
            return AgentResponse(text="- Pro: readable\n- Con: slower", cost_usd=0.0, is_error=False)

        with patch.object(researcher, "_call_with", side_effect=fake_call):
            researcher._generate_synthesis()

        prompt = captured["prompt"]
        assert "Deliverable Goal" in prompt
        assert "under 100 words" in prompt.lower()
        assert "lightweight_mode" in prompt
        assert "lightweight mode: truncated knowledge base" in prompt.lower()

    def test_generate_synthesis_injects_output_style_contract(self, researcher):
        researcher.config = ResearchConfig(
            topic="API gateways",
            goal="Recommend a path forward.",
            dimensions=("Architecture",),
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=researcher.config.reporting.__class__(output_style="paper"),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.knowledge_base = "Documented evidence about multiple gateway options."

        captured: dict[str, str] = {}

        def fake_call(backend, prompt, **kwargs):
            captured["prompt"] = prompt
            return AgentResponse(text="## Abstract\nFindings.", cost_usd=0.0, is_error=False)

        with patch.object(researcher, "_call_with", side_effect=fake_call):
            researcher._generate_synthesis()

        prompt = captured["prompt"]
        assert "Output Style Contract" in prompt
        assert "Abstract" in prompt
        assert "Methodology" in prompt
        assert "Limitations" in prompt
        assert "Do not include an executive summary" in prompt
        assert "Do not include a comparison table" in prompt
        assert "dedicated References section" in prompt
        assert "Present evidence and findings before stating the recommendation" in prompt

    def test_generate_synthesis_injects_output_style_overrides(self, researcher):
        researcher.config = ResearchConfig(
            topic="API gateways",
            goal="Recommend a path forward.",
            dimensions=("Architecture",),
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=researcher.config.reporting.__class__(
                output_style="technical_doc",
                style_overrides=researcher.config.reporting.style_overrides.__class__(
                    include_executive_summary=False,
                    include_comparison_table=True,
                    include_methodology=False,
                    include_limitations=True,
                    include_next_actions=True,
                    section_order="recommendation_first",
                    recommendation_mode="decision_only",
                    citation_mode="references_section",
                ),
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.knowledge_base = "Documented evidence about multiple gateway options."

        captured: dict[str, str] = {}

        def fake_call(backend, prompt, **kwargs):
            captured["prompt"] = prompt
            return AgentResponse(text="## Decision\nFindings.", cost_usd=0.0, is_error=False)

        with patch.object(researcher, "_call_with", side_effect=fake_call):
            researcher._generate_synthesis()

        prompt = captured["prompt"].lower()
        assert "do not include an executive summary" in prompt
        assert "include a comparison table" in prompt
        assert "do not include a standalone methodology section" in prompt
        assert "include a limitations section" in prompt
        assert "next actions section" in prompt
        assert "lead with the recommendation before supporting evidence" in prompt
        assert "single decision section" in prompt
        assert "references section" in prompt

    def test_call_with_uses_isolated_backend_context_by_default(self, tmp_path):
        backend = CapturingBackend()
        cfg = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(
                backend="claude-cli",
                model="sonnet",
                isolate_backend_context=True,
                sanitize_backend_env=True,
            ),
        )
        researcher = AutoResearcher(config=cfg, backend=backend, output_dir=tmp_path / "output")
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher._call_with(backend, "hello")
        assert backend.last_opts is not None
        assert backend.last_opts.sanitize_environment is True
        assert backend.last_opts.working_directory
        assert "autoresearch-backend-" in backend.last_opts.working_directory

    def test_call_with_applies_provider_model_override(self, tmp_path):
        backend = CapturingBackend()
        backend.provider_config = ProviderConfig(adapter="claude-cli", model="opus")
        cfg = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(
                backend="claude-cli",
                model="sonnet",
                isolate_backend_context=False,
                sanitize_backend_env=False,
            ),
            providers={"primary_reasoner": backend.provider_config},
        )
        researcher = AutoResearcher(config=cfg, backend=backend, output_dir=tmp_path / "output")
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher._call_with(backend, "hello")
        assert backend.last_opts is not None
        assert backend.last_opts.model == "opus"

    def test_resolve_model_keeps_claude_shortname_for_claude_cli(self):
        backend = get_backend("claude-cli")
        assert AutoResearcher._resolve_model(backend, "sonnet") == "sonnet"

    def test_resolve_model_maps_claude_shortname_for_claude_api(self):
        backend = get_backend("claude-api")
        assert AutoResearcher._resolve_model(backend, "sonnet") == "claude-sonnet-4-5"

    def test_resolve_model_maps_claude_shortname_for_direct_openai_api(self):
        backend = get_backend("codex-api")
        assert AutoResearcher._resolve_model(backend, "sonnet") == "gpt-5.4"

    def test_resolve_model_maps_claude_shortname_for_direct_gemini_api(self):
        backend = get_backend("gemini-api")
        assert AutoResearcher._resolve_model(backend, "sonnet") == "gemini-2.5-flash"

    def test_resolve_model_rejects_claude_shortname_for_aggregator(self):
        backend = get_backend("litellm-api")
        with pytest.raises(ValueError, match="explicit model"):
            AutoResearcher._resolve_model(backend, "sonnet")

    def test_call_with_rejects_implicit_shortname_on_aggregator(self, tmp_path):
        backend = get_backend("litellm-api")
        with patch.object(backend, "invoke", return_value=AgentResponse(text="ok", cost_usd=0.0, is_error=False)):
            cfg = ResearchConfig(
                topic="Test topic",
                goal="Test goal",
                dimensions=("Dim A",),
                scoring=ScoringConfig(),
                execution=ExecutionConfig(
                    backend="litellm-api",
                    model="sonnet",
                    isolate_backend_context=False,
                    sanitize_backend_env=False,
                ),
            )
            researcher = AutoResearcher(config=cfg, backend=backend, output_dir=tmp_path / "output")
            with pytest.raises(ValueError, match="explicit model"):
                researcher._call_with(backend, "hello")

    def test_call_with_preserves_explicit_aggregator_model(self, tmp_path):
        backend = get_backend("litellm-api")
        captured = {}

        def fake_invoke(prompt, opts, timeout=300):
            captured["model"] = opts.model
            return AgentResponse(text="ok", cost_usd=0.0, is_error=False)

        with patch.object(backend, "invoke", side_effect=fake_invoke):
            cfg = ResearchConfig(
                topic="Test topic",
                goal="Test goal",
                dimensions=("Dim A",),
                scoring=ScoringConfig(),
                execution=ExecutionConfig(
                    backend="litellm-api",
                    model="openai/gpt-4.1-mini",
                    isolate_backend_context=False,
                    sanitize_backend_env=False,
                ),
            )
            researcher = AutoResearcher(config=cfg, backend=backend, output_dir=tmp_path / "output")
            researcher._call_with(backend, "hello")
        assert captured["model"] == "openai/gpt-4.1-mini"

    def test_call_with_skips_isolation_when_disabled_in_config(self, tmp_path):
        """When isolate_backend_context=False, _call_with must pass cwd=None
        and env=None to the subprocess runner.
        """
        from src.backends.base import Backend, PromptMode
        from src.backends.types import AgentResponse, BackendCapabilities

        class PlainBackend(Backend):
            name = "stub-plain"
            capabilities = BackendCapabilities()

            def cli_executable(self) -> str:
                return "stub"

            def prompt_mode(self) -> PromptMode:
                return PromptMode.STDIN

            def build_command(self, opts):
                return ["stub"]

            def parse_response(self, stdout):
                return AgentResponse(text=stdout, cost_usd=0.0, is_error=False)

            def check_available(self) -> bool:
                return True

        backend = PlainBackend()
        cfg = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(
                backend="claude-cli",
                model="sonnet",
                isolate_backend_context=False,
                sanitize_backend_env=False,
            ),
        )
        researcher = AutoResearcher(config=cfg, backend=backend, output_dir=tmp_path / "output")

        captured = {}

        def fake_run(cmd, *, input=None, timeout=300, cwd=None, env=None):
            captured["cwd"] = cwd
            captured["env"] = env
            from subprocess import CompletedProcess

            return CompletedProcess(args=cmd, returncode=0, stdout='{"result":"ok","cost_usd":0.0}', stderr="")

        with patch.object(PlainBackend, "_resolve_executable", return_value="stub"), \
             patch.object(PlainBackend, "_run_process", side_effect=fake_run), \
             patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
            resp = researcher._call_with(backend, "hello")

        assert resp.is_error is False
        assert captured["cwd"] is None
        assert captured["env"] is None

    def test_score_findings_prompt_mentions_short_goal_constraints(self, researcher):
        researcher.config = ResearchConfig(
            topic="What are three pros and cons of Python?",
            goal="A bullet-point list in under 100 words",
            dimensions=("Developer experience",),
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=researcher.config.reporting,
            scoring=researcher.config.scoring,
            execution=ExecutionConfig(
                max_iterations=1,
                backend="claude-cli",
                model="sonnet",
                timeout_seconds=10,
                max_budget_per_call=0.10,
                allowed_tools="",
            ),
        )
        captured: dict[str, str] = {}

        def fake_call(backend, prompt, **kwargs):
            captured["prompt"] = prompt
            return AgentResponse(
                text=json.dumps(
                    {
                        "depth": 7,
                        "accuracy": 8,
                        "novelty": 7,
                        "actionability": 7,
                        "dimensions_covered": ["Developer experience"],
                        "gaps_identified": [],
                        "reasoning": "Concise but sufficient.",
                    }
                ),
                cost_usd=0.0,
                is_error=False,
            )

        with patch.object(researcher, "_call_with", side_effect=fake_call):
            score = researcher._score(
                "Developer experience",
                "Developer experience is Python's biggest strength. Trade-off: slower CPU performance."
            )

        prompt = captured["prompt"]
        assert "Deliverable Goal" in prompt
        assert "under 100 words" in prompt.lower()
        assert "lightweight mode" in prompt.lower()
        assert score.quality > 0

    def test_postprocess_goal_output_enforces_bullets_and_word_limit(self, researcher):
        researcher.config = ResearchConfig(
            topic="What are three pros and cons of Python?",
            goal="A bullet-point list in under 20 words",
            dimensions=("Developer experience",),
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=researcher.config.reporting,
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        raw = (
            "# Python Assessment\n\nPython is readable and productive. "
            "It also has slower CPU performance. Tooling is good."
        )
        fixed = researcher._postprocess_goal_output(raw)
        assert fixed.startswith("- ")
        assert len(fixed.split()) <= 20

    def test_generate_baseline_postprocesses_short_goal_output(self, researcher):
        researcher.config = ResearchConfig(
            topic="What are three pros and cons of Python?",
            goal="A bullet-point list in under 12 words",
            dimensions=("Developer experience",),
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(run_baselines=True),
            reporting=researcher.config.reporting,
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()

        with patch.object(
            researcher,
            "_call_with",
            return_value=AgentResponse(
                text="Python is readable. Python can be slower on CPU-bound workloads.",
                cost_usd=0.0,
                is_error=False,
            ),
        ):
            researcher._generate_baseline()

        baseline = researcher.baseline_path.read_text(encoding="utf-8")
        assert baseline.startswith("- ")
        assert len(baseline.split()) <= 12

    def test_finalize_writes_html_report(self, researcher):
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        synthesis_text = (
            "Recommend Python for orchestration-heavy workloads. "
            "High confidence. https://docs.python.org/3/"
        )
        researcher.best_score = 87.0
        researcher.explored_dimensions = ["Developer experience", "Performance"]
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")
        researcher._finalize_run_artifacts()
        html = researcher.report_html_path.read_text(encoding="utf-8")
        assert "<title>Test topic</title>" in html
        assert "Developer experience" in html
        assert "Recommend Python for orchestration-heavy workloads." in html
        assert "Rubric" in html
        assert "Semantic Calibration" in html
        assert "Dashboard Summary" in html

    def test_finalize_writes_pdf_report(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=researcher.config.evaluation,
            reporting=type(researcher.config.reporting)(export_html=False, export_pdf=True, report_title="PDF Report"),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        synthesis_text = "Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/"
        researcher.best_score = 87.0
        researcher.explored_dimensions = ["Developer experience", "Performance"]
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")
        researcher._finalize_run_artifacts()
        pdf_bytes = researcher.report_pdf_path.read_bytes()
        assert pdf_bytes.startswith(b"%PDF-1.4")
        assert b"PDF Report" in pdf_bytes

    def test_finalize_writes_portfolio_artifacts(self, researcher, tmp_path):
        sibling = tmp_path / "prior-run"
        sibling.mkdir()
        (sibling / "dashboard.json").write_text(
            json.dumps(
                {
                    "topic": "Previous topic",
                    "benchmark_id": "bench-001",
                    "current_strategy": "single",
                    "best_score": 75.0,
                    "rubric_grade": "good",
                    "consistency_level": "medium",
                }
            ),
            encoding="utf-8",
        )
        researcher.output_dir = tmp_path / "current-run"
        researcher.iterations_dir = researcher.output_dir / "iterations"
        researcher.results_path = researcher.output_dir / "results.tsv"
        researcher.kb_path = researcher.output_dir / "knowledge_base.md"
        researcher.synthesis_path = researcher.output_dir / "synthesis.md"
        researcher.methods_path = researcher.output_dir / "methods.md"
        researcher.manifest_path = researcher.output_dir / "run_manifest.json"
        researcher.metrics_path = researcher.output_dir / "metrics.json"
        researcher.claims_path = researcher.output_dir / "claims.json"
        researcher.citations_path = researcher.output_dir / "citations.json"
        researcher.evidence_links_path = researcher.output_dir / "evidence_links.json"
        researcher.evidence_quality_path = researcher.output_dir / "evidence_quality.json"
        researcher.rubric_path = researcher.output_dir / "rubric.json"
        researcher.contradictions_path = researcher.output_dir / "contradictions.json"
        researcher.search_log_path = researcher.output_dir / "search_log.json"
        researcher.screening_log_path = researcher.output_dir / "screening_log.json"
        researcher.baseline_path = researcher.output_dir / "baseline.md"
        researcher.evaluation_path = researcher.output_dir / "evaluation.json"
        researcher.comparison_path = researcher.output_dir / "comparison.json"
        researcher.strategy_summary_path = researcher.output_dir / "strategy_summary.json"
        researcher.dashboard_path = researcher.output_dir / "dashboard.json"
        researcher.semantic_calibration_path = researcher.output_dir / "semantic_calibration.json"
        researcher.semantic_review_path = researcher.output_dir / "semantic_review.json"
        researcher.report_html_path = researcher.output_dir / "report.html"
        researcher.report_pdf_path = researcher.output_dir / "report.pdf"
        researcher.portfolio_path = researcher.output_dir.parent / "portfolio.json"
        researcher.portfolio_html_path = researcher.output_dir.parent / "portfolio.html"

        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        synthesis_text = "Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/"
        researcher.best_score = 87.0
        researcher.explored_dimensions = ["Developer experience"]
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")
        researcher._finalize_run_artifacts()

        portfolio = json.loads(researcher.portfolio_path.read_text(encoding="utf-8"))
        portfolio_html = researcher.portfolio_html_path.read_text(encoding="utf-8")
        assert portfolio["runs_count"] == 2
        assert portfolio["best_run"]["name"] == "current-run"
        assert "current-run" in portfolio_html
        assert "prior-run" in portfolio_html

    def test_finalize_delegates_to_run_finalize_module(self, researcher):
        with patch("src.orchestrator.finalize_run_artifacts") as finalize:
            researcher._finalize_run_artifacts()
        finalize.assert_called_once_with(researcher)

    def test_reporting_artifacts_delegate_to_report_exports_module(self, researcher):
        with patch("src.orchestrator.write_reporting_artifacts") as writer:
            researcher._write_reporting_artifacts()
        writer.assert_called_once_with(researcher)

    def test_run_metadata_artifacts_delegate_to_helper_module(self, researcher):
        with patch("src.orchestrator.write_run_metadata_artifacts") as writer:
            researcher._write_run_metadata_artifacts()
        writer.assert_called_once_with(researcher)

    def test_agreement_artifact_delegates_to_helper_module(self, researcher):
        with patch("src.orchestrator.write_agreement_artifact") as writer:
            researcher._write_agreement_artifact()
        writer.assert_called_once_with(researcher)

    def test_evaluation_artifact_delegates_to_helper_module(self, researcher):
        with patch("src.orchestrator.write_evaluation_artifacts") as writer:
            researcher._write_evaluation_artifact(
                {"average_evidence_quality_score": 0.7},
                {"grade": "good"},
                benchmark_summary={},
                reference_comparison={},
                semantic_review={"grade": "good"},
                semantic_calibration={"grade": "reasonable"},
            )
        writer.assert_called_once()

    def test_resume_empty_dir(self, researcher):
        researcher._setup()
        researcher._resume()
        assert researcher.iteration == 0
        assert researcher.best_score == 0.0

    def test_resume_rebuilds_state(self, researcher):
        researcher._setup()

        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        (researcher.iterations_dir / "iter_002.md").write_text("# Iter 2", encoding="utf-8")

        rows = [
            {"iteration": "001", "timestamp": "T", "dimension": "Dim A",
             "coverage_score": "80.0", "quality_score": "70.0", "total_score": "74.0",
             "status": "keep", "hypothesis": "h", "cumulative_cost_usd": "0.1"},
            {"iteration": "002", "timestamp": "T", "dimension": "Dim B",
             "coverage_score": "60.0", "quality_score": "50.0", "total_score": "54.0",
             "status": "discard", "hypothesis": "h", "cumulative_cost_usd": "0.2"},
        ]
        with open(researcher.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        researcher._resume()
        assert researcher.iteration == 2
        assert researcher.best_score == 74.0
        assert researcher.best_scores["Dim A"] == 74.0
        assert "Dim A" in researcher.explored_dimensions
        assert len(researcher.results) == 2

    def test_resume_restores_discovered_dimensions_from_results(self, researcher):
        researcher._setup()
        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        rows = [
            {"iteration": "001", "timestamp": "T", "dimension": "Dim A",
             "coverage_score": "80.0", "quality_score": "70.0", "total_score": "74.0",
             "status": "keep", "hypothesis": "h", "discovered_gaps": json.dumps(["Gap X"]),
             "cumulative_cost_usd": "0.1"}
        ]
        with open(researcher.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        researcher._resume()
        assert "Gap X" in researcher.discovered_dimensions

    def test_run_without_resume_does_not_restore_state(self, researcher):
        researcher._setup()
        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        with patch.object(researcher, "_run_iteration", side_effect=KeyboardInterrupt), \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"):
            researcher.run()
        assert researcher.iteration == 0

    def test_run_with_resume_restores_state(self, research_config, fake_backend, tmp_path):
        researcher = AutoResearcher(
            config=research_config,
            backend=fake_backend,
            output_dir=tmp_path / "output",
            resume=True,
        )
        researcher._setup()
        (researcher.iterations_dir / "iter_001.md").write_text("# Iter 1", encoding="utf-8")
        rows = [
            {"iteration": "001", "timestamp": "T", "dimension": "Dim A",
             "coverage_score": "80.0", "quality_score": "70.0", "total_score": "74.0",
             "status": "keep", "hypothesis": "h", "cumulative_cost_usd": "0.1"}
        ]
        with open(researcher.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

        with patch.object(researcher, "_run_iteration", side_effect=KeyboardInterrupt), \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"), \
             patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher.run()
        assert researcher.iteration == 1
        assert researcher.best_score == 74.0

    def test_should_stop_on_target_dimensions_total(self, researcher):
        researcher.explored_dimensions = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        assert researcher._should_stop() is True

    def test_run_stops_when_target_dimensions_total_reached(self, research_config, fake_backend, tmp_path):
        researcher = AutoResearcher(
            config=research_config,
            backend=fake_backend,
            output_dir=tmp_path / "output",
        )
        researcher.explored_dimensions = [f"Dim {i}" for i in range(10)]
        with patch.object(researcher, "_run_iteration") as mock_iter, \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"), \
             patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher.run()
        mock_iter.assert_not_called()

    def test_run_writes_metrics_artifact(self, researcher):
        researcher.results = [{"iteration": "001", "dimension": "Dim A", "total_score": "80.0", "status": "keep"}]
        researcher.explored_dimensions = ["Dim A"]
        researcher.total_input_tokens = 10
        researcher.total_output_tokens = 5
        with patch.object(researcher, "_run_iteration", side_effect=KeyboardInterrupt), \
             patch.object(researcher, "_generate_synthesis"), \
             patch.object(researcher, "_print_summary"), \
             patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher.run()
        metrics = json.loads(researcher.metrics_path.read_text(encoding="utf-8"))
        assert metrics["run_status"] == "interrupted"
        assert metrics["explored_dimensions"] == ["Dim A"]
        assert metrics["total_input_tokens"] == 10

    def test_finalize_writes_provenance_artifacts(self, researcher):
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher._collect_provenance(
            "Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/",
            scope="iteration-001",
            dimension="Developer experience",
        )
        researcher._finalize_run_artifacts()
        claims = json.loads(researcher.claims_path.read_text(encoding="utf-8"))
        citations = json.loads(researcher.citations_path.read_text(encoding="utf-8"))
        links = json.loads(researcher.evidence_links_path.read_text(encoding="utf-8"))
        evidence_quality = json.loads(researcher.evidence_quality_path.read_text(encoding="utf-8"))
        rubric = json.loads(researcher.rubric_path.read_text(encoding="utf-8"))
        contradictions = json.loads(researcher.contradictions_path.read_text(encoding="utf-8"))
        assert any(claim["claim_type"] == "recommendation" for claim in claims)
        assert any(citation["url"].startswith("https://docs.python.org") for citation in citations)
        assert len(links) == len(claims)
        assert "average_evidence_quality_score" in evidence_quality
        assert rubric["grade"] in {"strong", "good", "developing", "insufficient"}
        assert contradictions == []

    def test_generate_baseline_and_evaluation_artifacts(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                benchmark_id="bench-001",
                run_baselines=True,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.knowledge_base = "Developer experience Iterative knowledge"
        with patch.object(researcher, "_call_with", return_value=AgentResponse(
            text="Recommend Python for orchestration-heavy workloads. High confidence. https://docs.python.org/3/",
            cost_usd=0.0,
            is_error=False,
        )):
            researcher._generate_synthesis()
            researcher._generate_baseline()
            researcher._finalize_run_artifacts()
        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert evaluation["benchmark_id"] == "bench-001"
        assert evaluation["baseline_generated"] is True
        assert evaluation["rubric"]["grade"] in {"strong", "good", "developing", "insufficient"}
        assert evaluation["summary"]["rubric_grade"] == evaluation["rubric"]["grade"]
        assert evaluation["semantic_calibration"]["grade"] in {"well_calibrated", "reasonable", "tentative", "weak"}
        assert evaluation["summary"]["semantic_calibration_grade"] == evaluation["semantic_calibration"]["grade"]
        assert evaluation["benchmark"]["benchmark_title"] == "Python orchestration smoke benchmark"
        assert evaluation["benchmark"]["all_expectations_satisfied"] is True

    def test_generate_benchmark_evaluation_without_baseline(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                benchmark_id="bench-002",
                run_baselines=False,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.knowledge_base = "Developer experience findings"
        researcher.synthesis_path.write_text(
            "Python remains suitable for orchestration-heavy workloads. https://docs.python.org/3/",
            encoding="utf-8",
        )

        researcher._finalize_run_artifacts()

        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert evaluation["benchmark_id"] == "bench-002"
        assert evaluation["baseline_generated"] is False
        assert evaluation["benchmark"]["benchmark_title"] == "Python orchestration coverage benchmark"
        assert evaluation["benchmark"]["covered_dimensions"] == ["Developer experience"]
        assert evaluation["benchmark"]["matched_keywords"] == ["python", "workloads"]
        assert evaluation["summary"]["benchmark_expectations_satisfied"] is True

    def test_generate_benchmark_evaluation_for_vendor_comparison_catalog(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal="Compare and recommend the best option",
            dimensions=("Cost and pricing", "Operational complexity"),
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                benchmark_id="bench-003",
                run_baselines=False,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()
        researcher.explored_dimensions = ["Cost and pricing", "Operational complexity"]
        researcher.knowledge_base = "Cost and pricing plus operational complexity trade-off and recommendation."
        researcher.synthesis_path.write_text(
            "Compare the options and recommend one based on a clear trade-off analysis of cost and pricing and operational complexity.",
            encoding="utf-8",
        )

        researcher._finalize_run_artifacts()

        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert evaluation["benchmark"]["benchmark_title"] == "Vendor comparison decision benchmark"
        assert evaluation["benchmark"]["covered_dimensions"] == ["Cost and pricing", "Operational complexity"]
        assert evaluation["benchmark"]["matched_keywords"] == ["recommendation", "trade-off", "compare"]

    def test_generate_reference_run_comparison_artifacts(self, researcher, tmp_path):
        reference_dir = tmp_path / "prior-run"
        reference_dir.mkdir()
        (reference_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "benchmark_id": "bench-001",
                    "best_score": 80.0,
                    "explored_dimensions": ["Developer experience", "Security"],
                }
            ),
            encoding="utf-8",
        )
        (reference_dir / "run_manifest.json").write_text(
            json.dumps({"strategy": {"name": "ensemble"}, "evaluation": {"benchmark_id": "bench-001"}}),
            encoding="utf-8",
        )
        (reference_dir / "claims.json").write_text(
            json.dumps(
                [
                    {
                        "id": "synthesis-claim-001",
                        "scope": "synthesis",
                        "text": "Recommend Python for orchestration-heavy workloads.",
                    }
                ]
            ),
            encoding="utf-8",
        )
        (reference_dir / "citations.json").write_text(
            json.dumps(
                [
                    {
                        "id": "synthesis-cite-001",
                        "scope": "synthesis",
                        "url": "https://docs.python.org/3/",
                    }
                ]
            ),
            encoding="utf-8",
        )

        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(
                reference_runs=(str(reference_dir),),
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()

        researcher.explored_dimensions = ["Developer experience", "Performance"]
        researcher.best_score = 88.0
        synthesis_text = (
            "Recommend Python for orchestration-heavy workloads. "
            "High confidence. https://docs.python.org/3/"
        )
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")

        researcher._finalize_run_artifacts()

        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        comparison = json.loads(researcher.comparison_path.read_text(encoding="utf-8"))
        strategy_summary = json.loads(researcher.strategy_summary_path.read_text(encoding="utf-8"))
        dashboard = json.loads(researcher.dashboard_path.read_text(encoding="utf-8"))
        semantic_calibration = json.loads(researcher.semantic_calibration_path.read_text(encoding="utf-8"))
        assert evaluation["summary"]["reference_runs_compared"] == 1
        assert comparison["compared_runs_count"] == 1
        assert comparison["runs"][0]["strategy"] == "ensemble"
        assert comparison["runs"][0]["score_delta"] == 8.0
        assert comparison["runs"][0]["shared_dimensions"] == ["Developer experience"]
        assert comparison["summary"]["consistency_level"] in {"medium", "high", "low"}
        assert comparison["strategy_summary"]["best_reference_strategy"] == "ensemble"
        assert strategy_summary["current_strategy"] == researcher.config.execution.strategy
        assert any(item["strategy"] == "ensemble" for item in strategy_summary["strategies"])
        assert dashboard["current_strategy"] == researcher.config.execution.strategy
        assert dashboard["reference_runs_compared"] == 1
        assert dashboard["strategy_summary"]["best_reference_strategy"] == "ensemble"
        assert semantic_calibration["enabled"] is True
        assert semantic_calibration["grade"] in {"well_calibrated", "reasonable", "tentative", "weak"}

    def test_finalize_writes_semantic_review_when_enabled(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=researcher.config.methodology,
            evaluation=type(researcher.config.evaluation)(semantic_review=True),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        with patch("src.orchestrator.git_commit", return_value="abc123"), \
             patch("src.orchestrator.cli_version", return_value="1.0"), \
             patch("src.orchestrator.package_version", return_value="0.2.0"):
            researcher._setup()

        synthesis_text = "Recommend Python. High confidence. https://docs.python.org/3/"
        researcher.synthesis_path.write_text(synthesis_text, encoding="utf-8")
        researcher._collect_provenance(synthesis_text, scope="synthesis")

        def fake_call(backend, prompt, **kwargs):
            if "semantic quality judge" in prompt.lower():
                return AgentResponse(
                    text=json.dumps(
                        {
                            "dimensions": {
                                "coherence": 0.8,
                                "support": 0.7,
                                "limitations": 0.6,
                                "contradiction_handling": 0.9,
                                "decision_readiness": 0.75,
                            },
                            "grade": "good",
                            "summary": "Decision-ready with minor gaps.",
                        }
                    ),
                    cost_usd=0.0,
                    is_error=False,
                )
            return AgentResponse(text="noop", cost_usd=0.0, is_error=False)

        with patch.object(researcher, "_call_with", side_effect=fake_call):
            researcher._finalize_run_artifacts()

        semantic_review = json.loads(researcher.semantic_review_path.read_text(encoding="utf-8"))
        evaluation = json.loads(researcher.evaluation_path.read_text(encoding="utf-8"))
        assert semantic_review["enabled"] is True
        assert semantic_review["grade"] == "good"
        assert semantic_review["judge_backend"] == researcher.strategy.get_judge_backend().name
        assert evaluation["semantic_review"]["grade"] == "good"
        assert evaluation["summary"]["semantic_review_grade"] == "good"


# ---------------------------------------------------------------------------
# AutoResearcher — dimension exhaustion
# ---------------------------------------------------------------------------

class TestDimensionExhaustion:
    def test_maybe_exhaust_below_threshold(self, researcher):
        researcher._dimension_attempts["Dim A"] = 1
        researcher._maybe_exhaust_dimension("Dim A")
        assert "Dim A" not in researcher.explored_dimensions

    def test_maybe_exhaust_at_threshold(self, researcher):
        researcher._dimension_attempts["Dim A"] = 3
        researcher._maybe_exhaust_dimension("Dim A")
        assert "Dim A" in researcher.explored_dimensions

    def test_already_explored_not_duplicated(self, researcher):
        researcher.explored_dimensions.append("Dim A")
        researcher._dimension_attempts["Dim A"] = 5
        researcher._maybe_exhaust_dimension("Dim A")
        assert researcher.explored_dimensions.count("Dim A") == 1


# ---------------------------------------------------------------------------
# AutoResearcher — helpers
# ---------------------------------------------------------------------------

class TestAutoResearcherHelpers:
    def test_kb_summary_empty(self, researcher):
        assert "No prior findings" in researcher._kb_summary()

    def test_kb_summary_short(self, researcher):
        researcher.knowledge_base = "Some findings about APIs."
        assert researcher._kb_summary() == "Some findings about APIs."

    def test_kb_summary_truncated(self, researcher):
        researcher.knowledge_base = "word " * 5000
        summary = researcher._kb_summary()
        # Sandwich pattern: keeps head + tail, truncates middle
        assert "truncated" in summary
        assert summary.startswith("word")
        assert summary.rstrip().endswith("word")
        assert len(summary.split()) < 5000

    def test_format_dimension_list_empty(self, researcher):
        assert researcher._format_dimension_list([]) == "(none)"

    def test_format_dimension_list(self, researcher):
        result = researcher._format_dimension_list(["A", "B"])
        assert result == "- A\n- B"

    def test_format_results_table_empty(self, researcher):
        assert researcher._format_results_table() == "(no results yet)"

    def test_format_results_table(self, researcher):
        researcher.results = [
            {"iteration": "001", "dimension": "Dim A", "total_score": "85.0", "status": "keep"},
        ]
        table = researcher._format_results_table()
        assert "Dim A" in table
        assert "85.0" in table
        assert "keep" in table

    def test_candidate_selection_prefers_scored_best_over_longest(self, researcher):
        candidates = [
            ResearchCandidate(findings="long but weak", backend_name="claude-cli", cost_usd=0.1),
            ResearchCandidate(findings="short but strong", backend_name="codex-cli", cost_usd=0.1),
        ]

        def fake_score(ctx, state, dimension, findings):
            if findings == "long but weak":
                return IterationScore(total=40.0)
            return IterationScore(total=85.0)

        with patch("src.research_loop._score", side_effect=fake_score):
            selected = researcher._select_candidate_findings("Dim A", candidates)

        assert selected == "short but strong"

    def test_candidate_union_merges_only_above_threshold(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            scoring=researcher.config.scoring,
            execution=ExecutionConfig(
                **{
                    **researcher.config.execution.__dict__,
                    "strategy_config": researcher.config.execution.strategy_config.__class__(
                        **{
                            **researcher.config.execution.strategy_config.__dict__,
                            "merge_mode": "union",
                            "merge_threshold": 60.0,
                        }
                    ),
                }
            ),
        )
        candidates = [
            ResearchCandidate(findings="finding A", backend_name="claude-cli", cost_usd=0.1),
            ResearchCandidate(findings="finding B", backend_name="codex-cli", cost_usd=0.1),
        ]

        def fake_score(ctx, state, dimension, findings):
            return IterationScore(total=75.0 if findings == "finding A" else 50.0)

        with patch("src.research_loop._score", side_effect=fake_score):
            selected = researcher._select_candidate_findings("Dim A", candidates)

        assert "finding A" in selected
        assert "finding B" not in selected

    def test_generate_hypothesis_includes_discovered_dimensions(self, researcher):
        researcher.discovered_dimensions.append("New Gap")
        researcher.explored_dimensions.append("Dim A")
        with patch("src.research_loop._render") as mock_render, \
             patch.object(researcher, "_call_with", return_value=AgentResponse(
                 text=json.dumps({"dimension": "New Gap", "questions": [], "approach": ""}),
                 cost_usd=0.0,
                 is_error=False,
             )):
            researcher._generate_hypothesis()

        render_kwargs = mock_render.call_args.kwargs
        assert "New Gap" in render_kwargs["unexplored_dimensions"]

    def test_methodology_summary_formats_constraints(self, researcher):
        researcher.config = ResearchConfig(
            topic=researcher.config.topic,
            goal=researcher.config.goal,
            dimensions=researcher.config.dimensions,
            methodology=type(researcher.config.methodology)(
                question="Which option is best?",
                scope="Architect review",
                inclusion_criteria=("official docs",),
                exclusion_criteria=("forum posts",),
                preferred_source_types=("vendor docs",),
                recency_days=180,
            ),
            scoring=researcher.config.scoring,
            execution=researcher.config.execution,
        )
        summary = researcher._methodology_summary()
        assert "Which option is best?" in summary
        assert "official docs" in summary
        assert "180 days" in summary

    def test_merge_findings_queues_discovered_gaps(self, researcher):
        score = IterationScore(gaps=["Gap One", "Gap Two"])
        researcher._setup()
        researcher._merge_findings("Dim A", "findings", score)
        assert "Gap One" in researcher.discovered_dimensions
        assert "Gap Two" in researcher.discovered_dimensions

    def test_execute_research_tracks_per_backend_usage_from_candidates(self, researcher):
        class FakeStrategy:
            def execute_research(self, *args, **kwargs):
                return type("X", (), {
                    "findings": "",
                    "backend_name": "multiple",
                    "cost_usd": 0.3,
                    "per_backend_costs": {"claude-cli": 0.1, "codex-cli": 0.2},
                    "candidates": [
                        ResearchCandidate(findings="candidate a", backend_name="claude-cli", cost_usd=0.1, input_tokens=10, output_tokens=2),
                        ResearchCandidate(findings="candidate b", backend_name="codex-cli", cost_usd=0.2, input_tokens=20, output_tokens=3),
                    ],
                })()

            def post_research(self, findings, invoke, *, timeout=600):
                return None

        researcher.strategy = FakeStrategy()
        with patch("src.research_loop._render", return_value="prompt"), \
             patch("src.research_loop._select_candidate_findings", return_value="candidate b"):
            findings = researcher._execute_research("Dim A", [], "")

        assert findings == "candidate b"
        assert researcher.total_cost == pytest.approx(0.3)
        assert researcher.total_input_tokens == 30
        assert researcher.total_output_tokens == 5
        assert researcher.per_backend_costs["claude-cli"] == pytest.approx(0.1)
        assert researcher.per_backend_costs["codex-cli"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# AutoResearcher — save and log
# ---------------------------------------------------------------------------

class TestAutoResearcherSaveLog:
    def test_save_iteration(self, researcher):
        from src.scorer import IterationScore
        researcher._setup()
        researcher.iteration = 1
        researcher._save_iteration("Dim A", "findings text", IterationScore(coverage=80.0, quality=70.0, total=74.0), True)
        path = researcher.iterations_dir / "iter_001.md"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "Dim A" in content
        assert "keep" in content
        assert "findings text" in content

    def test_log_result_appends_tsv(self, researcher):
        from src.scorer import IterationScore
        researcher._setup()
        researcher.iteration = 1
        researcher._log_result("Dim A", IterationScore(total=74.0), "test hypothesis", status="keep")
        content = researcher.results_path.read_text(encoding="utf-8")
        assert "Dim A" in content
        assert "keep" in content

    def test_merge_findings(self, researcher):
        from src.scorer import IterationScore
        researcher._setup()
        researcher._merge_findings("Dim A", "New findings", IterationScore())
        assert "Dim A" in researcher.explored_dimensions
        assert "New findings" in researcher.knowledge_base
        assert researcher.kb_path.read_text(encoding="utf-8") == researcher.knowledge_base


# ---------------------------------------------------------------------------
# AutoResearcher — _call delegates to backend
# ---------------------------------------------------------------------------

class TestAutoResearcherCall:
    def test_call_delegates_to_backend(self, researcher):
        researcher.backend = MagicMock()
        researcher.backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        resp = researcher._call("prompt")
        researcher.backend.invoke.assert_called_once()
        assert resp.text == "ok"

    def test_call_passes_config_defaults(self, researcher):
        mock_backend = MagicMock()
        mock_backend.name = "claude-cli"
        mock_backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher.backend = mock_backend
        researcher._call("prompt")
        opts = mock_backend.invoke.call_args[0][1]
        assert isinstance(opts, CallOptions)
        assert opts.model == "sonnet"
        assert opts.max_budget_usd == 0.10

    def test_call_allows_overrides(self, researcher):
        mock_backend = MagicMock()
        mock_backend.name = "claude-cli"
        mock_backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)
        researcher.backend = mock_backend
        researcher._call("prompt", model="opus", max_turns=3)
        opts = mock_backend.invoke.call_args[0][1]
        assert opts.model == "opus"
        assert opts.max_turns == 3

    def test_invoke_for_strategy_enables_stream_from_execution_config(self, researcher):
        researcher.config = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(
                backend="claude-cli",
                model="sonnet",
                timeout_seconds=10,
                stream=True,
            ),
        )
        mock_backend = CapturingBackend()
        mock_backend.name = "codex-api"
        mock_backend.capabilities = get_backend("codex-api").capabilities

        researcher._invoke_for_strategy(mock_backend, "prompt")

        assert mock_backend.last_opts is not None
        assert mock_backend.last_opts.stream is True

    def test_call_with_uses_streaming_backend_for_run_progress(self, researcher):
        backend = MagicMock()
        backend.name = "litellm-api"
        backend.capabilities = get_backend("litellm-api").capabilities
        backend.parse_payload.return_value = AgentResponse(
            text="Hello world",
            cost_usd=0.0,
            is_error=False,
            input_tokens=3,
            output_tokens=2,
        )
        backend.invoke_stream.return_value = iter([
            StreamEvent(type="start"),
            StreamEvent(type="text_delta", text="Hello "),
            StreamEvent(type="text_delta", text="world"),
            StreamEvent(type="completed", raw={"response": {"output_text": "Hello world", "usage": {"input_tokens": 3, "output_tokens": 2}}}),
        ])

        with patch("sys.stdout", new_callable=io.StringIO) as stdout:
            resp = researcher._call_with(backend, "prompt", model="openai/gpt-4.1-mini", stream=True)

        backend.invoke.assert_not_called()
        backend.invoke_stream.assert_called_once()
        backend.parse_payload.assert_called_once_with(
            {"output_text": "Hello world", "usage": {"input_tokens": 3, "output_tokens": 2}}
        )
        assert resp.text == "Hello world"
        assert "[litellm-api stream]" in stdout.getvalue()
        assert "Hello world" in stdout.getvalue()

    def test_call_with_falls_back_to_invoke_when_streaming_disabled(self, researcher):
        backend = MagicMock()
        backend.name = "litellm-api"
        backend.capabilities = get_backend("litellm-api").capabilities
        backend.invoke.return_value = AgentResponse(text="ok", cost_usd=0.01, is_error=False)

        researcher._call_with(backend, "prompt", model="openai/gpt-4.1-mini", stream=False)

        backend.invoke.assert_called_once()
        backend.invoke_stream.assert_not_called()

    def test_call_with_retries_retryable_api_errors(self, researcher):
        backend = MagicMock()
        backend.name = "litellm-api"
        backend.capabilities = get_backend("litellm-api").capabilities
        researcher.config = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(
                backend="claude-cli",
                model="sonnet",
                retry_api_errors=1,
                retry_backoff_seconds=2.5,
            ),
        )
        backend.invoke.side_effect = [
            AgentResponse(
                text="",
                cost_usd=0.0,
                is_error=True,
                raw={"error": {"category": "rate_limit", "retryable": True, "provider_code": "rate_limit"}},
            ),
            AgentResponse(text="ok after retry", cost_usd=0.01, is_error=False, raw={}),
        ]

        with patch("src.orchestrator.time.sleep") as sleep_mock:
            resp = researcher._call_with(backend, "prompt", model="openai/gpt-4.1-mini")

        assert resp.text == "ok after retry"
        assert resp.raw["retry_attempts"] == 1
        assert resp.raw["retry_summary"]["categories"]["rate_limit"] == 1
        backend.invoke.assert_called()
        assert backend.invoke.call_count == 2
        sleep_mock.assert_called_once_with(2.5)

    def test_call_with_does_not_retry_non_retryable_api_errors(self, researcher):
        backend = MagicMock()
        backend.name = "litellm-api"
        backend.capabilities = get_backend("litellm-api").capabilities
        researcher.config = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(
                backend="claude-cli",
                model="sonnet",
                retry_api_errors=2,
                retry_backoff_seconds=2.5,
            ),
        )
        backend.invoke.return_value = AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=True,
            raw={"error": {"category": "auth", "retryable": False, "provider_code": "invalid_api_key"}},
        )

        with patch("src.orchestrator.time.sleep") as sleep_mock:
            resp = researcher._call_with(backend, "prompt", model="openai/gpt-4.1-mini")

        assert resp.is_error is True
        assert backend.invoke.call_count == 1
        sleep_mock.assert_not_called()

    def test_call_with_does_not_retry_tool_loops_even_when_api_retries_enabled(self, researcher):
        backend = get_backend("codex-api")
        backend.invoke = MagicMock(return_value=AgentResponse(
            text="",
            cost_usd=0.0,
            is_error=False,
            raw={
                "output": [
                    {
                        "id": "fc_123",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "missing_tool",
                        "arguments": "{}",
                    }
                ]
            },
        ))
        researcher.config = ResearchConfig(
            topic="Test topic",
            goal="Test goal",
            dimensions=("Dim A",),
            scoring=ScoringConfig(),
            execution=ExecutionConfig(
                backend="claude-cli",
                model="sonnet",
                retry_api_errors=2,
                retry_backoff_seconds=2.5,
            ),
        )

        with patch("src.orchestrator.time.sleep") as sleep_mock:
            resp = researcher._call_with(
                backend,
                "Say hi",
                model="gpt-5.4",
                tools=(
                    __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                        type="function",
                        name="echo",
                    ),
                ),
                tool_registry={"echo": lambda args: "unused"},
            )

        assert resp.is_error is True
        assert resp.raw["error"]["category"] == "tool_execution"
        assert backend.invoke.call_count == 1
        sleep_mock.assert_not_called()

    @pytest.mark.parametrize(
        ("backend_name", "model", "completed_payload", "expected_text"),
        [
            (
                "claude-api",
                "claude-sonnet-4-5",
                {"content": [{"type": "text", "text": "Hello from Claude"}], "usage": {"input_tokens": 4, "output_tokens": 3}},
                "Hello from Claude",
            ),
            (
                "gemini-api",
                "gemini-2.5-flash",
                {
                    "candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}],
                    "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 3},
                },
                "Hello from Gemini",
            ),
            (
                "copilot-api",
                "openai/gpt-4.1",
                {
                    "choices": [{"message": {"role": "assistant", "content": "Hello from GitHub Models"}}],
                    "usage": {"prompt_tokens": 4, "completion_tokens": 3},
                },
                "Hello from GitHub Models",
            ),
            (
                "bedrock-api",
                "anthropic.claude-3-5-sonnet-20240620-v1:0",
                {
                    "output": {"message": {"content": [{"text": "Hello from Bedrock"}]}},
                    "usage": {"inputTokens": 4, "outputTokens": 3},
                },
                "Hello from Bedrock",
            ),
        ],
    )
    def test_call_with_streaming_round_trips_completed_payloads(
        self,
        researcher,
        backend_name,
        model,
        completed_payload,
        expected_text,
    ):
        backend = get_backend(backend_name)
        backend.invoke_stream = MagicMock(return_value=iter([
            StreamEvent(type="start"),
            StreamEvent(type="text_delta", text="Hello "),
            StreamEvent(type="completed", raw={"response": completed_payload}),
        ]))

        with patch("sys.stdout", new_callable=io.StringIO):
            resp = researcher._call_with(backend, "prompt", model=model, stream=True)

        assert resp.text == expected_text
        backend.invoke_stream.assert_called_once()

    def test_call_with_runs_function_tool_loop_for_codex_api(self, researcher):
        backend = get_backend("codex-api")
        responses = iter([
            AgentResponse(
                text="",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "output": [
                        {
                            "id": "fc_123",
                            "type": "function_call",
                            "call_id": "call_123",
                            "name": "echo",
                            "arguments": json.dumps({"message": "hello"}),
                        }
                    ]
                },
            ),
            AgentResponse(
                text="Final answer",
                cost_usd=0.0,
                is_error=False,
                raw={"output_text": "Final answer"},
            ),
        ])
        backend.invoke = MagicMock(side_effect=lambda prompt, opts, timeout=300: next(responses))

        resp = researcher._call_with(
            backend,
            "Say hi",
            model="gpt-5.4",
            tools=(
                __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                    type="function",
                    name="echo",
                ),
            ),
            tool_registry={"echo": lambda args: f"echo:{args['message']}"},
        )

        assert resp.text == "Final answer"
        assert backend.invoke.call_count == 2

    def test_call_with_does_not_run_function_tool_loop_for_unsupported_backend(self, researcher):
        backend = get_backend("gemini-api")
        backend.invoke = MagicMock(return_value=AgentResponse(text="ok", cost_usd=0.0, is_error=False))

        resp = researcher._call_with(
            backend,
            "Say hi",
            model="gemini-2.5-flash",
            tools=(
                __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                    type="function",
                    name="echo",
                ),
            ),
            tool_registry={"echo": lambda args: "unused"},
        )

        assert resp.text == "ok"
        backend.invoke.assert_called_once()

    def test_call_with_runs_function_tool_loop_for_litellm_api(self, researcher):
        backend = get_backend("litellm-api")
        responses = iter([
            AgentResponse(
                text="",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "output": [
                        {
                            "id": "fc_123",
                            "type": "function_call",
                            "call_id": "call_123",
                            "name": "echo",
                            "arguments": json.dumps({"message": "hello"}),
                        }
                    ]
                },
            ),
            AgentResponse(
                text="LiteLLM final",
                cost_usd=0.0,
                is_error=False,
                raw={"output_text": "LiteLLM final"},
            ),
        ])
        backend.invoke = MagicMock(side_effect=lambda prompt, opts, timeout=300: next(responses))

        resp = researcher._call_with(
            backend,
            "Say hi",
            model="openai/gpt-4.1-mini",
            tools=(
                __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                    type="function",
                    name="echo",
                ),
            ),
            tool_registry={"echo": lambda args: f"echo:{args['message']}"},
        )

        assert resp.text == "LiteLLM final"
        assert backend.invoke.call_count == 2

    def test_call_with_runs_function_tool_loop_for_copilot_api(self, researcher):
        backend = get_backend("copilot-api")
        responses = iter([
            AgentResponse(
                text="",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "call_123",
                                        "type": "function",
                                        "function": {
                                            "name": "echo",
                                            "arguments": json.dumps({"message": "hello"}),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            ),
            AgentResponse(
                text="Copilot final",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Copilot final",
                            }
                        }
                    ]
                },
            ),
        ])
        backend.invoke = MagicMock(side_effect=lambda prompt, opts, timeout=300: next(responses))

        resp = researcher._call_with(
            backend,
            "Say hi",
            model="openai/gpt-4.1",
            tools=(
                __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                    type="function",
                    name="echo",
                ),
            ),
            tool_registry={"echo": lambda args: f"echo:{args['message']}"},
        )

        assert resp.text == "Copilot final"
        assert backend.invoke.call_count == 2

    def test_call_with_runs_function_tool_loop_for_claude_api(self, researcher):
        backend = get_backend("claude-api")
        responses = iter([
            AgentResponse(
                text="",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_123",
                            "name": "echo",
                            "input": {"message": "hello"},
                        }
                    ],
                    "stop_reason": "tool_use",
                },
            ),
            AgentResponse(
                text="Claude final",
                cost_usd=0.0,
                is_error=False,
                raw={"content": [{"type": "text", "text": "Claude final"}]},
            ),
        ])
        backend.invoke = MagicMock(side_effect=lambda prompt, opts, timeout=300: next(responses))

        resp = researcher._call_with(
            backend,
            "Say hi",
            model="claude-sonnet-4-5",
            tools=(
                __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                    type="function",
                    name="echo",
                ),
            ),
            tool_choice="required",
            tool_registry={"echo": lambda args: f"echo:{args['message']}"},
        )

        assert resp.text == "Claude final"
        assert backend.invoke.call_count == 2

    def test_call_with_runs_function_tool_loop_for_gemini_api(self, researcher):
        backend = get_backend("gemini-api")
        responses = iter([
            AgentResponse(
                text="",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "echo",
                                            "args": {"message": "hello"},
                                        }
                                    }
                                ],
                            }
                        }
                    ]
                },
            ),
            AgentResponse(
                text="Gemini final",
                cost_usd=0.0,
                is_error=False,
                raw={"candidates": [{"content": {"parts": [{"text": "Gemini final"}]}}]},
            ),
        ])
        backend.invoke = MagicMock(side_effect=lambda prompt, opts, timeout=300: next(responses))

        resp = researcher._call_with(
            backend,
            "Say hi",
            model="gemini-2.5-flash",
            tools=(
                __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                    type="function",
                    name="echo",
                ),
            ),
            tool_choice="required",
            tool_registry={"echo": lambda args: f"echo:{args['message']}"},
        )

        assert resp.text == "Gemini final"
        assert backend.invoke.call_count == 2

    def test_call_with_runs_function_tool_loop_for_bedrock_api(self, researcher):
        backend = get_backend("bedrock-api")
        responses = iter([
            AgentResponse(
                text="",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "output": {
                        "message": {
                            "content": [
                                {
                                    "toolUse": {
                                        "toolUseId": "toolu_123",
                                        "name": "echo",
                                        "input": {"message": "hello"},
                                    }
                                }
                            ]
                        }
                    },
                    "stopReason": "tool_use",
                    "messages": [
                        {"role": "user", "content": [{"text": "Say hi"}]},
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "toolUse": {
                                        "toolUseId": "toolu_123",
                                        "name": "echo",
                                        "input": {"message": "hello"},
                                    }
                                }
                            ],
                        },
                    ],
                },
            ),
            AgentResponse(
                text="Bedrock final",
                cost_usd=0.0,
                is_error=False,
                raw={"output": {"message": {"content": [{"text": "Bedrock final"}]}}},
            ),
        ])
        backend.invoke = MagicMock(side_effect=lambda prompt, opts, timeout=300: next(responses))

        resp = researcher._call_with(
            backend,
            "Say hi",
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            tools=(
                __import__("src.backends.types", fromlist=["ToolDefinition"]).ToolDefinition(
                    type="function",
                    name="echo",
                ),
            ),
            tool_choice="required",
            tool_registry={"echo": lambda args: f"echo:{args['message']}"},
        )

        assert resp.text == "Bedrock final"
        assert backend.invoke.call_count == 2

    def test_track_usage_accumulates_tool_loop_summary(self, researcher):
        researcher._track_usage(
            AgentResponse(
                text="ok",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "tool_loop": {
                        "backend": "codex-api",
                        "turns": 2,
                        "tool_calls": 3,
                        "tool_failures": 1,
                    },
                    "tool_trace": [
                        {
                            "backend": "codex-api",
                            "turn": 1,
                            "tool_name": "echo",
                            "call_id": "call_123",
                            "status": "success",
                        }
                    ],
                },
            ),
            "codex-api",
        )
        assert researcher._tool_loop_summary["runs"] == 1
        assert researcher._tool_loop_summary["tool_calls"] == 3
        assert researcher._tool_loop_summary["tool_failures"] == 1
        assert researcher._tool_loop_summary["per_backend"]["codex-api"]["runs"] == 1
        assert researcher._tool_loop_summary["per_backend"]["codex-api"]["tools"]["echo"]["calls"] == 1
        assert researcher._tool_loop_summary["per_tool"]["echo"]["calls"] == 1
        assert researcher._tool_trace[0]["tool_name"] == "echo"

    def test_track_usage_accumulates_retry_summary(self, researcher):
        researcher._track_usage(
            AgentResponse(
                text="ok",
                cost_usd=0.0,
                is_error=False,
                raw={
                    "retry_attempts": 2,
                    "retry_summary": {
                        "categories": {"rate_limit": 2},
                    },
                },
            ),
            "litellm-api",
        )
        assert researcher._retry_summary["total_retries"] == 2
        assert researcher._retry_summary["per_backend"]["litellm-api"] == 2
        assert researcher._retry_summary["per_category"]["rate_limit"] == 2
        assert researcher._retry_summary["per_backend_category"]["litellm-api"]["rate_limit"] == 2

    def test_write_tool_trace_artifact(self, researcher):
        researcher.output_dir.mkdir(parents=True, exist_ok=True)
        researcher._tool_trace = [
            {
                "backend": "codex-api",
                "turn": 1,
                "tool_name": "echo",
                "call_id": "call_123",
                "status": "success",
            }
        ]
        researcher._write_tool_trace_artifact()
        payload = json.loads(researcher.tool_trace_path.read_text(encoding="utf-8"))
        assert payload["entries_count"] == 1
        assert payload["entries"][0]["backend"] == "codex-api"

    def test_write_provenance_artifacts_writes_search_and_screening_logs(self, researcher):
        researcher.output_dir.mkdir(parents=True, exist_ok=True)
        researcher._claims = [
            {
                "id": "synthesis-claim-001",
                "scope": "synthesis",
                "dimension": "DX",
                "text": "Python has strong docs.",
                "claim_type": "factual",
                "confidence": "high",
                "cited_urls": ["https://docs.python.org/3/"],
            }
        ]
        researcher._citations = [
            {
                "id": "synthesis-cite-001",
                "scope": "synthesis",
                "title": "Python docs",
                "url": "https://docs.python.org/3/",
                "source_type": "official_docs",
                "source_quality_weight": 1.0,
                "retrieved_at": "2026-04-22T00:00:00Z",
            },
            {
                "id": "synthesis-cite-002",
                "scope": "synthesis",
                "title": "Random blog",
                "url": "https://example.com/blog",
                "source_type": "web",
                "source_quality_weight": 0.6,
                "retrieved_at": "2026-04-22T00:00:00Z",
            },
        ]

        researcher._write_provenance_artifacts()

        search_log = json.loads((researcher.output_dir / "search_log.json").read_text(encoding="utf-8"))
        screening_log = json.loads((researcher.output_dir / "screening_log.json").read_text(encoding="utf-8"))
        certainty = json.loads((researcher.output_dir / "certainty_tables.json").read_text(encoding="utf-8"))
        assert search_log["summary"]["sources_considered"] == 2
        assert screening_log["summary"]["included_count"] == 1
        assert screening_log["summary"]["excluded_count"] == 1
        assert certainty["summary"]["conclusions_count"] >= 1

    def test_write_provenance_artifacts_delegates_persistence(self, researcher):
        researcher.output_dir.mkdir(parents=True, exist_ok=True)
        researcher._claims = []
        researcher._citations = []

        with patch("src.orchestrator.write_provenance_artifacts_bundle") as writer:
            researcher._write_provenance_artifacts()

        writer.assert_called_once()

    def test_write_prompt_snapshot_artifact(self, researcher):
        researcher.output_dir.mkdir(parents=True, exist_ok=True)
        backend = get_backend("codex-api")

        with patch.object(
            backend,
            "invoke",
            return_value=AgentResponse(text="ok", cost_usd=0.0, is_error=False),
        ):
            researcher._call_with(backend, "Investigate Python packaging.", model="gpt-5.4")

        researcher._write_prompt_snapshot_artifact()

        payload = json.loads((researcher.output_dir / "prompt_snapshot.json").read_text(encoding="utf-8"))
        assert payload["entries_count"] == 1
        entry = payload["entries"][0]
        assert entry["backend"] == "codex-api"
        assert entry["model"] == "gpt-5.4"
        assert entry["prompt"] == "Investigate Python packaging."
        assert entry["prompt_sha256"]
