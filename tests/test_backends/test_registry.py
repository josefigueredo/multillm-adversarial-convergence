"""Tests for src.backends.registry — get_backend, get_backends, and the
T4.6 registration-validation contract (non-empty name + no collision)."""

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
from src.backends.base import Backend
from src.backends.types import BackendCapabilities, PromptMode


def _concrete_attrs(name: str) -> dict:
    """Minimal attribute dict for a concrete Backend subclass."""
    return {
        "name": name,
        "cli_executable": lambda self: "x",
        "prompt_mode": lambda self: PromptMode.STDIN,
        "build_command": lambda self, opts: [],
        "parse_response": lambda self, stdout: None,
        "capabilities": BackendCapabilities(),
    }


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


class TestRegistrationValidation:
    """T4.6: concrete subclasses must declare a non-empty unique name."""

    def test_missing_name_raises(self):
        attrs = _concrete_attrs("_dummy")
        del attrs["name"]
        with pytest.raises(TypeError, match="non-empty string ``name``"):
            type("_NoName", (Backend,), attrs)

    def test_empty_name_raises(self):
        with pytest.raises(TypeError, match="non-empty string ``name``"):
            type("_EmptyName", (Backend,), _concrete_attrs(""))

    def test_collision_with_existing_class_raises(self):
        """Two distinct classes claiming the same name → ValueError on the
        second registration. ``claude-cli`` is already taken by ClaudeBackend."""
        with pytest.raises(ValueError, match="already registered"):
            type("_Imposter", (Backend,), _concrete_attrs("claude-cli"))

    def test_abstract_base_skipped(self):
        """``_abstract_base = True`` opts the class out of registration —
        used by intermediate code-sharing layers like ApiBackend."""
        intermediate = type("_Intermediate", (Backend,), {"_abstract_base": True})
        assert intermediate.__name__ == "_Intermediate"
        # Subsequent concrete subclass with a fresh name still registers.
        concrete = type("_Child", (intermediate,),
                        _concrete_attrs("_t4_6_intermediate_child"))
        assert concrete.name == "_t4_6_intermediate_child"
