"""Research / refine / plan configuration types.

Public API entry point for the config package. Submodules:

- ``common``: Shared types every workflow composes — ProviderConfig,
  BackendsConfig, StrategyConfig, ExecutionConfig + the parsers that
  build them.
- ``security``: SecurityConfig and the sandbox-policy enum sets.
- ``hitl``: HitlConfig and the intervention-mode enum.
- ``research``: ResearchConfig and its companion types (Methodology,
  Scoring, Discovery, Judge, Evaluation, Reporting, OutputStyleOverrides).
- ``document``: DocumentConfig + persona/artifact/source-file types.
- ``plan``: PlanConfig + plan-specific persona type.

Every symbol is re-exported here so existing
``from src.config import X`` call sites keep working unchanged.
"""

from __future__ import annotations

from ..backends import VALID_BACKENDS
from ..output_style import VALID_OUTPUT_STYLES
from .common import (
    VALID_STRATEGIES,
    BackendsConfig,
    ExecutionConfig,
    ProviderConfig,
    StrategyConfig,
    _build_backends_config_from_raw,
    _build_strategy_config_from_raw,
    _parse_backends_config,
    _parse_execution_config,
    _parse_providers_config,
    _resolve_backends_and_providers,
    _validate_backend_name,
    _validate_provider_references,
)
from .document import (
    VALID_PERSONA_MODES,
    ArtifactConfig,
    DocumentConfig,
    PersonaConfig,
    SourceFileConfig,
    _parse_source_files,
)
from .hitl import VALID_INTERVENTION_MODES, HitlConfig, _parse_hitl_config
from .plan import PlanConfig, PlanPersonaConfig
from .research import (
    DiscoveryConfig,
    EvaluationConfig,
    JudgeConfig,
    MethodologyConfig,
    OutputStyleOverrides,
    ReportingConfig,
    ResearchConfig,
    ScoringConfig,
    ScoringWeights,
)
from .security import (
    VALID_CONTENT_TRUST,
    VALID_SANDBOX_BACKENDS,
    VALID_SANDBOX_FILESYSTEM_ACCESS,
    VALID_SANDBOX_MODES,
    VALID_SANDBOX_NETWORK_ACCESS,
    VALID_SANDBOX_SCOPES,
    VALID_TOOL_EXECUTION_MODES,
    ContainerBackendConfig,
    SandboxConfig,
    SecurityConfig,
    _parse_security_config,
)

__all__ = [
    # Common
    "BackendsConfig",
    "ExecutionConfig",
    "ProviderConfig",
    "StrategyConfig",
    "VALID_BACKENDS",
    "VALID_STRATEGIES",
    "_build_backends_config_from_raw",
    "_build_strategy_config_from_raw",
    "_parse_backends_config",
    "_parse_execution_config",
    "_parse_providers_config",
    "_resolve_backends_and_providers",
    "_validate_backend_name",
    "_validate_provider_references",
    # Security
    "ContainerBackendConfig",
    "SandboxConfig",
    "SecurityConfig",
    "VALID_CONTENT_TRUST",
    "VALID_SANDBOX_BACKENDS",
    "VALID_SANDBOX_FILESYSTEM_ACCESS",
    "VALID_SANDBOX_MODES",
    "VALID_SANDBOX_NETWORK_ACCESS",
    "VALID_SANDBOX_SCOPES",
    "VALID_TOOL_EXECUTION_MODES",
    "_parse_security_config",
    # HITL
    "HitlConfig",
    "VALID_INTERVENTION_MODES",
    "_parse_hitl_config",
    # Research
    "DiscoveryConfig",
    "EvaluationConfig",
    "JudgeConfig",
    "MethodologyConfig",
    "OutputStyleOverrides",
    "ReportingConfig",
    "ResearchConfig",
    "ScoringConfig",
    "ScoringWeights",
    # Document
    "ArtifactConfig",
    "DocumentConfig",
    "PersonaConfig",
    "SourceFileConfig",
    "VALID_PERSONA_MODES",
    "_parse_source_files",
    # Plan
    "PlanConfig",
    "PlanPersonaConfig",
    # Output styles (re-exported for convenience)
    "VALID_OUTPUT_STYLES",
]
