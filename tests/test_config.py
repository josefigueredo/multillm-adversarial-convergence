"""Tests for src.config — YAML loading and dataclass validation."""

import textwrap
from pathlib import Path

import pytest

from src.config import BackendsConfig, EvaluationConfig, ExecutionConfig, MethodologyConfig, OutputStyleOverrides, ProviderConfig, ReportingConfig, ResearchConfig, ScoringConfig, StrategyConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "full.yaml"
    p.write_text(textwrap.dedent("""\
        research:
          topic: "Compare API gateways"
          goal: "Architect-level comparison"
          dimensions:
            - "REST vs HTTP"
            - "WebSocket"
            - "Auth options"
          scoring:
            min_dimensions_per_iteration: 2
            target_dimensions_total: 5
            evidence_types:
              - comparison_table
              - pricing_data
          execution:
            max_iterations: 10
            compress_every: 3
            allowed_tools: "WebSearch,Read"
            max_turns: 5
            timeout_seconds: 120
            model: opus
            max_budget_per_call: 1.25
            lightweight_mode: true
            isolate_backend_context: false
            sanitize_backend_env: false
    """), encoding="utf-8")
    return p


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "minimal.yaml"
    p.write_text(textwrap.dedent("""\
        research:
          topic: "Minimal topic"
    """), encoding="utf-8")
    return p


@pytest.fixture
def no_goal_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "no_goal.yaml"
    p.write_text(textwrap.dedent("""\
        research:
          topic: "Topic without goal"
          dimensions:
            - "Dim A"
    """), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# ScoringConfig defaults
# ---------------------------------------------------------------------------

class TestScoringConfig:
    def test_defaults(self):
        sc = ScoringConfig()
        assert sc.min_dimensions_per_iteration == 1
        assert sc.target_dimensions_total == 10
        assert len(sc.evidence_types) == 5
        assert "comparison_table" in sc.evidence_types

    def test_frozen(self):
        sc = ScoringConfig()
        with pytest.raises(AttributeError):
            sc.min_dimensions_per_iteration = 99


class TestMethodologyConfig:
    def test_defaults(self):
        mc = MethodologyConfig()
        assert mc.question == ""
        assert mc.scope == ""
        assert mc.review_type == ""
        assert mc.inclusion_criteria == ()
        assert mc.search_sources == ()
        assert mc.stopping_criteria == ()
        assert mc.stopping_rationale == ""
        assert mc.scoring_rationale == ""
        assert mc.recency_days == 0


class TestEvaluationConfig:
    def test_defaults(self):
        ec = EvaluationConfig()
        assert ec.benchmark_id == ""
        assert ec.run_baselines is False
        assert ec.expected_dimensions == ()
        assert ec.required_keywords == ()
        assert ec.reference_runs == ()
        assert ec.semantic_calibration is True
        assert ec.semantic_review is False


class TestReportingConfig:
    def test_defaults(self):
        rc = ReportingConfig()
        assert rc.export_html is True
        assert rc.export_pdf is False
        assert rc.report_title == ""
        assert rc.output_style == "default"
        assert rc.style_overrides == OutputStyleOverrides()
        assert rc.capture_raw_backend_outputs is False
        assert rc.raw_backend_output_max_chars == 20000
        assert rc.raw_backend_output_redact is True


# ---------------------------------------------------------------------------
# ExecutionConfig defaults
# ---------------------------------------------------------------------------

class TestExecutionConfig:
    def test_defaults(self):
        ec = ExecutionConfig()
        assert ec.max_iterations == 0
        assert ec.compress_every == 5
        assert ec.model == "sonnet"
        assert ec.system_prompt == ""
        assert ec.stream is False
        assert ec.retry_api_errors == 0
        assert ec.retry_backoff_seconds == 1.0
        assert ec.max_budget_per_call == 0.50
        assert ec.lightweight_mode is False
        assert ec.isolate_backend_context is True
        assert ec.sanitize_backend_env is True
        assert ec.timeout_seconds == 600
        assert ec.max_turns == 10
        assert "WebSearch" in ec.allowed_tools

    def test_frozen(self):
        ec = ExecutionConfig()
        with pytest.raises(AttributeError):
            ec.model = "opus"


# ---------------------------------------------------------------------------
# ResearchConfig.from_yaml
# ---------------------------------------------------------------------------

class TestResearchConfigFromYaml:
    def test_full_config(self, full_yaml: Path):
        cfg = ResearchConfig.from_yaml(full_yaml)
        assert cfg.topic == "Compare API gateways"
        assert cfg.goal == "Architect-level comparison"
        assert cfg.dimensions == ("REST vs HTTP", "WebSocket", "Auth options")
        assert cfg.scoring.min_dimensions_per_iteration == 2
        assert cfg.scoring.target_dimensions_total == 5
        assert cfg.scoring.evidence_types == ("comparison_table", "pricing_data")
        assert cfg.execution.max_iterations == 10
        assert cfg.execution.compress_every == 3
        assert cfg.execution.allowed_tools == "WebSearch,Read"
        assert cfg.execution.max_turns == 5
        assert cfg.execution.timeout_seconds == 120
        assert cfg.execution.model == "opus"
        assert cfg.execution.system_prompt == ""
        assert cfg.execution.stream is False
        assert cfg.execution.max_budget_per_call == 1.25
        assert cfg.execution.lightweight_mode is True
        assert cfg.execution.isolate_backend_context is False
        assert cfg.execution.sanitize_backend_env is False

    def test_methodology_config(self, tmp_path: Path):
        p = tmp_path / "methodology.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              methodology:
                question: "What is the best option?"
                scope: "Architectural decision support"
                inclusion_criteria:
                  - official docs
                exclusion_criteria:
                  - anonymous forum posts
                preferred_source_types:
                  - vendor docs
                  - standards
                search_sources:
                  - official docs
                  - benchmark corpora
                stopping_criteria:
                  - cover all configured dimensions
                  - stop when no new evidence appears
                stopping_rationale: "Bound cost while preserving coverage."
                scoring_rationale: "Prefer evidence-backed, actionable synthesis."
                review_type: "systematic_review"
                recency_days: 180
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.methodology.question == "What is the best option?"
        assert cfg.methodology.scope == "Architectural decision support"
        assert cfg.methodology.review_type == "systematic_review"
        assert cfg.methodology.inclusion_criteria == ("official docs",)
        assert cfg.methodology.exclusion_criteria == ("anonymous forum posts",)
        assert cfg.methodology.preferred_source_types == ("vendor docs", "standards")
        assert cfg.methodology.search_sources == ("official docs", "benchmark corpora")
        assert cfg.methodology.stopping_criteria == (
            "cover all configured dimensions",
            "stop when no new evidence appears",
        )
        assert cfg.methodology.stopping_rationale == "Bound cost while preserving coverage."
        assert cfg.methodology.scoring_rationale == "Prefer evidence-backed, actionable synthesis."
        assert cfg.methodology.recency_days == 180

    def test_evaluation_config(self, tmp_path: Path):
        p = tmp_path / "evaluation.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              evaluation:
                benchmark_id: "bench-001"
                run_baselines: true
                expected_dimensions:
                  - "Cost"
                  - "Security"
                required_keywords:
                  - "pricing"
                  - "latency"
                reference_runs:
                  - "output/run-a"
                  - "output/run-b"
                semantic_calibration: false
                semantic_review: true
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.evaluation.benchmark_id == "bench-001"
        assert cfg.evaluation.run_baselines is True
        assert cfg.evaluation.expected_dimensions == ("Cost", "Security")
        assert cfg.evaluation.required_keywords == ("pricing", "latency")
        assert cfg.evaluation.reference_runs == ("output/run-a", "output/run-b")
        assert cfg.evaluation.semantic_calibration is False
        assert cfg.evaluation.semantic_review is True

    def test_reporting_config(self, tmp_path: Path):
        p = tmp_path / "reporting.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              reporting:
                export_html: false
                export_pdf: true
                report_title: "Custom Research Report"
                output_style: "paper"
                style_overrides:
                  include_executive_summary: false
                  include_comparison_table: true
                  include_methodology: true
                  include_limitations: true
                  include_next_actions: true
                  section_order: "recommendation_first"
                  recommendation_mode: "decision_only"
                  citation_mode: "references_section"
                capture_raw_backend_outputs: true
                raw_backend_output_max_chars: 1234
                raw_backend_output_redact: false
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.reporting.export_html is False
        assert cfg.reporting.export_pdf is True
        assert cfg.reporting.report_title == "Custom Research Report"
        assert cfg.reporting.output_style == "paper"
        assert cfg.reporting.style_overrides.include_executive_summary is False
        assert cfg.reporting.style_overrides.include_comparison_table is True
        assert cfg.reporting.style_overrides.include_methodology is True
        assert cfg.reporting.style_overrides.include_limitations is True
        assert cfg.reporting.style_overrides.include_next_actions is True
        assert cfg.reporting.style_overrides.section_order == "recommendation_first"
        assert cfg.reporting.style_overrides.recommendation_mode == "decision_only"
        assert cfg.reporting.style_overrides.citation_mode == "references_section"
        assert cfg.reporting.capture_raw_backend_outputs is True
        assert cfg.reporting.raw_backend_output_max_chars == 1234
        assert cfg.reporting.raw_backend_output_redact is False

    def test_reporting_output_style_supports_new_profiles(self, tmp_path: Path):
        p = tmp_path / "reporting_profiles.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              reporting:
                output_style: "executive_brief"
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.reporting.output_style == "executive_brief"

    def test_reporting_output_style_must_be_valid(self, tmp_path: Path):
        p = tmp_path / "reporting_style_invalid.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              reporting:
                output_style: "marketing_brochure"
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid reporting.output_style"):
            ResearchConfig.from_yaml(p)

    def test_reporting_style_override_recommendation_mode_must_be_valid(self, tmp_path: Path):
        p = tmp_path / "reporting_override_invalid.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              reporting:
                style_overrides:
                  recommendation_mode: "narrative_poetry"
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid reporting.style_overrides.recommendation_mode"):
            ResearchConfig.from_yaml(p)

    def test_reporting_style_override_citation_mode_must_be_valid(self, tmp_path: Path):
        p = tmp_path / "reporting_override_invalid_citation.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              reporting:
                style_overrides:
                  citation_mode: "footnotes"
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid reporting.style_overrides.citation_mode"):
            ResearchConfig.from_yaml(p)

    def test_reporting_style_override_section_order_must_be_valid(self, tmp_path: Path):
        p = tmp_path / "reporting_override_invalid_order.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              reporting:
                style_overrides:
                  section_order: "chronological_epic"
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid reporting.style_overrides.section_order"):
            ResearchConfig.from_yaml(p)

    def test_reporting_raw_backend_output_max_chars_must_be_positive(self, tmp_path: Path):
        p = tmp_path / "reporting_invalid.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              reporting:
                raw_backend_output_max_chars: 0
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="raw_backend_output_max_chars must be positive"):
            ResearchConfig.from_yaml(p)

    def test_minimal_config_uses_defaults(self, minimal_yaml: Path):
        cfg = ResearchConfig.from_yaml(minimal_yaml)
        assert cfg.topic == "Minimal topic"
        assert cfg.goal == "Minimal topic"  # falls back to topic
        assert cfg.dimensions == ()
        assert cfg.scoring == ScoringConfig()
        assert cfg.execution.model == "sonnet"
        assert cfg.execution.system_prompt == ""
        assert cfg.execution.max_iterations == 0

    def test_execution_system_prompt_parses(self, tmp_path: Path):
        p = tmp_path / "system_prompt.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "System prompt test"
              execution:
                system_prompt: "You are precise."
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.system_prompt == "You are precise."

    def test_execution_stream_parses(self, tmp_path: Path):
        p = tmp_path / "stream.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Streaming test"
              execution:
                stream: true
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.stream is True

    def test_execution_api_retry_settings_parse(self, tmp_path: Path):
        p = tmp_path / "retry.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Retry test"
              execution:
                retry_api_errors: 2
                retry_backoff_seconds: 3.5
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.retry_api_errors == 2
        assert cfg.execution.retry_backoff_seconds == 3.5

    def test_goal_falls_back_to_topic(self, no_goal_yaml: Path):
        cfg = ResearchConfig.from_yaml(no_goal_yaml)
        assert cfg.goal == "Topic without goal"
        assert cfg.dimensions == ("Dim A",)

    def test_explicit_cli_aliases_are_valid_backends(self, tmp_path: Path):
        p = tmp_path / "aliases.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Alias test"
              execution:
                backend: claude-cli
                strategy: ensemble
                backends:
                  primary: claude-cli
                  research:
                    - codex-cli
                    - gemini-cli
                  judge: claude-cli
                  utility: gemini-cli
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.backend == "claude-cli"
        assert cfg.execution.backends.primary == "claude-cli"
        assert cfg.execution.backends.research == ("codex-cli", "gemini-cli")
        assert cfg.execution.backends.utility == "gemini-cli"

    def test_provider_instances_parse_and_roles_reference_instances(self, tmp_path: Path):
        p = tmp_path / "providers.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Provider test"
              execution:
                strategy: ensemble
                providers:
                  primary_reasoner:
                    adapter: claude-cli
                    model: opus
                  fast_research:
                    adapter: codex-cli
                    model: gpt-5.4
                  cheap_utility:
                    adapter: gemini-cli
                    model: gemini-2.5-flash
                backends:
                  primary: primary_reasoner
                  research:
                    - primary_reasoner
                    - fast_research
                  judge: primary_reasoner
                  utility: cheap_utility
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.providers["primary_reasoner"] == ProviderConfig(adapter="claude-cli", model="opus")
        assert cfg.providers["fast_research"] == ProviderConfig(adapter="codex-cli", model="gpt-5.4")
        assert cfg.execution.backends.primary == "primary_reasoner"
        assert cfg.execution.backends.research == ("primary_reasoner", "fast_research")
        assert cfg.execution.backends.utility == "cheap_utility"

    def test_provider_role_reference_must_exist(self, tmp_path: Path):
        p = tmp_path / "bad_provider_ref.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Provider test"
              execution:
                providers:
                  primary_reasoner:
                    adapter: claude-cli
                backends:
                  primary: missing_instance
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Unknown provider instance"):
            ResearchConfig.from_yaml(p)

    def test_provider_adapter_must_be_valid(self, tmp_path: Path):
        p = tmp_path / "bad_provider_adapter.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Provider test"
              execution:
                providers:
                  primary_reasoner:
                    adapter: no-such-adapter
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid provider adapter"):
            ResearchConfig.from_yaml(p)

    def test_api_provider_instances_are_valid(self, tmp_path: Path):
        p = tmp_path / "api_providers.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "API Provider test"
              execution:
                providers:
                  claude_direct:
                    adapter: claude-api
                    model: claude-sonnet-4-5
                  codex_direct:
                    adapter: codex-api
                    model: gpt-5.4
                    base_url: https://litellm.example.com
                  gemini_direct:
                    adapter: gemini-api
                    model: gemini-2.5-flash
                  gateway_fast:
                    adapter: litellm-api
                    model: openai/gpt-4.1-mini
                    base_url: http://localhost:4000
                  github_models:
                    adapter: copilot-api
                    model: openai/gpt-4.1
                    organization: acme
                    api_version: 2026-03-10
                  aws_foundation:
                    adapter: bedrock-api
                    model: anthropic.claude-3-5-sonnet-20240620-v1:0
                    region: us-east-1
                    aws_profile: sandbox
                backends:
                  primary: claude_direct
                  research:
                    - codex_direct
                    - gateway_fast
                  judge: claude_direct
                  utility: gemini_direct
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.providers["claude_direct"] == ProviderConfig(adapter="claude-api", model="claude-sonnet-4-5")
        assert cfg.providers["codex_direct"] == ProviderConfig(
            adapter="codex-api",
            model="gpt-5.4",
            base_url="https://litellm.example.com",
        )
        assert cfg.providers["gemini_direct"] == ProviderConfig(adapter="gemini-api", model="gemini-2.5-flash")
        assert cfg.providers["gateway_fast"] == ProviderConfig(
            adapter="litellm-api",
            model="openai/gpt-4.1-mini",
            base_url="http://localhost:4000",
        )
        assert cfg.providers["github_models"] == ProviderConfig(
            adapter="copilot-api",
            model="openai/gpt-4.1",
            organization="acme",
            api_version="2026-03-10",
        )
        assert cfg.providers["aws_foundation"] == ProviderConfig(
            adapter="bedrock-api",
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            region="us-east-1",
            aws_profile="sandbox",
        )

    def test_legacy_backend_name_is_invalid(self, tmp_path: Path):
        p = tmp_path / "legacy.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Legacy test"
              execution:
                backend: claude
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid backend 'claude'"):
            ResearchConfig.from_yaml(p)

    def test_missing_topic_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("research:\n  goal: 'no topic'\n", encoding="utf-8")
        with pytest.raises(ValueError, match="topic"):
            ResearchConfig.from_yaml(p)

    def test_empty_file_raises(self, tmp_path: Path):
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="YAML mapping"):
            ResearchConfig.from_yaml(p)

    def test_missing_research_key_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("other_key: value\n", encoding="utf-8")
        with pytest.raises(ValueError, match="research"):
            ResearchConfig.from_yaml(p)

    def test_invalid_backend_raises(self, tmp_path: Path):
        p = tmp_path / "bad_backend.yaml"
        p.write_text("research:\n  topic: test\n  execution:\n    backend: chatgpt\n", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid backend"):
            ResearchConfig.from_yaml(p)

    def test_example_github_models_config_parses(self):
        cfg = ResearchConfig.from_yaml(Path("configs/example_github_models.yaml"))
        assert cfg.providers["github_models"].adapter == "copilot-api"
        assert cfg.providers["gateway_fast"].adapter == "litellm-api"

    def test_example_bedrock_config_parses(self):
        cfg = ResearchConfig.from_yaml(Path("configs/example_bedrock.yaml"))
        assert cfg.providers["aws_foundation"].adapter == "bedrock-api"
        assert cfg.providers["gateway_fast"].adapter == "litellm-api"

    def test_example_direct_api_config_parses(self):
        cfg = ResearchConfig.from_yaml(Path("configs/example_direct_api.yaml"))
        assert cfg.providers["anthropic_primary"].adapter == "claude-api"
        assert cfg.providers["openai_research"].adapter == "codex-api"
        assert cfg.providers["google_utility"].adapter == "gemini-api"

    def test_example_mixed_cli_api_config_parses(self):
        cfg = ResearchConfig.from_yaml(Path("configs/example_mixed_cli_api.yaml"))
        assert cfg.providers["primary_cli"].adapter == "claude-cli"
        assert cfg.providers["research_api"].adapter == "codex-api"
        assert cfg.providers["utility_gateway"].adapter == "litellm-api"

    def test_example_litellm_only_config_parses(self):
        cfg = ResearchConfig.from_yaml(Path("configs/example_litellm_only.yaml"))
        assert cfg.providers["primary_gateway"].adapter == "litellm-api"
        assert cfg.providers["research_gateway"].adapter == "litellm-api"
        assert cfg.providers["utility_gateway"].adapter == "litellm-api"

    def test_valid_backends(self, tmp_path: Path):
        for backend in ("claude-cli", "codex-cli", "gemini-cli", "copilot-cli"):
            p = tmp_path / f"{backend}.yaml"
            p.write_text(f"research:\n  topic: test\n  execution:\n    backend: {backend}\n", encoding="utf-8")
            cfg = ResearchConfig.from_yaml(p)
            assert cfg.execution.backend == backend

    def test_negative_budget_raises(self, tmp_path: Path):
        p = tmp_path / "bad_budget.yaml"
        p.write_text("research:\n  topic: test\n  execution:\n    max_budget_per_call: -1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="non-negative"):
            ResearchConfig.from_yaml(p)

    def test_zero_timeout_raises(self, tmp_path: Path):
        p = tmp_path / "bad_timeout.yaml"
        p.write_text("research:\n  topic: test\n  execution:\n    timeout_seconds: 0\n", encoding="utf-8")
        with pytest.raises(ValueError, match="positive"):
            ResearchConfig.from_yaml(p)

    def test_frozen(self, minimal_yaml: Path):
        cfg = ResearchConfig.from_yaml(minimal_yaml)
        with pytest.raises(AttributeError):
            cfg.topic = "changed"


# ---------------------------------------------------------------------------
# Multi-backend config
# ---------------------------------------------------------------------------

class TestMultiBackendConfig:
    def test_defaults(self):
        bc = BackendsConfig()
        assert bc.primary == "claude-cli"
        assert bc.research == ("claude-cli",)
        assert bc.judge_or_primary == "claude-cli"
        assert bc.utility_or_primary == "claude-cli"

    def test_all_backend_names(self):
        bc = BackendsConfig(primary="claude-cli", research=("codex-cli", "gemini-cli"), judge="claude-cli", utility="gemini-cli")
        names = bc.all_backend_names()
        assert names == {"claude-cli", "codex-cli", "gemini-cli"}

    def test_strategy_config_defaults(self):
        sc = StrategyConfig()
        assert sc.merge_mode == "best"
        assert sc.merge_threshold == 40.0
        assert sc.critique_depth == "standard"
        assert sc.refiner_sees_draft is True
        assert sc.max_parallel == 3
        assert sc.stagger_seconds == 5

    def test_backward_compat_single_backend(self, minimal_yaml: Path):
        cfg = ResearchConfig.from_yaml(minimal_yaml)
        assert cfg.execution.strategy == "single"
        assert cfg.execution.backends.primary == "claude-cli"
        assert cfg.execution.backends.research == ("claude-cli",)

    def test_ensemble_config(self, tmp_path: Path):
        p = tmp_path / "ensemble.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test ensemble"
              execution:
                backend: claude-cli
                strategy: ensemble
                backends:
                  primary: claude-cli
                  research:
                    - codex-cli
                    - gemini-cli
                  judge: claude-cli
                  utility: gemini-cli
                strategy_config:
                  merge_mode: union
                  stagger_seconds: 10
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.strategy == "ensemble"
        assert cfg.execution.backends.primary == "claude-cli"
        assert cfg.execution.backends.research == ("codex-cli", "gemini-cli")
        assert cfg.execution.backends.judge == "claude-cli"
        assert cfg.execution.backends.utility == "gemini-cli"
        assert cfg.execution.strategy_config.merge_mode == "union"
        assert cfg.execution.strategy_config.stagger_seconds == 10

    def test_invalid_strategy_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                strategy: bogus
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid strategy"):
            ResearchConfig.from_yaml(p)

    def test_invalid_research_backend_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                strategy: ensemble
                backends:
                  primary: claude-cli
                  research:
                    - chatgpt
        """), encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid research backend"):
            ResearchConfig.from_yaml(p)

    def test_research_as_string(self, tmp_path: Path):
        p = tmp_path / "str.yaml"
        p.write_text(textwrap.dedent("""\
            research:
              topic: "Test"
              execution:
                strategy: single
                backends:
                  primary: claude-cli
                  research: codex-cli
        """), encoding="utf-8")
        cfg = ResearchConfig.from_yaml(p)
        assert cfg.execution.backends.research == ("codex-cli",)
