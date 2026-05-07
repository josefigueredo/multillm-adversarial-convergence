# Iteration atomicity & resume safety

**Status:** Proposed (2026-05-07)
**Author:** Jose Figueredo
**Replaces:** the defensive merge-idempotency guard added in `f3c4f18` (the
guard stays as a safety net but is no longer the primary mechanism).

---

## Problem statement

`run_iteration` performs four separate disk writes per KEEP iteration, in this
order:

1. `state.kb_path.write_text(...)` — appends `## DIM\n\n<findings>` to the
   knowledge base on disk
2. `write_iteration_markdown(...)` — creates `iterations/iter_NNN.md`
3. `write_discovered_gaps_sidecar(...)` — overwrites `discovered_gaps.json`
4. `_log_result(...) → append_results_row(...)` — appends a row to
   `results.tsv`

(After step 4, an optional step 5 fires: `_compress_knowledge_base`. This step
*reads* the KB and *replaces* it with a distilled version; it has no effect on
the partial-completion problem because by step 5 the iteration is fully
recorded.)

A SIGKILL (OOM, supervisor signal, kernel jetsam) at any point between steps 1
and 4 leaves the run in a state where:

- The KB on disk has `## DIM\n\n<findings>` for iteration N
- `iter_NNN.md` may or may not exist
- `discovered_gaps.json` may or may not be updated
- `results.tsv` may or may not have iteration N's row

`resume_state` derives `explored_dimensions` from `results.tsv`. If results.tsv
doesn't have the row, `explored_dimensions` doesn't include iteration N's dim,
and the next iteration loop picks the same dimension. `merge_findings` then
appends `## DIM\n\n<new findings>` to a KB that already has the section,
**doubling the dimension's content** in the corpus.

The current fix (`f3c4f18`) guards the merge call with a string check on the
KB. It prevents the doubling but introduces three problems:

1. **False positive on legitimate refinement attempts.** When a dimension is
   DISCARD'd then re-attempted (within `MAX_ATTEMPTS_PER_DIMENSION = 3`), the
   second attempt's findings are silently skipped because the dimension header
   is already in the KB.
2. **Brittle under compression.** `_compress_knowledge_base` rewrites the KB
   into a distilled summary. The dimension headers may be preserved verbatim,
   renamed, merged, or dropped. The string check assumes byte-for-byte
   preservation and gives wrong answers on either side of compression.
3. **Doesn't address the root cause.** The bug is non-atomic multi-file
   writes. The guard covers one symptom; other symptoms (orphaned
   `iter_NNN.md` from a different crash window) are silent.

## Proposed solution: sentinel file with rollback on resume

Treat each iteration's risky-write block as a transaction with an explicit
in-progress marker. On resume, scan for markers and roll back partial
completions before counting iterations.

### Sentinel file

Path: `iterations/.iter_<NNN>_in_progress.json`

Schema:

```json
{
  "iteration": 5,
  "dimension": "REST API vs HTTP API: feature matrix, ...",
  "started_at": "2026-05-07T08:05:15.000+00:00",
  "kb_section_marker": "\n## REST API vs HTTP API: feature matrix, ...\n"
}
```

Lifecycle:

1. Written at the top of the KEEP path inside `_merge_findings` (or in the
   caller, before the KB write) — `write_iteration_sentinel(...)`.
2. Removed at the bottom of the KEEP path, after `append_results_row` returns
   — `clear_iteration_sentinel(...)`.

Compress runs *after* the sentinel is cleared so a crash during compress does
not need rollback.

### Rollback on resume

A new function `rollback_partial_iterations(iterations_dir, results_path,
knowledge_base_path)` runs at the very top of `resume_state`, before any state
counting:

1. Glob `iterations/.iter_*_in_progress.json`.
2. For each sentinel, parse JSON to recover `iteration`, `dimension`,
   `kb_section_marker`.
3. Roll back any side effects that may have been written:
   - If `iter_<NNN>.md` exists → delete it.
   - If the last row of `results.tsv` is for `iteration` → drop the last row.
   - If `kb_section_marker` is present in the KB → delete the section
     (everything from the marker to the next `\n## ` heading or end of file).
4. Delete the sentinel.
5. Emit one `iteration_rolled_back` audit event per rollback with the
   iteration number, dimension, and which side effects were undone.

After rollback, `resume_state` proceeds normally. Disk state is consistent
with "iteration N never started"; iteration N reruns cleanly with no doubling
risk.

### Compress safety

A SIGKILL during `_compress_knowledge_base` (the user's actual current crash)
is *not* covered by the sentinel — by then the sentinel is already cleared.
That's intentional. Compress is read-then-replace on the KB; if it crashes,
the KB on disk is the pre-compress version (which is correct, just larger).
The two-layer compress defense (`compress_skipped_low_memory` /
`compress_failed_fallback_truncate`) handles the OOM-prevention story for
that step.

## Audit events

| event | when | fields |
|---|---|---|
| `iteration_sentinel_written` | sentinel created at top of KEEP path | iteration, dimension |
| `iteration_sentinel_cleared` | sentinel deleted after step 4 | iteration, dimension |
| `iteration_rolled_back` | sentinel detected on resume; rollback applied | iteration, dimension, undone (list of "iter_md", "tsv_row", "kb_section") |

The dashboard and TUI surface `iteration_rolled_back` as a recovery badge
on the affected iteration.

## Surfaces to update

| Surface | Change |
|---|---|
| `src/run_state.py` | Add sentinel I/O + rollback function; modify `resume_state` to call rollback first. Keep the `merge_findings` idempotency guard as a safety net (defensive only). |
| `src/research_loop.py` | Wrap the 4 risky writes with sentinel-write at top and sentinel-clear at bottom. Emit the new audit events. |
| `tests/test_iteration_atomicity.py` | New file. Crash-window matrix: simulate SIGKILL between each pair of writes by partially constructing on-disk state, then calling `resume_state` and asserting (a) rollback ran, (b) re-running the iteration produces no doubling, (c) audit events fired. |
| `docs/research.md` | Add an "Atomicity & resume" section between Architecture and Scoring; update the Architecture mermaid to show the sentinel/rollback path. |
| `docs/showcase/dashboard.html` | Audit-trail loader detects `iteration_rolled_back` events; renders a recovery badge on the iteration tile. |
| `scripts/tui_monitor.py` | `RunState.apply_event` handles `iteration_rolled_back`; surfaces in the existing fallback-events panel. |

## Test matrix

Six crash windows to cover, each as a separate test:

| # | Crash point | On-disk state at resume | Expected rollback action |
|---|---|---|---|
| 1 | Before any writes | None | (no sentinel, nothing to do) |
| 2 | Between sentinel write and KB write | Sentinel exists, no other side effects | Delete sentinel only |
| 3 | Between KB write and iter-md write | Sentinel + KB section | Delete KB section, delete sentinel |
| 4 | Between iter-md write and sidecar write | Sentinel + KB section + iter_NNN.md | Delete iter_NNN.md, delete KB section, delete sentinel |
| 5 | Between sidecar write and results.tsv write | Sentinel + KB section + iter_NNN.md + sidecar | Delete iter_NNN.md, delete KB section, delete sentinel (sidecar is overwrite-only, no rollback needed) |
| 6 | After all 4 writes complete (compress crash) | All 4 + compress mid-flight (no sentinel) | Nothing — rollback finds no sentinel; the iteration is complete |

Plus three positive-path tests:

- Happy path: sentinel written then cleared; no rollback on resume.
- Multiple sentinels (back-to-back crashes): each rolled back independently.
- Sentinel for a dimension that's no longer in the KB (post-compress drop):
  rollback succeeds without needing the section to be present.

## Migration

The old idempotency guard in `merge_findings` (added in `f3c4f18`) stays in
place but is documented as defensive-only. It should never fire after this
change ships; if it ever does, that indicates a bug in the rollback path
that needs investigation. The audit event name
`merge_skipped_duplicate_recovered` already reflects this — it's a "this
fired when it shouldn't have" signal, not a primary success path.

Existing on-disk runs without sentinels are unaffected: `rollback_partial_
iterations` is a no-op when the glob finds nothing.

## Out of scope (future work)

- **Atomic writes via temp-file + rename.** The KB and sidecar writes could
  be made atomic individually with `tempfile.NamedTemporaryFile + os.replace`.
  That would eliminate "partial single-file writes" but doesn't help the
  multi-file consistency problem the sentinel solves. Worth doing but
  separately.
- **Compress idempotency.** A SIGKILL mid-compress currently leaves the KB
  in its pre-compress state. That's correct, but the next iteration's
  compress trigger will fire again on a still-bloated KB. Not a bug; just
  inefficient. A "compress completed" marker could let resume skip the
  immediate re-compress. Defer until the OOM defense in
  `_compress_knowledge_base` proves insufficient in practice.
- **Multi-host concurrent runs.** Sentinel files don't coordinate across
  hosts. The framework is single-process per run today, so out of scope.
