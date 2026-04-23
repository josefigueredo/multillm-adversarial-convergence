"""Tests for dry-run planning summaries."""

from pathlib import Path

from src.config import BackendsConfig, ExecutionConfig, ProviderConfig, ResearchConfig, ScoringConfig
from src.config import DocumentConfig, PlanConfig
from src.dry_run import (
    build_convergence_dry_run_summary,
    build_dry_run_summary,
    render_dry_run_summary,
)


def _config(*, providers: dict[str, ProviderConfig] | None = None, backends: BackendsConfig | None = None) -> ResearchConfig:
    return ResearchConfig(
        topic="Dry topic",
        goal="Dry goal",
        dimensions=("Evidence",),
        scoring=ScoringConfig(),
        execution=ExecutionConfig(
            max_iterations=2,
            backend="claude-cli",
            model="sonnet",
            strategy="ensemble",
            backends=backends or BackendsConfig(primary="claude-cli", research=("claude-cli", "codex-cli")),
            stream=True,
            retry_api_errors=2,
            system_prompt="Be rigorous.",
        ),
        providers=providers or {},
    )


def test_build_dry_run_summary_includes_output_and_artifacts(tmp_path: Path):
    output_dir = tmp_path / "out"
    summary = build_dry_run_summary(
        config=_config(),
        config_path=tmp_path / "test.yaml",
        output_dir=output_dir,
        backends={"claude-cli": object(), "codex-cli": object()},
    )

    assert summary["output_dir"] == str(output_dir.resolve())
    assert summary["artifacts"]["manifest"].endswith("run_manifest.json")
    assert summary["artifacts"]["metrics"].endswith("metrics.json")
    assert summary["artifacts"]["prompt_snapshot"].endswith("prompt_snapshot.json")


def test_build_dry_run_summary_lists_provider_instances(tmp_path: Path):
    providers = {
        "primary_reasoner": ProviderConfig(adapter="claude-api", model="claude-sonnet-4-5"),
        "fast_research": ProviderConfig(adapter="litellm-api", model="gpt-5.4"),
    }
    backends = BackendsConfig(primary="primary_reasoner", research=("primary_reasoner", "fast_research"))
    summary = build_dry_run_summary(
        config=_config(providers=providers, backends=backends),
        config_path=tmp_path / "provider.yaml",
        output_dir=tmp_path / "out",
        backends={"primary_reasoner": object(), "fast_research": object()},
    )

    assert summary["providers_count"] == 2
    assert summary["providers"]["primary_reasoner"]["adapter"] == "claude-api"
    assert summary["resolved_backends"] == ["fast_research", "primary_reasoner"]
    assert summary["backend_roles"]["primary"] == "primary_reasoner"
    assert summary["backend_roles"]["research"] == ["primary_reasoner", "fast_research"]


def test_render_dry_run_summary_mentions_flags(tmp_path: Path):
    summary = build_dry_run_summary(
        config=_config(),
        config_path=tmp_path / "test.yaml",
        output_dir=tmp_path / "out",
        backends={"claude-cli": object(), "codex-cli": object()},
    )

    rendered = render_dry_run_summary(summary)

    assert "DRY RUN OK" in rendered
    assert "research backends: claude-cli, codex-cli" in rendered
    assert "stream: enabled" in rendered
    assert "retry_api_errors: 2" in rendered
    assert "system_prompt: configured" in rendered


def test_build_convergence_dry_run_summary_for_refine(tmp_path: Path):
    config = DocumentConfig(
        topic="Doc topic",
        goal="Doc goal",
        primary_artifact="PRD.md",
    )
    summary = build_convergence_dry_run_summary(
        mode="refine",
        config=config,
        config_path=tmp_path / "doc.yaml",
        output_dir=tmp_path / "out",
        backends={"claude-cli": object(), "gemini-cli": object()},
    )

    assert summary["mode"] == "refine"
    assert summary["primary_artifact"] == "PRD.md"
    assert summary["resolved_backends"] == ["claude-cli", "gemini-cli"]


def test_build_convergence_dry_run_summary_for_plan(tmp_path: Path):
    config = PlanConfig(
        topic="Plan topic",
        goal="Plan goal",
        primary_artifact="PLAN.md",
    )
    summary = build_convergence_dry_run_summary(
        mode="plan",
        config=config,
        config_path=tmp_path / "plan.yaml",
        output_dir=tmp_path / "out",
        backends={"claude-cli": object()},
    )

    rendered = render_dry_run_summary(summary)

    assert summary["mode"] == "plan"
    assert "mode: plan" in rendered
    assert "primary artifact: PLAN.md" in rendered
