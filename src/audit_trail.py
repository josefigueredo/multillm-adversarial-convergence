"""Structured execution audit trail for runtime traceability."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator


_IGNORED_FILENAMES = {"run.log", "audit_trail.jsonl"}


class AuditTrailWriter:
    """Append-only JSONL event writer with step-level filesystem diffs."""

    def __init__(self, path: Path, *, mode: str, run_id: str) -> None:
        self.path = path
        self.mode = mode
        self.run_id = run_id

    def emit(self, event: str, **fields: Any) -> None:
        """Append one structured event to the audit trail."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "mode": self.mode,
            "run_id": self.run_id,
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @contextmanager
    def step(
        self,
        step: str,
        *,
        artifact_root: Path | None = None,
        **fields: Any,
    ) -> Iterator[None]:
        """Record a step start/completion/failure and changed files."""
        before = self._snapshot(artifact_root)
        started = perf_counter()
        self.emit("step_started", step=step, **fields)
        try:
            yield
        except Exception as exc:
            duration_ms = round((perf_counter() - started) * 1000, 3)
            created, updated = self._diff(before, self._snapshot(artifact_root))
            self._emit_file_events(created, updated, **fields)
            self.emit(
                "step_failed",
                step=step,
                duration_ms=duration_ms,
                created_files=created,
                updated_files=updated,
                error=str(exc),
                error_type=type(exc).__name__,
                **fields,
            )
            raise

        duration_ms = round((perf_counter() - started) * 1000, 3)
        created, updated = self._diff(before, self._snapshot(artifact_root))
        self._emit_file_events(created, updated, **fields)
        self.emit(
            "step_completed",
            step=step,
            duration_ms=duration_ms,
            created_files=created,
            updated_files=updated,
            **fields,
        )

    def _emit_file_events(self, created: list[str], updated: list[str], **fields: Any) -> None:
        for rel_path in created:
            self.emit("file_written", path=rel_path, action="created", **fields)
        for rel_path in updated:
            self.emit("file_written", path=rel_path, action="updated", **fields)

    def _snapshot(self, root: Path | None) -> dict[str, tuple[int, int]]:
        if root is None or not root.exists():
            return {}
        snapshot: dict[str, tuple[int, int]] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.name in _IGNORED_FILENAMES:
                continue
            stat = path.stat()
            snapshot[str(path.relative_to(root))] = (stat.st_size, stat.st_mtime_ns)
        return snapshot

    @staticmethod
    def _diff(
        before: dict[str, tuple[int, int]],
        after: dict[str, tuple[int, int]],
    ) -> tuple[list[str], list[str]]:
        created = sorted(path for path in after if path not in before)
        updated = sorted(
            path
            for path, meta in after.items()
            if path in before and before[path] != meta
        )
        return created, updated


class NullAuditTrailWriter:
    """No-op writer used by tests or code paths that do not need tracing."""

    def emit(self, event: str, **fields: Any) -> None:
        return None

    @contextmanager
    def step(self, step: str, *, artifact_root: Path | None = None, **fields: Any) -> Iterator[None]:
        yield
