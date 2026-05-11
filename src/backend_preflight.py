"""Live readiness probes for backend CLI adapters."""

from __future__ import annotations

import dataclasses
import logging
import re
from dataclasses import dataclass
from typing import Iterable

from .backend_options import (
    apply_backend_capabilities,
    build_call_options,
    resolve_backend_model,
)
from .backends import Backend, CallOptions
from .config import ExecutionConfig, ProviderConfig

log = logging.getLogger("autoresearch")

PREFLIGHT_PROMPT = "Respond with exactly OK."
EXPECTED_PREFLIGHT_RESPONSE = "OK"
_OK_RESPONSE_RE = re.compile(r'^["\'`“”‘’]*\s*OK\s*[.!]*\s*["\'`“”‘’]*$', re.IGNORECASE)


@dataclass(frozen=True)
class PreflightResult:
    """Outcome of one backend readiness probe."""

    backend_name: str
    adapter_name: str
    model: str
    skipped: bool = False
    ok: bool = False
    reason: str = ""
    response_snippet: str = ""


def preflight_backend(
    *,
    backend_name: str,
    backend: Backend,
    opts: CallOptions,
    timeout: int,
) -> PreflightResult:
    """Probe a CLI backend with a tiny live model call."""
    if backend.capabilities.transport != "cli":
        return PreflightResult(
            backend_name=backend_name,
            adapter_name=backend.name,
            model=opts.model,
            skipped=True,
            ok=True,
            reason="non-cli backend",
        )

    probe_opts = apply_backend_capabilities(
        backend,
        CallOptions(
            model=opts.model,
            system_prompt="",
            stream=False,
            tools=(),
            tool_choice="none",
            allowed_tools="",
            max_turns=1,
            max_budget_usd=0.0,
            json_schema=None,
            working_directory=opts.working_directory,
            sanitize_environment=opts.sanitize_environment,
            process_env=opts.process_env,
        ),
    )

    resp = backend.invoke(PREFLIGHT_PROMPT, probe_opts, timeout=timeout)
    response_text = " ".join((resp.text or "").strip().split())
    if not resp.is_error and _is_expected_ok_response(response_text):
        return PreflightResult(
            backend_name=backend_name,
            adapter_name=backend.name,
            model=probe_opts.model,
            ok=True,
        )

    reason = "backend returned an error" if resp.is_error else "unexpected response"
    return PreflightResult(
        backend_name=backend_name,
        adapter_name=backend.name,
        model=probe_opts.model,
        ok=False,
        reason=reason,
        response_snippet=(resp.text or "")[:500],
    )


def _is_expected_ok_response(response_text: str) -> bool:
    """Return true for harmless CLI formatting around the required OK probe."""
    return bool(_OK_RESPONSE_RE.fullmatch(response_text))


def preflight_backends(
    *,
    backends: dict[str, Backend],
    execution: ExecutionConfig,
    provider_lookup: dict[str, ProviderConfig] | None = None,
    backend_names: Iterable[str] | None = None,
) -> list[PreflightResult]:
    """Probe each unique configured backend instance once."""
    if not execution.backend_preflight:
        return []

    names = list(backend_names or backends.keys())
    provider_lookup = provider_lookup or {}
    results: list[PreflightResult] = []
    seen: set[int] = set()

    for backend_name in names:
        backend = backends[backend_name]
        identity = id(backend)
        if identity in seen:
            continue
        seen.add(identity)

        provider = backend.provider_config
        if provider is None:
            provider = provider_lookup.get(backend_name)
        config_model = provider.model if provider and provider.model else execution.model
        model = resolve_backend_model(backend, config_model)
        # Start from a normal CallOptions (so working_directory /
        # sanitize_environment / process_env follow execution+provider rules)
        # then strip everything the probe doesn't need: no tools, no streaming,
        # no system prompt, max_turns=1, zero budget cap.
        base_opts = build_call_options(execution, provider=provider)
        opts = dataclasses.replace(
            base_opts,
            model=model,
            system_prompt="",
            stream=False,
            tools=(),
            tool_choice="none",
            allowed_tools="",
            max_turns=1,
            max_budget_usd=0.0,
            json_schema=None,
        )
        result = preflight_backend(
            backend_name=backend_name,
            backend=backend,
            opts=opts,
            timeout=execution.backend_preflight_timeout_seconds,
        )
        results.append(result)

    return results


def require_preflight_success(results: list[PreflightResult]) -> None:
    """Raise a concise runtime error when any preflight probe fails."""
    failures = [result for result in results if not result.ok and not result.skipped]
    if not failures:
        for result in results:
            if result.skipped:
                log.info("Backend preflight skipped for %s (%s): %s", result.backend_name, result.adapter_name, result.reason)
            else:
                log.info("Backend preflight passed for %s (%s, model=%s).", result.backend_name, result.adapter_name, result.model)
        return

    for result in failures:
        log.error(
            "Backend preflight failed for %s (%s, model=%s): %s. Response: %.500s",
            result.backend_name,
            result.adapter_name,
            result.model,
            result.reason,
            result.response_snippet or "(empty)",
        )

    first = failures[0]
    raise RuntimeError(
        "Backend preflight failed for "
        f"{first.backend_name} ({first.adapter_name}, model={first.model}): "
        f"{first.reason}"
    )
