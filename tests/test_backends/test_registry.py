"""Tests for src.backends.registry — get_backend, get_backends."""

import pytest

from src.backends import (
    BedrockApiBackend,
    ClaudeApiBackend,
    ClaudeBackend,
    CodexApiBackend,
    CodexBackend,
    CopilotApiBackend,
    CopilotBackend,
    GeminiApiBackend,
    GeminiBackend,
    LiteLLMApiBackend,
    canonical_backend_name,
    get_backend,
    get_backends,
)


class TestGetBackend:
    def test_claude(self):
        assert isinstance(get_backend("claude-cli"), ClaudeBackend)

    def test_codex(self):
        assert isinstance(get_backend("codex-cli"), CodexBackend)

    def test_gemini(self):
        assert isinstance(get_backend("gemini-cli"), GeminiBackend)

    def test_copilot(self):
        assert isinstance(get_backend("copilot-cli"), CopilotBackend)

    def test_claude_api(self):
        assert isinstance(get_backend("claude-api"), ClaudeApiBackend)

    def test_codex_api(self):
        assert isinstance(get_backend("codex-api"), CodexApiBackend)

    def test_gemini_api(self):
        assert isinstance(get_backend("gemini-api"), GeminiApiBackend)

    def test_litellm_api(self):
        assert isinstance(get_backend("litellm-api"), LiteLLMApiBackend)

    def test_bedrock_api(self):
        assert isinstance(get_backend("bedrock-api"), BedrockApiBackend)

    def test_copilot_api(self):
        assert isinstance(get_backend("copilot-api"), CopilotApiBackend)

    def test_invalid(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("chatgpt")

    def test_legacy_name_is_invalid(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("claude")


class TestGetBackends:
    def test_multiple(self):
        backends = get_backends({"claude-cli", "codex-cli"})
        assert len(backends) == 2
        assert isinstance(backends["claude-cli"], ClaudeBackend)
        assert isinstance(backends["codex-cli"], CodexBackend)

    def test_invalid_in_set(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backends({"claude-cli", "invalid"})


class TestCanonicalBackendName:
    def test_explicit_name_maps_to_itself(self):
        assert canonical_backend_name("claude-cli") == "claude-cli"
        assert canonical_backend_name("codex-cli") == "codex-cli"
        assert canonical_backend_name("gemini-cli") == "gemini-cli"
        assert canonical_backend_name("copilot-cli") == "copilot-cli"

    def test_invalid_name_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            canonical_backend_name("nope")
