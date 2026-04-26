"""ImplementRunner — orchestrator for the adversarial implement loop.

MM09: Safe Adversarial Implement Mode — Step 3.

:class:`ImplementRunner` is the top-level entry point for ``autoresearch
implement``.  It mirrors the shape of DocumentRefiner and PlanRefiner:

- explicit target repo contract (ImplementTarget via ImplementConfig)
- output directory for artifacts (patches, critiques, audit trail)
- ``run()`` returns an integer exit code (0 = ok / stopped)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .audit_trail import NullAuditTrailWriter
from .implement_loop import (
    ImplementConfig,
    ImplementCycleContext,
    ImplementTask,
    TaskState,
    _should_stop_implement,
    run_implement_cycle,
)

log = logging.getLogger("autoresearch")


class ImplementRunner:
    """Orchestrate the adversarial implement loop for a single code task.

    Parameters
    ----------
    config:
        Implement config providing target, task description, and cycle settings.
    backends:
        Backend mapping from role name to :class:`~src.backends.Backend`.
    output_dir:
        Directory for output artifacts (patches, critiques, audit trail).
    resume:
        If ``True``, attempt to resume from a previous paused run.
    """

    def __init__(
        self,
        config: ImplementConfig,
        backends: dict[str, Any],
        output_dir: Path,
        *,
        resume: bool = False,
    ) -> None:
        self._config = config
        self._backends = backends
        self._output_dir = output_dir
        self._resume = resume
        self.state: TaskState | None = None

    def run(self, *, _strategy: Any = None) -> int:
        """Execute the implement loop.

        Parameters
        ----------
        _strategy:
            Test hook — inject a pre-built (mock) strategy instead of
            constructing one from backends.  Should NOT be used in production.

        Returns
        -------
        int
            Exit code: 0 on success (convergence or max_cycles reached).
            1 when required backends are missing and no injected strategy.
        """
        if _strategy is None:
            if not self._backends:
                log.error(
                    "implement requires at least one backend to be configured "
                    "(none provided — pass --config with backends or use --dry-run)"
                )
                return 1
            from .implement_strategy import ImplementStrategy
            strategy = ImplementStrategy(self._config, self._backends)
        else:
            strategy = _strategy

        task = ImplementTask(description=self._config.task_description)
        state = TaskState(task=task)
        self.state = state

        noop = lambda *a, **kw: None
        ctx = ImplementCycleContext(
            call_with=noop,
            invoke_for_strategy=noop,
            track_usage=noop,
            track_cost=noop,
            target=self._config.target,
            audit_trail=NullAuditTrailWriter(),
        )

        while not _should_stop_implement(state, self._config):
            valid_count, stale_count, deferred_count = run_implement_cycle(
                state, ctx, strategy
            )
            log.info(
                "[implement][cycle %d] valid=%d stale=%d deferred=%d clean_streak=%d",
                state.cycle, valid_count, stale_count, deferred_count,
                state.consecutive_clean_cycles,
            )

        # Distinguish true convergence from max-cycles stop or boundary violation
        if state.boundary_violations:
            log.error(
                "[implement] stopped due to %d boundary violation(s): %s",
                len(state.boundary_violations), "; ".join(state.boundary_violations),
            )
            return 1

        state.converged = (
            state.consecutive_clean_cycles >= self._config.convergence_cycles
        )
        log.info(
            "[implement] done — cycles=%d converged=%s patches=%d critiques=%d",
            state.cycle, state.converged, len(state.patches), len(state.critiques),
        )
        return 0
