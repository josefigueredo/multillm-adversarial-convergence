"""Tests for explicit CLI aliases and provider metadata."""

from src.backends import get_backend


def test_cli_aliases_resolve_to_direct_cli_providers():
    for name in ("claude-cli", "codex-cli", "gemini-cli", "copilot-cli"):
        backend = get_backend(name)
        assert backend.capabilities.transport == "cli"
        assert backend.capabilities.provider_kind == "direct"
