# Source Files Feature — Design Spec

**Date:** 2026-04-18
**Status:** Approved

---

## Problem

`DocumentConfig.source_material` accepts a single string (file path or raw text). Users with structured document packages (PRDs, ADRs, architecture specs, design docs) have no way to feed multiple companion files to the refinement loop. Files are ignored.

---

## Goal

Allow users to declare a list of source files — with glob support — and control which agents see each file. Files are injected as structured context into the relevant prompt templates.

---

## Design

### 1. Data Model

**New dataclass in `src/config.py`:**

```python
@dataclass(frozen=True)
class SourceFileConfig:
    path: str                  # resolved absolute path (one file, post-glob-expansion)
    roles: tuple[str, ...]     # which agents receive this file's content
```

**`DocumentConfig` change:**

```python
source_files: tuple[SourceFileConfig, ...] = ()
```

`source_material` is kept for backward compatibility and rendered before `source_files` in the builder prompt.

---

### 2. YAML Syntax

```yaml
source_files:
  - path: docs/**/*.md
    roles: [builder, architect]
  - path: docs/product/*.md
    roles: [all]
  - path: /absolute/path/to/file.md
    roles: [builder, product_owner]
```

**Path resolution rules:**
- Relative paths are resolved relative to the config file's parent directory.
- Absolute paths are used as-is.
- Glob patterns are expanded using `pathlib.Path.glob()`.
- A glob that matches nothing → warning logged, silently skipped.
- A literal path (no glob wildcards) that does not exist → `ValueError` raised at load time.

**Valid roles:**
- `"builder"` — the PRD Builder (research[0])
- `"challenger"` — the internal consistency Challenger (research[1])
- Any persona name: `"architect"`, `"scrum_master"`, `"product_owner"`, or any custom persona declared in `personas:`
- `"all"` — expands to `builder` + `challenger` + every persona in the config

Glob entries are expanded into one `SourceFileConfig` per matched file. Role `"all"` is expanded at load time into the concrete role names from the config.

---

### 3. ConvergeStrategy

**New method `_source_block(role: str) -> str`:**

- Filters `self._config.source_files` for entries where `role in entry.roles`
- Reads each file's content from disk (lazy, per call — no caching)
- Returns a formatted Markdown block:

```
### docs/architecture/PLATFORM_ARCH.md

[file content here]

---

### docs/architecture/adr/ADR-001-temporal-self-hosted.md

[file content here]

---
```

- Returns empty string `""` when no files match the role.

**Injection points:**
- `run_builder` → passes `source_files=self._source_block("builder")` to `render("prd_builder.md", ...)`
- `run_challenger` → passes `source_files=self._source_block("challenger")` to `render("prd_challenger.md", ...)`
- `run_personas` → each persona call passes `source_files=self._source_block(persona.name)` to `render(persona.prompt_file, ...)`

Verifier and Arbitrator do not receive source files — they operate on critiques and patches, not source material.

---

### 4. Prompt Template Changes

Three prompt files are updated to include a `{source_files}` variable:

**`prd_builder.md`** — add after existing `## Source Material` section:
```
## Reference Files

{source_files}
```

**`prd_challenger.md`** — add before `## Document Under Review`:
```
## Reference Files

{source_files}
```

**`prd_persona_*.md`** (all persona prompts) — add before `## Document Under Review`:
```
## Reference Files

{source_files}
```

When `source_files` is empty, the section renders as `## Reference Files\n\n` — harmless to the LLM.

---

### 5. Config Template Update

`configs/prd_template.yaml` gets a documented `source_files:` section with examples showing glob usage and role targeting.

---

## Error Handling

| Condition | Behavior |
|---|---|
| Literal path not found | `ValueError` at `from_yaml` time |
| Glob matches nothing | `log.warning(...)`, skip silently |
| File unreadable at call time | `log.warning(...)`, skip that file |
| Unknown role name | `log.warning(...)`, entry still stored (future persona may match) |

---

## Files Changed

| File | Change |
|---|---|
| `src/config.py` | Add `SourceFileConfig`; add `source_files` to `DocumentConfig.from_yaml` |
| `src/document_strategy.py` | Add `_source_block(role)`; inject into `run_builder`, `run_challenger`, `run_personas` |
| `prompts/prd_builder.md` | Add `{source_files}` block |
| `prompts/prd_challenger.md` | Add `{source_files}` block |
| `prompts/prd_persona_architect.md` | Add `{source_files}` block |
| `prompts/prd_persona_scrum_master.md` | Add `{source_files}` block |
| `prompts/prd_persona_product_owner.md` | Add `{source_files}` block |
| `configs/prd_template.yaml` | Document `source_files:` syntax |

## Files NOT Changed

- `src/document_refiner.py` — no changes needed
- `src/document_loop.py` — no changes needed
- `src/hitl.py` — no changes needed
- `src/cli.py` — no changes needed
- Verifier / Arbitrator prompts — do not receive source files by design
