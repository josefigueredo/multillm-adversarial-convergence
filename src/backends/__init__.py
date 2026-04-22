"""AI CLI backend abstraction layer.

Re-exports all public symbols so callers can use::

    from src.backends import ClaudeBackend, get_backend, AgentResponse
"""

# Import concrete backends to trigger auto-registration.
from .bedrock_api import BedrockApiBackend
from .claude_api import ClaudeApiBackend
from .claude import ClaudeBackend
from .codex_api import CodexApiBackend
from .codex import CodexBackend
from .copilot_api import CopilotApiBackend
from .copilot import CopilotBackend
from .gemini_api import GeminiApiBackend
from .gemini import GeminiBackend
from .litellm_api import LiteLLMApiBackend
from .openai_direct_api import OpenAIDirectResponsesApiBackend
from .openai_compatible_api import OpenAICompatibleResponsesApiBackend

# Re-export public API.
from .base import Backend
from .base_api import ApiBackend
from .jsonl import parse_jsonl_last_result
from .registry import canonical_backend_name, get_backend, get_backends, valid_backends

# Generated from registry after all backends are imported above.
VALID_BACKENDS = valid_backends()
from .types import (
    CLAUDE_SHORTNAMES,
    AgentResponse,
    BackendCapabilities,
    CallOptions,
    PromptMode,
    StreamEvent,
)

__all__ = [
    "AgentResponse",
    "ApiBackend",
    "Backend",
    "BackendCapabilities",
    "BedrockApiBackend",
    "CallOptions",
    "ClaudeApiBackend",
    "CLAUDE_SHORTNAMES",
    "ClaudeBackend",
    "canonical_backend_name",
    "CodexApiBackend",
    "CodexBackend",
    "CopilotApiBackend",
    "CopilotBackend",
    "GeminiApiBackend",
    "GeminiBackend",
    "LiteLLMApiBackend",
    "OpenAIDirectResponsesApiBackend",
    "OpenAICompatibleResponsesApiBackend",
    "PromptMode",
    "StreamEvent",
    "VALID_BACKENDS",
    "get_backend",
    "get_backends",
    "parse_jsonl_last_result",
]
