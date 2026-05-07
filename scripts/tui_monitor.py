#!/usr/bin/env python3
"""Terminal monitor for adversarial-convergence research runs.

Two modes:
  live    — tail audit_trail.jsonl in real time as the run executes
  replay  — read the whole file, auto-advance frame by frame

The display mirrors the in-browser dashboard at docs/showcase/dashboard.html
but renders in the terminal via rich:

    ┌─ Adversarial Convergence — <run> ──────────────── live ──┐
    │ iter N/M   state STEP   backend X   dim Y                │
    ├──────────────────────────┬───────────────────────────────┤
    │ State machine (active   │ Score progression (sparklines)│
    │  step highlighted)      │                               │
    │                         ├───────────────────────────────┤
    │                         │ Dimensions covered grid       │
    │                         ├───────────────────────────────┤
    │                         │ Cost & calls                  │
    └─────────────────────────┴───────────────────────────────┘

Usage:
    python scripts/tui_monitor.py output/<run>/                # auto-detect
    python scripts/tui_monitor.py output/<run>/ --live         # force live
    python scripts/tui_monitor.py output/<run>/ --replay       # force replay
    python scripts/tui_monitor.py --scripted                   # demo data
    python scripts/tui_monitor.py output/<run>/ --replay-speed 0.3  # fast replay
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Iterable

from rich.align import Align
from rich.box import ROUNDED, SIMPLE
from rich.columns import Columns
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# ---------------------------------------------------------------------------
# Constants — colors mirror docs/showcase/dashboard.html where possible
# ---------------------------------------------------------------------------

# rich uses standard ANSI color names; chosen to match the dashboard palette.
COLOR_PRIMARY = "deep_sky_blue3"
COLOR_RESEARCH = "cyan3"
COLOR_CRITIQUE = "medium_purple3"
COLOR_JUDGE = "medium_purple3"
COLOR_DECIDE = "dark_orange"
COLOR_KEEP = "green3"
COLOR_DISCARD = "red3"
COLOR_COMPRESS = "cyan3"
COLOR_SYNTH = "deep_sky_blue3"
COLOR_MUTED = "grey50"
COLOR_ACCENT = "yellow1"
COLOR_TEXT = "grey85"

SPARK_BARS = "▁▂▃▄▅▆▇█"

# Step-name → state-machine label.  Step names emitted by the orchestrator
# (extracted by inspecting audit_trail.jsonl from real runs).
STEP_TO_STATE: dict[str, str] = {
    "hypothesise": "HYPOTHESISE",
    "hypothesize": "HYPOTHESISE",  # spelling variant
    "execute_research": "EXECUTE",
    "critique": "CRITIQUE",
    "score_iteration": "SCORE",
    "score": "SCORE",
    "decide": "DECIDE",
    "merge_findings": "KEEP",
    "persist_iteration_markdown": "PERSIST",
    "append_results_row": "LOG",
    "compress_knowledge_base": "COMPRESS",
}

STATE_COLOR: dict[str, str] = {
    "HYPOTHESISE": COLOR_PRIMARY,
    "EXECUTE": COLOR_RESEARCH,
    "CRITIQUE": COLOR_CRITIQUE,
    "SCORE": COLOR_JUDGE,
    "DECIDE": COLOR_DECIDE,
    "KEEP": COLOR_KEEP,
    "DISCARD": COLOR_DISCARD,
    "PERSIST": COLOR_MUTED,
    "LOG": COLOR_MUTED,
    "COMPRESS": COLOR_COMPRESS,
    "SYNTHESIZE": COLOR_SYNTH,
    "(idle)": COLOR_MUTED,
}

# Vertical state-machine layout — order shown top-to-bottom.
STATE_FLOW = [
    "HYPOTHESISE",
    "EXECUTE",
    "CRITIQUE",
    "SCORE",
    "DECIDE",
]


# ---------------------------------------------------------------------------
# RunState — accumulates everything we want to render
# ---------------------------------------------------------------------------

@dataclass
class IterRecord:
    iter: int
    dimension: str = ""
    heuristic: float | None = None
    quality: float | None = None
    total: float | None = None
    decision: str = ""  # KEEP / DISCARD / aborted


@dataclass
class RunState:
    run_id: str = "(unknown)"
    topic: str = ""
    strategy: str = ""
    started_at: float | None = None
    last_event_at: float | None = None
    current_iter: int = 0
    current_state: str = "(idle)"
    current_dim: str = "—"
    current_backend: str = "—"
    iters: dict[int, IterRecord] = field(default_factory=dict)
    chart_points: list[tuple[int, float, float, float]] = field(default_factory=list)
    dimensions_covered: set[str] = field(default_factory=set)
    fallback_events: list[str] = field(default_factory=list)
    finished: bool = False
    # Loaded from effective_config.json at startup (with safe defaults).
    target_dimensions: int = 0
    configured_dimensions: list[str] = field(default_factory=list)
    # Real call counter: incremented per ``step_started`` event whose
    # ``backend`` field is set (one event per backend invocation).
    backend_calls: int = 0
    # Authoritative score breakdowns by iteration, loaded from results.tsv
    # at startup.  Empty when results.tsv is missing — chart_points then
    # carry only the total_score from iteration_completed events.
    score_breakdowns: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    # Tail buffer of meaningful events for the live log panel.  Capped so
    # long-running observers don't accumulate unbounded memory.  Each entry
    # is ``(ts_str, kind, summary)`` where kind drives row colouring.
    recent_events: Deque[tuple[str, str, str]] = field(
        default_factory=lambda: deque(maxlen=12)
    )

    def upsert_iter(self, n: int) -> IterRecord:
        if n not in self.iters:
            self.iters[n] = IterRecord(iter=n)
        return self.iters[n]

    def _upsert_chart_point(self, point: tuple[int, float, float, float]) -> None:
        """Replace an existing chart point for the same iteration, otherwise append.
        Keeps the chart idempotent under replay (events seen multiple times) and
        consistent with seeding from results.tsv."""
        iter_n = point[0]
        for i, existing in enumerate(self.chart_points):
            if existing[0] == iter_n:
                self.chart_points[i] = point
                return
        self.chart_points.append(point)
        self.chart_points.sort(key=lambda p: p[0])

    def seed_chart_from_breakdowns(self) -> None:
        """Pre-populate chart_points from ``score_breakdowns`` so iterations
        whose ``iteration_completed`` audit event was never emitted (e.g.,
        SIGKILL during the post-iteration compress) still appear in the chart.
        Safe to call multiple times — _upsert_chart_point dedupes."""
        for iter_n, (cov, qual, total) in sorted(self.score_breakdowns.items()):
            self._upsert_chart_point((iter_n, cov, qual, total))

    def _push_log(self, kind: str, summary: str, ts: str = "") -> None:
        """Append one row to the event tail buffer.  ``kind`` drives colour."""
        # Trim ts to HH:MM:SS for compactness; tolerate missing or odd shapes.
        ts_short = ""
        if ts and len(ts) >= 19 and ts[10] == "T":
            ts_short = ts[11:19]
        self.recent_events.append((ts_short, kind, summary))

    def apply_event(self, ev: dict) -> None:
        """Mutate state from one audit event.  Keeps logic in one place so
        live-tail and replay both go through the same code path."""
        self.last_event_at = time.time()
        evt = ev.get("event", "")
        ts = ev.get("ts", "")

        if evt == "run_started":
            self.run_id = ev.get("run_id", self.run_id)
            self.topic = ev.get("topic", self.topic)
            self.strategy = ev.get("strategy", self.strategy)
            if not self.started_at:
                self.started_at = time.time()
            self._push_log("info", f"run started · strategy {self.strategy}", ts)

        elif evt == "iteration_started":
            self.current_iter = ev.get("iteration", self.current_iter)
            self.upsert_iter(self.current_iter)
            self.current_state = "(idle)"
            self._push_log("iter", f"iter {self.current_iter} started", ts)

        elif evt == "step_started":
            step = ev.get("step", "")
            self.current_state = STEP_TO_STATE.get(step, step.upper().replace("_", " "))
            iter_n = ev.get("iteration")
            if iter_n is not None:
                self.current_iter = iter_n
            dim = ev.get("dimension")
            if dim:
                self.current_dim = _short_dim(dim)
                rec = self.upsert_iter(self.current_iter)
                rec.dimension = self.current_dim
            backend = ev.get("backend")
            if backend:
                self.current_backend = backend
                # Real call counter: each step_started with a backend field is
                # one backend invocation (replaces the earlier "~5 per iter"
                # heuristic which was made up).
                self.backend_calls += 1
                self._push_log(
                    "step",
                    f"iter {self.current_iter} → {self.current_state.lower()} · {backend[:18]}",
                    ts,
                )

        elif evt == "step_completed":
            # Stay on the same state badge until the next step_started so the
            # operator sees a stable label between events.
            pass

        elif evt == "iteration_completed":
            iter_n = ev.get("iteration", self.current_iter)
            rec = self.upsert_iter(iter_n)
            # Audit trail emits lowercase ``status`` ("keep"/"discard"); the
            # rest of the TUI compares against uppercase tokens.  Normalise
            # at the boundary so downstream code stays simple.
            rec.decision = (ev.get("status", "") or "").upper()
            total = ev.get("total_score")
            if total is not None:
                rec.total = float(total)
                # Prefer authoritative breakdown from results.tsv when available;
                # fall back to total-only for both lines so we don't fabricate
                # numbers.  ``audit_trail.jsonl::iteration_completed`` only carries
                # ``total_score`` -- coverage / quality columns live in
                # ``results.tsv``.  When the breakdown isn't loaded (e.g., live
                # tail before the row is written), heuristic and quality both
                # equal total — visually that collapses the three lines into one.
                breakdown = self.score_breakdowns.get(iter_n)
                if breakdown is not None:
                    cov, qual, total_b = breakdown
                    rec.heuristic = cov
                    rec.quality = qual
                    self._upsert_chart_point((iter_n, cov, qual, total_b))
                else:
                    self._upsert_chart_point((iter_n, float(total), float(total), float(total)))
            if rec.decision == "KEEP" and rec.dimension:
                self.dimensions_covered.add(rec.dimension)
            kind = "keep" if rec.decision == "KEEP" else "discard"
            score_str = f"{rec.total:.1f}" if rec.total is not None else "?"
            self._push_log(kind, f"iter {iter_n} {rec.decision.lower()} · score {score_str}", ts)

        elif evt == "iteration_aborted":
            iter_n = ev.get("iteration", self.current_iter)
            rec = self.upsert_iter(iter_n)
            rec.decision = "aborted"
            self._push_log("warn", f"iter {iter_n} aborted · {ev.get('reason', '?')}", ts)

        elif evt == "compress_skipped_low_memory":
            free_gb = ev.get("free_gb", "?")
            self.fallback_events.append(f"iter {ev.get('iteration','?')}: skipped compress, {free_gb} GB free")

        elif evt == "compress_failed_fallback_truncate":
            err = ev.get("error", "?")
            self.fallback_events.append(f"iter {ev.get('iteration','?')}: compress failed → truncate ({err[:30]})")

        elif evt == "iteration_rolled_back":
            undone = ev.get("undone", []) or []
            undone_str = ", ".join(undone) if undone else "(no side effects)"
            dim = (ev.get("dimension", "") or "")[:30]
            self.fallback_events.append(
                f"iter {ev.get('iteration','?')}: rolled back partial iteration "
                f"(dim={dim or '?'}, undone: {undone_str})"
            )

        elif evt == "merge_skipped_duplicate_recovered":
            dim = (ev.get("dimension", "") or "")[:30]
            self.fallback_events.append(
                f"iter {ev.get('iteration','?')}: defensive merge guard fired "
                f"(dim={dim or '?'} — investigate; rollback may have failed)"
            )

        elif evt == "run_completed":
            self.finished = True
            self.current_state = "DONE"
            self._push_log("info", "run completed", ts)


def _short_dim(dim: str) -> str:
    """Shorten a long dimension string for the dim grid."""
    # Take up to first colon or first 30 chars
    if ":" in dim:
        dim = dim.split(":", 1)[0]
    return dim[:34].strip()


# ---------------------------------------------------------------------------
# Renderers — each returns a rich.console.RenderableType
# ---------------------------------------------------------------------------

def render_header(state: RunState, mode: str) -> Panel:
    title = Text()
    title.append("Adversarial Convergence", style=f"bold {COLOR_ACCENT}")
    title.append(f" — {state.run_id}", style=COLOR_TEXT)
    badge_color = "green" if mode == "live" else "yellow"
    title.append(f"  [{mode}]", style=f"bold {badge_color}")

    target = state.target_dimensions
    covered = len(state.dimensions_covered)
    state_color = STATE_COLOR.get(state.current_state, COLOR_TEXT)

    meta = Text()
    meta.append("iter ", style=COLOR_MUTED)
    meta.append(f"{state.current_iter}", style=f"bold {COLOR_TEXT}")
    meta.append("   state ", style=COLOR_MUTED)
    meta.append(state.current_state.ljust(12), style=f"bold {state_color}")
    meta.append("   backend ", style=COLOR_MUTED)
    meta.append(state.current_backend[:24], style=COLOR_TEXT)
    meta.append("   dim ", style=COLOR_MUTED)
    meta.append(state.current_dim[:30], style=COLOR_TEXT)
    meta.append("   covered ", style=COLOR_MUTED)
    meta.append(f"{covered}/{target}", style=f"bold {COLOR_KEEP}")

    return Panel(
        Group(title, meta),
        box=ROUNDED,
        border_style="grey39",
        padding=(0, 1),
    )


# Animation: rich.Live re-renders at REFRESH_HZ.  This counter advances
# once per render and drives subtle motion on the active state (pulsing
# brightness, spinner char, edge glow) without being epileptic.
ANIM_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
ANIM_BRIGHTNESS = ["bright_yellow", "yellow1", "yellow2", "yellow1"]


def _spinner_char(tick: int) -> str:
    return ANIM_FRAMES[tick % len(ANIM_FRAMES)]


def _pulse_color(tick: int) -> str:
    return ANIM_BRIGHTNESS[(tick // 2) % len(ANIM_BRIGHTNESS)]


# State-machine layout: list of (label, role-color).  Box-drawn with proper
# horizontal centering so the chart looks like a real flowchart, not a list.
_BOX_W = 24  # node box width


def _box(label: str, *, active: bool, color: str, tick: int) -> list[Text]:
    """Return three Text lines forming a box around `label`.

    Active boxes pulse: spinner char on the left, brightness-cycling border.
    """
    pad = max(0, _BOX_W - 2 - len(label))
    left_pad = pad // 2
    right_pad = pad - left_pad
    if active:
        border_color = _pulse_color(tick)
        body_color = f"bold {color}"
        # Spinner replaces the inactive 2-space left margin; same width,
        # so the box right border stays aligned with the top/bottom corners.
        left_marker = _spinner_char(tick) + " "
    else:
        border_color = COLOR_MUTED
        body_color = COLOR_MUTED
        left_marker = "  "
    top = Text()
    top.append("  ┌" + "─" * (_BOX_W - 2) + "┐", style=border_color)
    mid = Text()
    mid.append(left_marker, style=COLOR_ACCENT if active else COLOR_MUTED)
    mid.append("│", style=border_color)
    mid.append(" " * left_pad + label + " " * right_pad, style=body_color)
    mid.append("│", style=border_color)
    bot = Text()
    bot.append("  └" + "─" * (_BOX_W - 2) + "┘", style=border_color)
    return [top, mid, bot]


def _connector(active: bool, tick: int) -> Text:
    """Vertical arrow between boxes; pulses when the next box is active."""
    color = _pulse_color(tick) if active else COLOR_MUTED
    line = Text()
    line.append(" " * (_BOX_W // 2 + 2), style=color)
    line.append("│" if not active else "▼", style=color)
    return line


def render_state_machine(state: RunState, tick: int = 0) -> Panel:
    """Vertical box-drawn state machine with per-tick animation on the active node."""
    lines: list[Text] = []
    for i, st in enumerate(STATE_FLOW):
        is_active = state.current_state == st
        # If THIS state is active, the connector ABOVE it pulses too
        if i > 0:
            prev_was_active = state.current_state == STATE_FLOW[i - 1]
            lines.append(_connector(active=is_active or prev_was_active, tick=tick))
        color = STATE_COLOR.get(st, COLOR_TEXT)
        lines.extend(_box(st, active=is_active, color=color, tick=tick))

    # DECIDE branches into KEEP / DISCARD horizontally
    keep_active = state.current_state == "KEEP"
    discard_active = state.current_state == "DISCARD"
    decide_just_resolved = keep_active or discard_active
    lines.append(_connector(active=decide_just_resolved, tick=tick))
    branch = Text()
    branch.append(" " * 2, style=COLOR_MUTED)
    branch.append("┌─ KEEP ", style=_pulse_color(tick) if keep_active else COLOR_MUTED)
    branch.append(" " * (_BOX_W - 12), style=COLOR_MUTED)
    branch.append(" DISCARD ─┐", style=_pulse_color(tick) if discard_active else COLOR_MUTED)
    lines.append(branch)
    branch_box = Text()
    branch_box.append("  │ ", style=_pulse_color(tick) if keep_active else COLOR_MUTED)
    branch_box.append(f"{_spinner_char(tick) if keep_active else ' '} merge ",
                      style=f"bold {COLOR_KEEP}" if keep_active else COLOR_MUTED)
    branch_box.append(" " * (_BOX_W - 16), style=COLOR_MUTED)
    branch_box.append(f" save {_spinner_char(tick) if discard_active else ' '} ",
                      style=f"bold {COLOR_DISCARD}" if discard_active else COLOR_MUTED)
    branch_box.append("│", style=_pulse_color(tick) if discard_active else COLOR_MUTED)
    lines.append(branch_box)

    # Side-cars
    lines.append(Text(""))
    side = Text()
    compress_active = state.current_state == "COMPRESS"
    synth_active = state.current_state in ("SYNTHESIZE", "DONE")
    side.append("  ", style=COLOR_MUTED)
    if compress_active:
        side.append(f"{_spinner_char(tick)} ⚙ COMPRESS ", style=f"bold {COLOR_COMPRESS}")
    else:
        side.append("  ⚙ COMPRESS ", style=COLOR_MUTED)
    side.append("   ", style=COLOR_MUTED)
    if synth_active:
        side.append(f"{_spinner_char(tick)} 📄 SYNTHESIZE", style=f"bold {COLOR_SYNTH}")
    else:
        side.append("  📄 SYNTHESIZE", style=COLOR_MUTED)
    lines.append(side)

    return Panel(
        Group(*lines),
        title="[bold]state machine[/bold]",
        title_align="left",
        border_style="grey39",
        box=ROUNDED,
        padding=(0, 1),
    )


def render_score_chart(state: RunState) -> Panel:
    """Sparklines for heuristic / judge / total."""
    if not state.chart_points:
        body: Group | Text = Text("(no scores yet)", style=COLOR_MUTED)
    else:
        heur_vals = [p[1] for p in state.chart_points]
        qual_vals = [p[2] for p in state.chart_points]
        total_vals = [p[3] for p in state.chart_points]

        def line(label: str, values: list[float], color: str) -> Text:
            spark = _sparkline(values)
            t = Text()
            t.append(f"{label:<10}", style=COLOR_MUTED)
            t.append(spark, style=color)
            t.append(f"  {values[-1]:6.1f}", style=f"bold {color}")
            return t

        recent_iters = ", ".join(f"#{p[0]}={p[3]:.1f}" for p in state.chart_points[-5:])
        body = Group(
            line("heuristic", heur_vals, COLOR_RESEARCH),
            line("judge   ", qual_vals, COLOR_CRITIQUE),
            line("total   ", total_vals, COLOR_ACCENT),
            Text(""),
            Text(f"recent: {recent_iters}", style=COLOR_MUTED),
        )

    return Panel(
        body,
        title="[bold]score progression[/bold]",
        title_align="left",
        border_style="grey39",
        box=ROUNDED,
        padding=(1, 2),
    )


def render_dim_grid(state: RunState, all_dimensions: list[str] | None = None) -> Panel:
    """Grid of dimension tiles — covered cells in green, current in yellow.

    Source of truth for the full dimension list: ``state.configured_dimensions``
    (loaded from ``effective_config.json``).  Falls back to dimensions seen in
    the run's iterations when no config is available (scripted demo).
    """
    target = state.target_dimensions or len(state.configured_dimensions) or len(state.iters) or 1
    covered_set = state.dimensions_covered
    current_dim = state.current_dim if state.current_state not in ("(idle)", "DONE") else ""

    # Configured dimensions are the truth; fall back to discovered-from-run.
    seen: list[str] = list(state.configured_dimensions) if state.configured_dimensions else (
        list(all_dimensions) if all_dimensions else []
    )
    if not state.configured_dimensions:
        for rec in state.iters.values():
            if rec.dimension and rec.dimension not in seen:
                seen.append(rec.dimension)
    if current_dim and current_dim not in seen:
        seen.append(current_dim)

    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 1), pad_edge=False)
    table.add_column("dim", overflow="ellipsis", no_wrap=True)
    for dim in seen:
        if dim in covered_set:
            mark, style = "✓", f"bold {COLOR_KEEP}"
        elif dim == current_dim:
            mark, style = "◉", f"bold {COLOR_ACCENT}"
        else:
            mark, style = "·", COLOR_MUTED
        line = Text()
        line.append(f"{mark} ", style=style)
        line.append(dim[:32], style=style if dim in covered_set or dim == current_dim else COLOR_MUTED)
        table.add_row(line)

    body: Group = Group(
        Text(f"{len(covered_set)} / {target}", style=f"bold {COLOR_KEEP}"),
        Text(""),
        table,
    )
    return Panel(
        body,
        title="[bold]dimensions[/bold]",
        title_align="left",
        border_style="grey39",
        box=ROUNDED,
        padding=(0, 1),
    )


def render_cost_block(state: RunState) -> Panel:
    """Iters / backend calls / elapsed.

    All four cells show real numbers from the audit trail.  Spend is
    intentionally omitted: the framework doesn't surface it in
    audit_trail.jsonl today, and showing a hardcoded "$0.00" is
    misleading for API-backend runs.  Re-add when run_manifest grows
    a cost_estimate field.
    """
    iter_count = len(state.iters)
    calls_str = str(state.backend_calls) if state.backend_calls else "—"
    kept = sum(1 for r in state.iters.values() if r.decision.upper() == "KEEP")
    discarded = sum(1 for r in state.iters.values() if r.decision.upper() == "DISCARD")

    elapsed = "—"
    if state.started_at:
        secs = int(time.time() - state.started_at)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        elapsed = f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"

    cells = Table.grid(expand=True, padding=(0, 1))
    for _ in range(4):
        cells.add_column(justify="center", ratio=1)

    def cell(label: str, value: str, color: str = COLOR_TEXT) -> Group:
        return Group(
            Text(label.upper(), style=COLOR_MUTED, justify="center"),
            Text(value, style=f"bold {color}", justify="center"),
        )

    cells.add_row(
        cell("iters", str(iter_count), COLOR_TEXT),
        cell("calls", calls_str, COLOR_TEXT),
        cell("kept/disc", f"{kept}/{discarded}", COLOR_KEEP if kept >= discarded else COLOR_DECIDE),
        cell("elapsed", elapsed, COLOR_TEXT),
    )

    return Panel(
        cells,
        title="[bold]throughput[/bold]",
        title_align="left",
        border_style="grey39",
        box=ROUNDED,
        padding=(0, 1),
    )


_LOG_KIND_COLOR = {
    "info":    COLOR_MUTED,
    "iter":    COLOR_PRIMARY,
    "step":    COLOR_RESEARCH,
    "keep":    COLOR_KEEP,
    "discard": COLOR_DISCARD,
    "warn":    COLOR_DECIDE,
}


def render_event_log(state: RunState) -> Panel:
    """Live tail of the most-recent meaningful audit events.

    Reads from ``state.recent_events`` (a bounded deque populated by
    ``_push_log`` calls inside ``apply_event``).  Each row carries a
    timestamp, a kind tag for colour, and a short summary.  Newest at
    the bottom (so the cursor's natural reading order matches "what
    just happened").
    """
    if not state.recent_events:
        body: Group | Text = Text("(no events yet — waiting for audit trail)", style=COLOR_MUTED)
    else:
        rows: list[Text] = []
        for ts_short, kind, summary in state.recent_events:
            color = _LOG_KIND_COLOR.get(kind, COLOR_TEXT)
            line = Text()
            line.append(f"{ts_short or '--:--:--'}  ", style=COLOR_MUTED)
            line.append(f"{kind:<7}", style=f"bold {color}")
            line.append(f" {summary}", style=COLOR_TEXT)
            rows.append(line)
        body = Group(*rows)

    return Panel(
        body,
        title="[bold]events · live tail[/bold]",
        title_align="left",
        border_style="grey39",
        box=ROUNDED,
        padding=(0, 1),
    )


def render_fallback_log(state: RunState) -> Panel | None:
    """Tail of OOM-defense fallback events, only shown when there are any."""
    if not state.fallback_events:
        return None
    body = Group(*[Text(line, style=COLOR_DECIDE) for line in state.fallback_events[-5:]])
    return Panel(
        body,
        title="[bold]⚠ fallbacks fired[/bold]",
        title_align="left",
        border_style="dark_orange",
        box=ROUNDED,
        padding=(0, 1),
    )


def render_footer(mode: str, source_path: Path | None, paused: bool) -> Panel:
    parts = Text()
    parts.append(f"{mode}", style=f"bold {'green' if mode == 'live' else 'yellow'}")
    if source_path:
        parts.append(f" · {source_path}", style=COLOR_MUTED)
    if paused:
        parts.append("  [paused]", style=COLOR_DECIDE)
    parts.append("   ", style=COLOR_MUTED)
    parts.append("Ctrl+C", style=COLOR_TEXT)
    parts.append(" to quit", style=COLOR_MUTED)
    return Panel(parts, border_style="grey39", box=SIMPLE, padding=(0, 1))


# ---------------------------------------------------------------------------
# Sparkline
# ---------------------------------------------------------------------------

def _sparkline(values: Iterable[float], width: int = 30, vmin: float = 0.0, vmax: float | None = None) -> str:
    """Unicode sparkline padded/truncated to ``width``.

    When ``vmax`` is None, auto-scales to the data range with a floor of 100
    so low-score runs still use the full 0-100 visual range AND novelty-blended
    runs (max 125) don't clamp to ``█``.
    """
    vals = list(values)
    if not vals:
        return ""
    vals = vals[-width:]
    if vmax is None:
        vmax = max(100.0, max(vals))
    out_chars = []
    span = max(0.0001, vmax - vmin)
    for v in vals:
        normalized = max(0.0, min(1.0, (v - vmin) / span))
        idx = int(normalized * (len(SPARK_BARS) - 1))
        out_chars.append(SPARK_BARS[idx])
    return "".join(out_chars).rjust(width)


# ---------------------------------------------------------------------------
# Layout assembly
# ---------------------------------------------------------------------------

def build_layout(state: RunState, mode: str, source: Path | None, paused: bool,
                 known_dims: list[str] | None = None, tick: int = 0) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3),
    )
    # Left column width must fit the widest state-machine line, which is
    # the KEEP / DISCARD branch (~33 chars inside) plus panel padding +
    # border (4 chars total).  ``_BOX_W + 16`` gives 40 char column,
    # enough headroom for the branch and the COMPRESS / SYNTHESIZE row
    # without wrap.  Empirically: was 32 (overlapping); 40 fits cleanly.
    layout["body"].split_row(
        Layout(name="left", size=_BOX_W + 16),
        Layout(name="right", ratio=1),
    )
    # The right column splits into "data" (top) and "events log" (bottom).
    # Data section stacks the existing score / dims / throughput cards;
    # events section is a live tail of the audit trail, filling the space
    # that was previously empty whitespace below the dims panel.
    layout["right"].split_column(
        Layout(name="right_top", ratio=2),
        Layout(name="right_bottom", ratio=1, minimum_size=8),
    )
    top_components = [
        Layout(render_score_chart(state), name="chart", size=8),
        Layout(render_dim_grid(state, known_dims), name="dims", ratio=1),
        Layout(render_cost_block(state), name="cost", size=4),
    ]
    fallback = render_fallback_log(state)
    if fallback:
        top_components.append(Layout(fallback, name="fallback", size=7))
    layout["right_top"].split_column(*top_components)
    layout["right_bottom"].update(render_event_log(state))
    layout["left"].update(render_state_machine(state, tick=tick))
    layout["header"].update(render_header(state, mode))
    layout["footer"].update(render_footer(mode, source, paused))
    return layout


# ---------------------------------------------------------------------------
# Data sources: live tail + file replay + scripted
# ---------------------------------------------------------------------------

def load_run_metadata(output_dir: Path) -> dict:
    """Read topic / dimensions / target_dimensions_total from the run's
    ``effective_config.json``.  Returns ``{}`` when missing or unparseable.

    The framework writes this snapshot at run start; it is the canonical
    source for static run metadata that doesn't change during the run.
    """
    path = output_dir / "effective_config.json"
    if not path.exists():
        return {}
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        "topic": cfg.get("topic", "") or "",
        "dimensions": list(cfg.get("dimensions", []) or []),
        "target_dimensions_total": int(
            (cfg.get("scoring") or {}).get("target_dimensions_total")
            or len(cfg.get("dimensions", []) or [])
            or 0
        ),
        "strategy": (cfg.get("execution") or {}).get("strategy", ""),
        "compress_every": (cfg.get("execution") or {}).get("compress_every", 0),
    }


def load_results_tsv(path: Path) -> dict[int, tuple[float, float, float]]:
    """Parse ``results.tsv`` for per-iteration score breakdowns.

    Returns ``{iteration: (coverage_score, quality_score, total_score)}``.
    The breakdown is the source of truth for the TUI score chart because
    ``audit_trail.jsonl::iteration_completed`` only carries ``total_score``.
    Returns ``{}`` when the file is missing or unparseable.
    """
    out: dict[int, tuple[float, float, float]] = {}
    if not path.exists():
        return out
    try:
        import csv

        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                try:
                    iter_n = int(row.get("iteration", 0))
                    cov = float(row.get("coverage_score", 0))
                    qual = float(row.get("quality_score", 0))
                    total = float(row.get("total_score", 0))
                    out[iter_n] = (cov, qual, total)
                except (ValueError, TypeError):
                    continue
    except OSError:
        pass
    return out


def iter_audit_events(path: Path) -> Iterable[dict]:
    """Read every existing event from an audit file, yielding parsed dicts.
    Malformed lines are silently skipped."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return


def follow_audit_events(path: Path, poll_interval: float = 0.25) -> Iterable[dict]:
    """Tail the audit file, yielding new events as they arrive.
    Yields existing events first (catch-up), then poll-tails forever."""
    pos = 0
    while True:
        try:
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(pos)
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
                pos = fh.tell()
        except FileNotFoundError:
            pass
        time.sleep(poll_interval)


def scripted_events() -> list[dict]:
    """Synthetic event sequence so the TUI can be demoed without a real run."""
    out: list[dict] = [
        {"event": "run_started", "topic": "Demo", "strategy": "adversarial", "run_id": "scripted-demo"},
    ]
    dims = [
        "REST vs HTTP", "WebSocket", "AuthN/AuthZ", "Rate limiting",
        "Integrations", "VTL mapping", "CORS", "Observability",
        "Cost model", "Deployment", "Custom domains", "Hard limits",
    ]
    scores = [51.6, 56.4, 61.0, 64.0, 66.8, 69.6, 67.6, 73.0, 78.0, 81.0, 83.0, 85.0]
    for i, (dim, score) in enumerate(zip(dims, scores), start=1):
        out.append({"event": "iteration_started", "iteration": i})
        for step in ("hypothesise", "execute_research", "critique", "score_iteration"):
            out.append({"event": "step_started", "step": step, "iteration": i,
                        "dimension": dim, "backend": _backend_for_step(step)})
            out.append({"event": "step_completed", "step": step, "iteration": i})
        decision = "DISCARD" if i == 7 else "KEEP"
        out.append({"event": "iteration_completed", "iteration": i,
                    "dimension": dim, "status": decision, "total_score": score})
        if i % 2 == 0:
            out.append({"event": "step_started", "step": "compress_knowledge_base",
                        "iteration": i, "backend": "claude-cli sonnet"})
            out.append({"event": "step_completed", "step": "compress_knowledge_base", "iteration": i})
    out.append({"event": "run_completed", "iteration": len(dims)})
    return out


def _backend_for_step(step: str) -> str:
    return {
        "hypothesise": "claude-cli opus",
        "execute_research": "claude-cli sonnet",
        "critique": "codex-cli gpt-5.4",
        "score_iteration": "codex-cli gpt-5.4",
    }.get(step, "—")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

REFRESH_HZ = 8   # rich Live refresh rate — fast enough for smooth pulse animation


def _apply_metadata(state: RunState, meta: dict) -> None:
    """Populate static run metadata on the RunState from effective_config.json.
    No-op when the dict is empty (file missing / unreadable)."""
    if not meta:
        return
    if meta.get("topic"):
        state.topic = meta["topic"]
    if meta.get("strategy"):
        state.strategy = meta["strategy"]
    if meta.get("dimensions"):
        state.configured_dimensions = [_short_dim(d) for d in meta["dimensions"]]
    if meta.get("target_dimensions_total"):
        state.target_dimensions = int(meta["target_dimensions_total"])


def run_live(audit_path: Path, console: Console) -> None:
    """Tail audit_trail.jsonl and update the display in real time."""
    state = RunState()
    state.run_id = audit_path.parent.name
    state.started_at = time.time()
    # Load authoritative score breakdowns from results.tsv (audit_trail's
    # iteration_completed only carries total_score).  In live mode the file
    # may grow during the run; this snapshot is fine for completed iterations.
    state.score_breakdowns = load_results_tsv(audit_path.parent / "results.tsv")
    state.seed_chart_from_breakdowns()
    _apply_metadata(state, load_run_metadata(audit_path.parent))

    layout = build_layout(state, "live", audit_path, paused=False, tick=0)
    tick = 0
    with Live(layout, console=console, refresh_per_second=REFRESH_HZ, screen=False) as live:
        try:
            poll = 1.0 / REFRESH_HZ
            for ev in follow_audit_events(audit_path, poll_interval=poll):
                state.apply_event(ev)
                tick += 1
                live.update(build_layout(state, "live", audit_path, paused=False, tick=tick))
        except KeyboardInterrupt:
            pass


def run_replay(audit_path: Path | None, console: Console, frame_delay: float,
               scripted: bool = False) -> None:
    """Read the whole audit file (or scripted events) and step through with delay."""
    if scripted:
        events = scripted_events()
        source = None
        run_label = "scripted-demo"
    else:
        assert audit_path is not None
        events = list(iter_audit_events(audit_path))
        source = audit_path
        run_label = audit_path.parent.name

    state = RunState()
    state.run_id = run_label
    state.started_at = time.time()
    if audit_path is not None:
        state.score_breakdowns = load_results_tsv(audit_path.parent / "results.tsv")
        state.seed_chart_from_breakdowns()
        _apply_metadata(state, load_run_metadata(audit_path.parent))

    layout = build_layout(state, "replay", source, paused=False, tick=0)
    tick = 0
    with Live(layout, console=console, refresh_per_second=REFRESH_HZ, screen=False) as live:
        try:
            for ev in events:
                state.apply_event(ev)
                # Subdivide the frame_delay into smaller animation ticks so
                # the active state pulses smoothly even when an event takes
                # a few seconds (frame_delay > 1).
                anim_ticks = max(1, int(frame_delay * REFRESH_HZ))
                for _ in range(anim_ticks):
                    tick += 1
                    live.update(build_layout(state, "replay", source, paused=False, tick=tick))
                    time.sleep(frame_delay / anim_ticks)
            # Hold the final state on screen until user quits — keep the
            # pulse animation alive so the user knows the page isn't frozen.
            while True:
                tick += 1
                live.update(build_layout(state, "replay", source, paused=False, tick=tick))
                time.sleep(1.0 / REFRESH_HZ)
        except KeyboardInterrupt:
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tui_monitor",
        description=__doc__.split("\n")[0],
    )
    parser.add_argument("output_dir", nargs="?",
                        help="Path to output/<run>/ — required unless --scripted")
    parser.add_argument("--live", action="store_true", help="Force live tail mode")
    parser.add_argument("--replay", action="store_true", help="Force replay mode")
    parser.add_argument("--scripted", action="store_true",
                        help="Demo with synthetic data (no audit file required)")
    parser.add_argument("--replay-speed", type=float, default=0.25,
                        help="Seconds per frame in replay mode (default 0.25)")
    args = parser.parse_args()

    console = Console()

    if args.scripted:
        run_replay(None, console, args.replay_speed, scripted=True)
        return 0

    if not args.output_dir:
        parser.print_usage(sys.stderr)
        print("error: output_dir is required (or pass --scripted)", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    audit_path = output_dir / "audit_trail.jsonl"

    if not audit_path.exists():
        print(f"error: {audit_path} does not exist", file=sys.stderr)
        return 1

    if args.live and args.replay:
        print("error: pick --live OR --replay, not both", file=sys.stderr)
        return 2

    # Auto-detect: if the file's been written to in the last 60s, assume live.
    mode = "replay"
    if args.live:
        mode = "live"
    elif args.replay:
        mode = "replay"
    else:
        age = time.time() - audit_path.stat().st_mtime
        mode = "live" if age < 60 else "replay"

    if mode == "live":
        run_live(audit_path, console)
    else:
        run_replay(audit_path, console, args.replay_speed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
