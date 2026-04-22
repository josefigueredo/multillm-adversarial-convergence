"""Tests for src.strategy — multi-backend research strategies."""

from unittest.mock import MagicMock

import pytest

from src.backends import AgentResponse
from src.config import BackendsConfig, StrategyConfig
from src.strategy import (
    AdversarialStrategy,
    CritiqueResult,
    EnsembleStrategy,
    ParallelStrategy,
    ResearchCandidate,
    ResearchResult,
    SerialStrategy,
    SingleStrategy,
    SpecialistStrategy,
    get_strategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backend(name: str) -> MagicMock:
    b = MagicMock()
    b.name = name
    return b


def _make_invoke(text: str = "findings", cost: float = 0.1):
    """Return a mock invoke callback that returns a fixed response."""
    def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
        return AgentResponse(text=text, cost_usd=cost, is_error=False)
    return invoke


def _make_invoke_per_backend(responses: dict[str, str]):
    """Return an invoke callback that returns different text per backend name."""
    def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
        text = responses.get(backend.name, "")
        return AgentResponse(text=text, cost_usd=0.1, is_error=False)
    return invoke


def _make_invoke_error():
    def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
        return AgentResponse(text="", cost_usd=0.0, is_error=True)
    return invoke


def _strategy(
    cls,
    primary="claude-cli",
    research=("claude-cli",),
    judge="",
    utility="",
    **strategy_kwargs,
):
    backends_config = BackendsConfig(
        primary=primary, research=tuple(research), judge=judge, utility=utility,
    )
    strategy_config = StrategyConfig(**strategy_kwargs)
    backend_names = backends_config.all_backend_names()
    backends = {name: _make_backend(name) for name in backend_names}
    return cls(backends_config, strategy_config, backends)


# ---------------------------------------------------------------------------
# get_strategy factory
# ---------------------------------------------------------------------------

class TestGetStrategy:
    def test_valid_strategies(self):
        for name in ("single", "ensemble", "adversarial", "parallel", "serial", "specialist"):
            bc = BackendsConfig()
            sc = StrategyConfig()
            backends = {"claude-cli": _make_backend("claude-cli")}
            s = get_strategy(name, bc, sc, backends)
            assert s.name == name

    def test_unknown_strategy(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("bogus", BackendsConfig(), StrategyConfig(), {})


# ---------------------------------------------------------------------------
# SingleStrategy
# ---------------------------------------------------------------------------

class TestSingleStrategy:
    def test_execute_success(self):
        s = _strategy(SingleStrategy)
        result = s.execute_research("prompt", _make_invoke("hello"))
        assert result.findings == "hello"
        assert result.backend_name == "claude-cli"
        assert result.cost_usd == 0.1

    def test_execute_error(self):
        s = _strategy(SingleStrategy)
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""

    def test_describe(self):
        s = _strategy(SingleStrategy)
        assert "single" in s.describe()
        assert "claude-cli" in s.describe()

    def test_hypothesis_backend(self):
        s = _strategy(SingleStrategy)
        assert s.get_hypothesis_backend().name == "claude-cli"

    def test_judge_backend_fallback(self):
        s = _strategy(SingleStrategy)
        assert s.get_judge_backend().name == "claude-cli"

    def test_no_post_research(self):
        s = _strategy(SingleStrategy)
        assert s.post_research("findings", _make_invoke()) is None


# ---------------------------------------------------------------------------
# EnsembleStrategy
# ---------------------------------------------------------------------------

class TestEnsembleStrategy:
    def test_parallel_execution_returns_candidates(self):
        s = _strategy(EnsembleStrategy, research=("claude-cli", "codex-cli"), stagger_seconds=0)
        invoke = _make_invoke_per_backend({"claude-cli": "short", "codex-cli": "much longer findings"})
        result = s.execute_research("prompt", invoke)
        assert result.findings == ""
        assert result.backend_name == "multiple"
        assert [candidate.backend_name for candidate in result.candidates] == ["claude-cli", "codex-cli"]

    def test_all_fail(self):
        s = _strategy(EnsembleStrategy, research=("claude-cli", "codex-cli"), stagger_seconds=0)
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""
        assert result.backend_name == "none"

    def test_union_mode_still_returns_candidates(self):
        s = _strategy(EnsembleStrategy, research=("claude-cli", "codex-cli"), merge_mode="union", stagger_seconds=0)
        invoke = _make_invoke_per_backend({"claude-cli": "finding A", "codex-cli": "finding B"})
        result = s.execute_research("prompt", invoke)
        assert result.findings == ""
        assert len(result.candidates) == 2

    def test_judge_isolation(self):
        s = _strategy(EnsembleStrategy, research=("codex-cli", "gemini-cli"), judge="claude-cli")
        assert s.get_judge_backend().name == "claude-cli"
        assert "claude-cli" not in [b.name for b in s.research_backends]

    def test_describe(self):
        s = _strategy(EnsembleStrategy, research=("claude-cli", "codex-cli"), judge="gemini-cli")
        desc = s.describe()
        assert "ensemble" in desc
        assert "claude-cli" in desc
        assert "codex-cli" in desc


# ---------------------------------------------------------------------------
# AdversarialStrategy
# ---------------------------------------------------------------------------

class TestAdversarialStrategy:
    def test_execute_uses_first_research_backend(self):
        s = _strategy(AdversarialStrategy, research=("codex-cli", "claude-cli"))
        result = s.execute_research("prompt", _make_invoke("research output"))
        assert result.findings == "research output"
        assert result.backend_name == "codex-cli"

    def test_post_research_critique(self):
        s = _strategy(AdversarialStrategy, research=("codex-cli", "claude-cli"))
        critique = s.post_research("findings text", _make_invoke("errors found"))
        assert critique is not None
        assert critique.critique == "errors found"
        assert critique.backend_name == "claude-cli"

    def test_post_research_empty_findings(self):
        s = _strategy(AdversarialStrategy, research=("codex-cli", "claude-cli"))
        assert s.post_research("", _make_invoke()) is None

    def test_describe(self):
        s = _strategy(AdversarialStrategy, research=("codex-cli", "claude-cli"))
        desc = s.describe()
        assert "adversarial" in desc


# ---------------------------------------------------------------------------
# ParallelStrategy
# ---------------------------------------------------------------------------

class TestParallelStrategy:
    def test_returns_candidates(self):
        s = _strategy(ParallelStrategy, research=("claude-cli", "codex-cli", "gemini-cli"), stagger_seconds=0)
        invoke = _make_invoke_per_backend({
            "claude-cli": "a",
            "codex-cli": "bb",
            "gemini-cli": "ccc",
        })
        result = s.execute_research("prompt", invoke)
        assert result.findings == ""
        assert result.backend_name == "multiple"
        assert len(result.candidates) == 3

    def test_all_fail(self):
        s = _strategy(ParallelStrategy, research=("claude-cli", "codex-cli"), stagger_seconds=0)
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""


# ---------------------------------------------------------------------------
# SerialStrategy
# ---------------------------------------------------------------------------

class TestSerialStrategy:
    def test_draft_then_refine(self):
        s = _strategy(SerialStrategy, research=("gemini-cli", "claude-cli"), stagger_seconds=0)
        call_count = [0]
        def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentResponse(text="draft", cost_usd=0.05, is_error=False)
            return AgentResponse(text="refined", cost_usd=0.15, is_error=False)

        result = s.execute_research("prompt", invoke)
        assert result.findings == "refined"
        assert "gemini-cli" in result.backend_name
        assert "claude-cli" in result.backend_name
        assert result.cost_usd == pytest.approx(0.20)

    def test_draft_fails_returns_empty(self):
        s = _strategy(SerialStrategy, research=("gemini-cli", "claude-cli"))
        result = s.execute_research("prompt", _make_invoke_error())
        assert result.findings == ""

    def test_refine_fails_returns_draft(self):
        s = _strategy(SerialStrategy, research=("gemini-cli", "claude-cli"))
        call_count = [0]
        def invoke(backend, prompt, *, allowed_tools="", max_turns=0, timeout=0):
            call_count[0] += 1
            if call_count[0] == 1:
                return AgentResponse(text="draft", cost_usd=0.05, is_error=False)
            return AgentResponse(text="", cost_usd=0.0, is_error=True)

        result = s.execute_research("prompt", invoke)
        assert result.findings == "draft"

    def test_single_backend_fallback(self):
        s = _strategy(SerialStrategy, research=("claude-cli",))
        result = s.execute_research("prompt", _make_invoke("solo"))
        assert result.findings == "solo"


# ---------------------------------------------------------------------------
# SpecialistStrategy
# ---------------------------------------------------------------------------

class TestSpecialistStrategy:
    def test_routing_code_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude-cli", "codex-cli", "gemini-cli"))
        backend = s.route_dimension("SDK implementation and code examples")
        assert backend.name == "codex-cli"

    def test_routing_pricing_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude-cli", "codex-cli", "gemini-cli"))
        backend = s.route_dimension("pricing comparison and market overview")
        assert backend.name == "gemini-cli"

    def test_routing_architecture_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude-cli", "codex-cli", "gemini-cli"))
        backend = s.route_dimension("architecture trade-off analysis")
        assert backend.name == "claude-cli"

    def test_routing_fallback(self):
        s = _strategy(SpecialistStrategy, research=("claude-cli", "codex-cli"))
        backend = s.route_dimension("random unrelated topic")
        assert backend.name == "claude-cli"  # falls back to primary

    def test_execute_with_dimension(self):
        s = _strategy(SpecialistStrategy, research=("claude-cli", "codex-cli"))
        result = s.execute_research(
            "prompt", _make_invoke("coded"),
            dimension="code implementation",
        )
        assert result.findings == "coded"


# ---------------------------------------------------------------------------
# Backend role helpers
# ---------------------------------------------------------------------------

class TestBackendRoles:
    def test_utility_fallback_to_primary(self):
        s = _strategy(SingleStrategy, primary="claude-cli", utility="")
        assert s.get_compress_backend().name == "claude-cli"

    def test_utility_explicit(self):
        s = _strategy(SingleStrategy, primary="claude-cli", utility="gemini-cli")
        assert s.get_compress_backend().name == "gemini-cli"

    def test_judge_fallback_to_primary(self):
        s = _strategy(SingleStrategy, primary="claude-cli", judge="")
        assert s.get_judge_backend().name == "claude-cli"

    def test_judge_explicit(self):
        s = _strategy(EnsembleStrategy, primary="claude-cli", research=("codex-cli",), judge="gemini-cli")
        assert s.get_judge_backend().name == "gemini-cli"

    def test_synthesize_uses_primary(self):
        s = _strategy(SingleStrategy, primary="codex-cli")
        assert s.get_synthesize_backend().name == "codex-cli"
