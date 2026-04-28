# Agent Task: Mega Milestone 15 — Research OS File Migration

**Status:** pending (do after MM16)  
**Approved execution order:** MM14 → MM16 → MM15  
**Prerequisite:** MM16 complete and approved  
**Reviewed by Codex:** 2026-04-27 ✅ (approved with migration-shim-first strategy; no delete-in-same-step)

---

## Review rule

After every committed step: stop, post the commit hash, and wait for human approval before continuing.

## Goal

Move files from flat `src/` into their canonical bounded-context packages. The package
seams exist (MM12), the domain map is accurate, and runtime semantics are settled (MM14,
MM16). Now complete the structural move.

---

## Migration protocol (mandatory for every step)

**Phase A (Steps 1–5):** copy file to new path → add one-liner compatibility shim at old
path → update `__init__.py` re-exports → keep repo green. Do NOT delete originals yet.

Shim template:
```python
# compatibility shim — remove in MM15 Step 7
from src.<package>.<module> import *  # noqa: F401, F403
```

**Phase B (Steps 6–7):** update all callers to canonical paths → verify no non-shim code
still imports from old paths → delete all shims in one sweep.

---

## Context you must read first

- `doc/RESEARCH_OS_DOMAIN_MAP.md` — canonical file-to-package mapping (authoritative)
- `src/evidence/__init__.py`, `src/deliverables/__init__.py`, `src/execution/__init__.py`,
  `src/implement/__init__.py`, `src/policy/__init__.py` — current re-export shims
- `tests/test_domain_packages.py`, `tests/test_execution_implement_packages.py`,
  `tests/test_policy_package.py` — MM12 package seam tests; must never fail during migration

---

## Step 1 — evidence Phase A: move + shim

Move per domain map:
- `src/references.py` → `src/evidence/references.py`
- `src/provenance.py` → `src/evidence/provenance.py`
- `src/provenance_artifacts.py` → `src/evidence/provenance_artifacts.py`
- `src/provenance_pipeline.py` → `src/evidence/provenance_pipeline.py`

Add compatibility shims at old paths. Update `src/evidence/__init__.py` to import from new
locations. Do NOT update callers yet (shims handle backward compat). Full suite must pass.

**Tests first:**
- `from src.evidence.references import build_references` succeeds
- `from src.evidence.provenance import ...` succeeds
- Old path `from src.references import build_references` still works (via shim)
- All existing evidence package seam tests pass; full suite passes

**Commit:** `refactor: move evidence modules into src/evidence (shims at old paths)`  
**Stop for review.**

---

## Step 2 — deliverables Phase A: move + shim

Move per domain map:
- `src/deliverable_pipeline.py` → `src/deliverables/pipeline.py`
- `src/deliverable_classes.py` → `src/deliverables/classes.py`
- `src/citation_verification.py` → `src/deliverables/citation_verification.py`
- `src/report_exports.py` → `src/deliverables/report_exports.py`

Add shims. Update `src/deliverables/__init__.py`. Full suite passes.

**Commit:** `refactor: move deliverable modules into src/deliverables (shims at old paths)`  
**Stop for review.**

---

## Step 3 — execution Phase A: move + shim

Move per domain map:
- `src/execution_plan.py` → `src/execution/plan.py`
- `src/execution_validator.py` → `src/execution/validator.py`
- `src/execution_diagnosis.py` → `src/execution/diagnosis.py`
- `src/integration_adapters.py` → `src/execution/integration_adapters.py`
- `src/repair_loop.py` → `src/execution/repair_loop.py`

Add shims. Update `src/execution/__init__.py`. Full suite passes.

**Commit:** `refactor: move execution modules into src/execution (shims at old paths)`  
**Stop for review.**

---

## Step 4 — implement Phase A: move + shim

Move all implement/plan/document loop modules per domain map into `src/implement/`.
Add shims. Update `src/implement/__init__.py`. Full suite passes.

**Commit:** `refactor: move implement modules into src/implement (shims at old paths)`  
**Stop for review.**

---

## Step 5 — policy Phase A: move + shim

Move HITL, trust, policy_denial, security_runtime, tool_capabilities, tool_runtime,
sandbox_executor modules per domain map into `src/policy/`.
Add shims. Update `src/policy/__init__.py`. Full suite passes.

**Commit:** `refactor: move policy modules into src/policy (shims at old paths)`  
**Stop for review.**

---

## Step 6 — caller import cleanup (Phase B part 1)

For each bounded context in order (evidence → deliverables → execution → implement →
policy): grep for any `from src.X import` or `from .X import` that still uses an old flat
path in non-shim code. Update those callers to use canonical package paths. Do NOT remove
shims yet. Full suite passes after each sub-step.

Grep command to find remaining flat imports per context:
```bash
rg "from src\.(references|provenance|deliverable_pipeline|execution_plan|repair_loop)\b" src/ tests/
```

**Commit:** `refactor: update all callers to canonical domain package imports`  
**Stop for review.**

---

## Step 7 — shim removal + MANIFEST + domain map (Phase B part 2)

1. Grep to verify no non-shim code imports from old flat paths:
   ```bash
   rg "# compatibility shim" src/   # list remaining shims
   ```
2. Delete all compatibility shim files.
3. Update `MANIFEST.md` to reflect canonical file locations.
4. Update `doc/RESEARCH_OS_DOMAIN_MAP.md` to mark all migration steps complete.
5. Full suite must pass.

**Commit:** `refactor: remove compatibility shims; finalize research OS file migration`  
**Stop for review (final MM15 review).**

---

## Copilot Prompt

Paste this verbatim to start MM15 (after MM16 is approved):

```
You are continuing a structured hardening roadmap for this repository.
MM01–MM14 and MM16 are complete and approved. Start MM15 now.

## Your working rule — applies to every step

1. Read the files listed under "Context" before writing any code.
2. Write failing tests FIRST. Run them and confirm they fail.
3. Implement the minimum code to make them pass.
4. Run the full test suite: `uv run pytest -x -q`
5. Commit with a conventional prefix (feat:, fix:, docs:, refactor:).
   No Co-authored-by trailers.
6. Post the commit hash and stop. Do NOT proceed to the next step
   until the human explicitly approves.

---

# MM15 — Research OS File Migration

## Goal

Move files from flat src/ into their canonical bounded-context packages.
The package seams exist (MM12). Now complete the structural move.

## MANDATORY migration protocol

Phase A (Steps 1-5): move file to new path + add compatibility shim at old path
  + update __init__.py + keep repo green. Do NOT delete originals in Phase A.

Shim template (add at old path):
    # compatibility shim — remove in MM15 Step 7
    from src.<package>.<module> import *  # noqa: F401, F403

Phase B (Steps 6-7): update all callers to canonical paths, then delete all shims.

NEVER move + delete in one step. Always shim first.

## Context — read before writing any code

- doc/RESEARCH_OS_DOMAIN_MAP.md — canonical file-to-package mapping (authoritative)
- src/evidence/__init__.py, src/deliverables/__init__.py, src/execution/__init__.py,
  src/implement/__init__.py, src/policy/__init__.py — current re-export shims
- tests/test_domain_packages.py, tests/test_execution_implement_packages.py,
  tests/test_policy_package.py — must never fail during migration

## Step 1 — evidence Phase A: move + shim

Move:
  src/references.py          → src/evidence/references.py
  src/provenance.py          → src/evidence/provenance.py
  src/provenance_artifacts.py → src/evidence/provenance_artifacts.py
  src/provenance_pipeline.py → src/evidence/provenance_pipeline.py

Add compatibility shims at OLD paths. Update src/evidence/__init__.py.
Do NOT update callers yet. Full suite must pass.

Tests first:
- from src.evidence.references import build_references  succeeds
- from src.evidence.provenance import ...  succeeds
- from src.references import build_references  still works (via shim)
- all existing evidence package seam tests pass; full suite passes

Commit: refactor: move evidence modules into src/evidence (shims at old paths)
Stop. Post commit hash. Wait for approval before Step 2.

## Step 2 — deliverables Phase A: move + shim

Move per domain map:
  src/deliverable_pipeline.py → src/deliverables/pipeline.py
  src/deliverable_classes.py  → src/deliverables/classes.py
  src/citation_verification.py → src/deliverables/citation_verification.py
  src/report_exports.py       → src/deliverables/report_exports.py

Add shims. Update src/deliverables/__init__.py. Full suite passes.

Commit: refactor: move deliverable modules into src/deliverables (shims at old paths)
Stop. Post commit hash. Wait for approval before Step 3.

## Step 3 — execution Phase A: move + shim

Move per domain map:
  src/execution_plan.py       → src/execution/plan.py
  src/execution_validator.py  → src/execution/validator.py
  src/execution_diagnosis.py  → src/execution/diagnosis.py
  src/integration_adapters.py → src/execution/integration_adapters.py
  src/repair_loop.py          → src/execution/repair_loop.py

Add shims. Update src/execution/__init__.py. Full suite passes.

Commit: refactor: move execution modules into src/execution (shims at old paths)
Stop. Post commit hash. Wait for approval before Step 4.

## Step 4 — implement Phase A: move + shim

Move all implement/plan/document loop modules per doc/RESEARCH_OS_DOMAIN_MAP.md
into src/implement/. Add shims. Update src/implement/__init__.py. Full suite passes.

Commit: refactor: move implement modules into src/implement (shims at old paths)
Stop. Post commit hash. Wait for approval before Step 5.

## Step 5 — policy Phase A: move + shim

Move HITL, trust, policy_denial, security_runtime, tool_capabilities, tool_runtime,
sandbox_executor modules per doc/RESEARCH_OS_DOMAIN_MAP.md into src/policy/.
Add shims. Update src/policy/__init__.py. Full suite passes.

Commit: refactor: move policy modules into src/policy (shims at old paths)
Stop. Post commit hash. Wait for approval before Step 6.

## Step 6 — caller import cleanup (Phase B part 1)

Grep for any non-shim code still importing from old flat paths:
    rg "from src\.(references|provenance|deliverable_pipeline|execution_plan|repair_loop)\b" src/ tests/

Update those callers to canonical package paths. Do NOT remove shims yet.
Full suite must pass.

Commit: refactor: update all callers to canonical domain package imports
Stop. Post commit hash. Wait for approval before Step 7.

## Step 7 — shim removal + MANIFEST + domain map (Phase B part 2)

1. Grep for remaining shims: rg "# compatibility shim" src/
2. Verify no non-shim code imports from old flat paths.
3. Delete all compatibility shim files.
4. Update MANIFEST.md to reflect canonical file locations.
5. Update doc/RESEARCH_OS_DOMAIN_MAP.md to mark all migration steps complete.
6. Full suite must pass.

Commit: refactor: remove compatibility shims; finalize research OS file migration
Stop. Post commit hash. This is the final MM15 step.
Wait for full MM15 review.
```
