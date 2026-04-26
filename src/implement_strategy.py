"""ImplementStrategy — adversarial builder/challenger/verifier/arbitrator for code tasks.

MM09: Safe Adversarial Implement Mode — Step 1 scaffold.

All methods raise :class:`NotImplementedError` in this scaffold.
Step 3 will add prompt wiring and backend invocation.
"""

from __future__ import annotations

from typing import Any

from .implement_loop import CandidatePatch, ImplementTarget, ImplementTask


class ImplementStrategy:
    """Adversarial strategy for code implementation tasks.

    Roles map to the same proven pattern used in ``ConvergeStrategy``
    (document) and ``PlanStrategy`` (plan):

    - **Builder** — generates the candidate patch
    - **Challenger** — critiques the patch for correctness, regressions, etc.
    - **Verifier** — classifies each critique (valid / stale / deferred)
    - **Arbitrator** — produces a revised patch from accepted critiques

    All phase methods receive explicit :class:`~src.implement_loop.ImplementTarget`
    context so that policy constraints can be enforced as the implementation
    progresses (Step 4 concern).

    Parameters
    ----------
    config:
        Implement config (``ImplementConfig`` once Step 2 defines it; ``Any``
        for now to keep the scaffold import-clean).
    backends:
        Backend mapping from role name to :class:`~src.backends.Backend`.
    """

    def __init__(self, config: Any, backends: dict[str, Any]) -> None:
        self._config = config
        self._backends = backends

    def run_builder(
        self,
        task: ImplementTask,
        target: ImplementTarget,
    ) -> CandidatePatch:
        """Generate an initial candidate patch for *task* against *target*.

        Raises
        ------
        NotImplementedError
            Scaffold stub — implemented in MM09 Step 3.
        """
        raise NotImplementedError("run_builder not yet implemented (MM09 Step 3)")

    def run_challenger(
        self,
        patch: CandidatePatch,
        task: ImplementTask,
        target: ImplementTarget,
    ) -> list[Any]:
        """Critique *patch* for correctness, architecture fit, and regressions.

        Returns
        -------
        list[Any]
            Raw critiques (structured in Step 3).

        Raises
        ------
        NotImplementedError
            Scaffold stub — implemented in MM09 Step 3.
        """
        raise NotImplementedError("run_challenger not yet implemented (MM09 Step 3)")

    def run_verifier(
        self,
        patch: CandidatePatch,
        critiques: list[Any],
    ) -> list[Any]:
        """Classify each critique in *critiques* against *patch*.

        Returns
        -------
        list[Any]
            Verified critiques with status classification.

        Raises
        ------
        NotImplementedError
            Scaffold stub — implemented in MM09 Step 3.
        """
        raise NotImplementedError("run_verifier not yet implemented (MM09 Step 3)")

    def run_arbitrator(
        self,
        patch: CandidatePatch,
        critiques: list[Any],
        task: ImplementTask,
        target: ImplementTarget,
    ) -> CandidatePatch:
        """Produce a revised :class:`~src.implement_loop.CandidatePatch` from accepted critiques.

        Raises
        ------
        NotImplementedError
            Scaffold stub — implemented in MM09 Step 3.
        """
        raise NotImplementedError("run_arbitrator not yet implemented (MM09 Step 3)")
