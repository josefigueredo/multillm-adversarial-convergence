# Source Files Feature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `source_files` to `DocumentConfig` with glob support and per-file role targeting, so companion documents are injected into builder, challenger, and persona prompts.

**Architecture:** `SourceFileConfig` is a new frozen dataclass stored in `DocumentConfig.source_files`; paths are resolved (and globs expanded) eagerly in `from_yaml` relative to the config file's directory. `ConvergeStrategy._source_block(role)` reads files lazily per call and returns a formatted Markdown block injected into the three prompt call sites. Verifier and Arbitrator are intentionally excluded.

**Tech Stack:** Python 3.10, `pathlib.Path.glob`, `dataclasses`, `unittest.mock.patch`

---

## File Structure

| File | Change |
|---|---|
| `src/config.py` | Add `SourceFileConfig` dataclass; add `source_files` field + parsing to `DocumentConfig` |
| `src/document_strategy.py` | Add `_source_block(role)`; inject into `run_builder`, `run_challenger`, `_invoke_persona` |
| `prompts/prd_builder.md` | Add `{source_files}` block |
| `prompts/prd_challenger.md` | Add `{source_files}` block |
| `prompts/prd_persona_architect.md` | Add `{source_files}` block |
| `prompts/prd_persona_scrum_master.md` | Add `{source_files}` block |
| `prompts/prd_persona_product_owner.md` | Add `{source_files}` block |
| `configs/prd_template.yaml` | Document `source_files:` syntax |
| `configs/iris_prd.yaml` | Add Iris companion files |
| `tests/test_document_config.py` | Add `SourceFileConfig` parsing tests |
| `tests/test_document_strategy.py` | Add `_source_block` and injection tests |

---

### Task 1: SourceFileConfig dataclass + DocumentConfig.source_files

**Files:**
- Modify: `src/config.py:442-558`
- Modify: `tests/test_document_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_document_config.py`:

```python
import logging
from src.config import SourceFileConfig


def test_source_file_config_glob_expansion(tmp_path):
    (tmp_path / "a.md").write_text("A")
    (tmp_path / "b.md").write_text("B")
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "*.md"
              roles: [builder]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 2
    assert all(sf.roles == ("builder",) for sf in cfg.source_files)
    paths = {sf.path for sf in cfg.source_files}
    assert str(tmp_path / "a.md") in paths
    assert str(tmp_path / "b.md") in paths


def test_source_file_config_literal_path_not_found_raises(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "nonexistent.md"
              roles: [builder]
    """)
    with pytest.raises(ValueError, match="nonexistent.md"):
        DocumentConfig.from_yaml(cfg_path)


def test_source_file_config_all_role_expands(tmp_path):
    (tmp_path / "file.md").write_text("content")
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          personas:
            - name: architect
            - name: scrum_master
          source_files:
            - path: "file.md"
              roles: [all]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 1
    roles = set(cfg.source_files[0].roles)
    assert "builder" in roles
    assert "challenger" in roles
    assert "architect" in roles
    assert "scrum_master" in roles


def test_source_file_config_empty_glob_warns_and_skips(tmp_path, caplog):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "*.nonexistent"
              roles: [builder]
    """)
    with caplog.at_level(logging.WARNING):
        cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 0
    assert "*.nonexistent" in caplog.text


def test_source_file_config_absolute_path(tmp_path):
    f = tmp_path / "abs.md"
    f.write_text("content")
    cfg_path = _write_yaml(tmp_path, f"""
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "{f}"
              roles: [builder]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert len(cfg.source_files) == 1
    assert cfg.source_files[0].path == str(f)
    assert cfg.source_files[0].roles == ("builder",)


def test_source_file_config_empty_when_not_declared(tmp_path):
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert cfg.source_files == ()


def test_source_file_config_multiple_roles(tmp_path):
    f = tmp_path / "file.md"
    f.write_text("content")
    cfg_path = _write_yaml(tmp_path, """
        document:
          topic: "T"
          goal: "G"
          source_files:
            - path: "file.md"
              roles: [builder, architect]
    """)
    cfg = DocumentConfig.from_yaml(cfg_path)
    assert set(cfg.source_files[0].roles) == {"builder", "architect"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/josefigueredo/Code/josefigueredo/auto-research
uv run pytest tests/test_document_config.py -k "source_file" -v
```

Expected: `ImportError` or `AttributeError` — `SourceFileConfig` doesn't exist yet.

- [ ] **Step 3: Add `SourceFileConfig` and `_parse_source_files` to `src/config.py`**

After line 449 (after `ArtifactConfig` class), insert:

```python
@dataclass(frozen=True)
class SourceFileConfig:
    """A source file injected into agent prompts during document convergence."""

    path: str                  # resolved absolute path (one file per entry)
    roles: tuple[str, ...]     # which agents receive this file's content


def _parse_source_files(
    raw_entries: list[dict[str, Any]],
    config_dir: Path,
    persona_names: set[str],
) -> tuple[SourceFileConfig, ...]:
    """Resolve glob patterns and expand 'all' roles into concrete SourceFileConfig entries."""
    _log = logging.getLogger("autoresearch")
    all_roles = {"builder", "challenger"} | persona_names
    result: list[SourceFileConfig] = []

    for entry in raw_entries:
        pattern: str = entry["path"]
        raw_roles: list[str] = entry.get("roles", ["builder"])

        roles: set[str] = set()
        for r in raw_roles:
            if r == "all":
                roles |= all_roles
            else:
                roles.add(r)
        roles_tuple = tuple(sorted(roles))

        is_absolute = Path(pattern).is_absolute()
        has_glob = any(c in pattern for c in "*?[")

        if is_absolute:
            p = Path(pattern)
            if not p.exists():
                raise ValueError(f"source_files path not found: {p}")
            result.append(SourceFileConfig(path=str(p), roles=roles_tuple))
        elif has_glob:
            matched = sorted(config_dir.glob(pattern))
            if not matched:
                _log.warning("source_files glob '%s' matched no files — skipping", pattern)
            for m in matched:
                result.append(SourceFileConfig(path=str(m), roles=roles_tuple))
        else:
            p = config_dir / pattern
            if not p.exists():
                raise ValueError(f"source_files path not found: {p}")
            result.append(SourceFileConfig(path=str(p), roles=roles_tuple))

    return tuple(result)
```

- [ ] **Step 4: Add `source_files` field to `DocumentConfig`**

In `DocumentConfig` (around line 472, after `artifacts`), add:

```python
source_files: tuple[SourceFileConfig, ...] = ()
```

- [ ] **Step 5: Add `logging` import and parse `source_files` in `from_yaml`**

At the top of `src/config.py`, `logging` is not yet imported. Add to the imports block:

```python
import logging
```

In `from_yaml`, after the `personas` tuple is built (around line 515) and before the `artifacts` block, insert:

```python
config_dir = path.parent
persona_names = {p.name for p in personas}
source_files = _parse_source_files(
    doc.get("source_files", []), config_dir, persona_names
)
```

Then in the `return cls(...)` call (around line 546), add:

```python
source_files=source_files,
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_document_config.py -k "source_file" -v
```

Expected: 7 tests PASS.

- [ ] **Step 7: Run full suite to catch regressions**

```bash
uv run pytest tests/ --tb=short -q
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/config.py tests/test_document_config.py
git commit -m "feat(config): add SourceFileConfig and source_files to DocumentConfig"
```

---

### Task 2: ConvergeStrategy._source_block + injection

**Files:**
- Modify: `src/document_strategy.py:89-151`
- Modify: `tests/test_document_strategy.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_document_strategy.py` (add `SourceFileConfig` and `PersonaConfig` to the imports from `src.config`, and add `Path` and `patch` imports):

```python
from pathlib import Path
from unittest.mock import patch
from src.config import BackendsConfig, DocumentConfig, PersonaConfig, SourceFileConfig
```

Then add the tests:

```python
# ── _source_block ────────────────────────────────────────────────────────────

def test_source_block_empty_when_no_source_files():
    s = _make_strategy()
    assert s._source_block("builder") == ""


def test_source_block_returns_content_for_matching_role(tmp_path):
    f = tmp_path / "arch.md"
    f.write_text("# Architecture\n\nContent here.")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("builder",)),),
    )
    s = ConvergeStrategy(cfg, {"claude": _make_backend()})
    block = s._source_block("builder")
    assert "arch.md" in block
    assert "# Architecture" in block


def test_source_block_excludes_files_not_matching_role(tmp_path):
    f = tmp_path / "file.md"
    f.write_text("secret content")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("architect",)),),
    )
    s = ConvergeStrategy(cfg, {"claude": _make_backend()})
    assert s._source_block("builder") == ""
    assert "secret content" in s._source_block("architect")


def test_source_block_warns_and_skips_unreadable_file(tmp_path, caplog):
    import logging
    f = tmp_path / "gone.md"
    f.write_text("content")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("builder",)),),
    )
    s = ConvergeStrategy(cfg, {"claude": _make_backend()})
    f.unlink()
    with caplog.at_level(logging.WARNING):
        block = s._source_block("builder")
    assert block == ""
    assert "gone.md" in caplog.text


def test_run_builder_injects_source_files(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Reference Doc")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("builder",)),),
    )
    s = ConvergeStrategy(cfg, {"claude": _make_backend("# PRD Output")})
    with patch("src.document_strategy.render", return_value="prompt") as mock_render:
        s.run_builder("", [], _call_with, human_decisions=[])
    _, kwargs = mock_render.call_args
    assert "# Reference Doc" in kwargs["source_files"]


def test_run_challenger_injects_source_files(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Challenger Ref")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("challenger",)),),
    )
    s = ConvergeStrategy(cfg, {"claude": _make_backend("[]")})
    with patch("src.document_strategy.render", return_value="[]") as mock_render:
        s.run_challenger("prd text", _call_with)
    _, kwargs = mock_render.call_args
    assert "# Challenger Ref" in kwargs["source_files"]


def test_invoke_persona_injects_source_files(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Architect Ref")
    cfg = DocumentConfig(
        topic="T", goal="G",
        personas=(PersonaConfig("architect"),),
        source_files=(SourceFileConfig(path=str(f), roles=("architect",)),),
    )
    s = ConvergeStrategy(cfg, {"claude": _make_backend("[]")})
    with patch("src.document_strategy.render", return_value="[]") as mock_render:
        s._invoke_persona(cfg.personas[0], "prd", _call_with)
    _, kwargs = mock_render.call_args
    assert "# Architect Ref" in kwargs["source_files"]


def test_run_builder_source_files_empty_when_no_match(tmp_path):
    f = tmp_path / "ref.md"
    f.write_text("# Persona Only")
    cfg = DocumentConfig(
        topic="T", goal="G",
        source_files=(SourceFileConfig(path=str(f), roles=("architect",)),),
    )
    s = ConvergeStrategy(cfg, {"claude": _make_backend("# PRD")})
    with patch("src.document_strategy.render", return_value="prompt") as mock_render:
        s.run_builder("", [], _call_with, human_decisions=[])
    _, kwargs = mock_render.call_args
    assert kwargs["source_files"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_document_strategy.py -k "source_block or source_files" -v
```

Expected: `AttributeError: 'ConvergeStrategy' object has no attribute '_source_block'`

- [ ] **Step 3: Add `_source_block` method and `logging` import to `src/document_strategy.py`**

Add to imports at the top of `src/document_strategy.py`:

```python
import logging
from pathlib import Path

log = logging.getLogger("autoresearch")
```

Add `_source_block` as a new method in `ConvergeStrategy`, after the `__init__` (around line 88):

```python
# ── Source file injection ────────────────────────────────────────────────────

def _source_block(self, role: str) -> str:
    """Return formatted Markdown block of source files visible to `role`."""
    matching = [sf for sf in self._config.source_files if role in sf.roles]
    if not matching:
        return ""
    parts = []
    for sf in matching:
        try:
            content = Path(sf.path).read_text(encoding="utf-8")
        except OSError:
            log.warning("source_files: could not read %s — skipping", sf.path)
            continue
        parts.append(f"### {sf.path}\n\n{content}")
    return "\n\n---\n\n".join(parts)
```

- [ ] **Step 4: Inject `source_files` into `run_builder`**

Replace the `render(...)` call in `run_builder` (lines 102-110):

```python
prompt = render(
    "prd_builder.md",
    topic=self._config.topic,
    goal=self._config.goal,
    source_material=self._config.source_material,
    source_files=self._source_block("builder"),
    current_prd=prd,
    patches=patches_block,
    human_decisions=human_block,
)
```

- [ ] **Step 5: Inject `source_files` into `run_challenger`**

Replace the `render(...)` call in `run_challenger` (line 118):

```python
prompt = render(
    "prd_challenger.md",
    prd=prd,
    topic=self._config.topic,
    source_files=self._source_block("challenger"),
)
```

- [ ] **Step 6: Inject `source_files` into `_invoke_persona`**

Replace the `render(...)` call in `_invoke_persona` (line 149):

```python
prompt = render(
    prompt_file,
    prd=prd,
    topic=self._config.topic,
    source_files=self._source_block(persona.name),
)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/test_document_strategy.py -k "source_block or source_files" -v
```

Expected: 9 new tests PASS.

- [ ] **Step 8: Run full suite**

```bash
uv run pytest tests/ --tb=short -q
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/document_strategy.py tests/test_document_strategy.py
git commit -m "feat(strategy): add _source_block and inject source_files into builder/challenger/personas"
```

---

### Task 3: Prompt template updates

**Files:**
- Modify: `prompts/prd_builder.md`
- Modify: `prompts/prd_challenger.md`
- Modify: `prompts/prd_persona_architect.md`
- Modify: `prompts/prd_persona_scrum_master.md`
- Modify: `prompts/prd_persona_product_owner.md`

- [ ] **Step 1: Update `prompts/prd_builder.md`**

The current file is:
```
## Source Material
{source_material}

{human_decisions}

## Current Document
{current_prd}
```

Replace with:
```
## Source Material
{source_material}

## Reference Files

{source_files}

{human_decisions}

## Current Document
{current_prd}
```

- [ ] **Step 2: Update `prompts/prd_challenger.md`**

Current file starts with:
```
You are an internal consistency auditor reviewing a Product Requirements Document.

## Topic
{topic}

## Document to Review
{prd}
```

Replace with:
```
You are an internal consistency auditor reviewing a Product Requirements Document.

## Topic
{topic}

## Reference Files

{source_files}

## Document to Review
{prd}
```

- [ ] **Step 3: Update `prompts/prd_persona_architect.md`**

Current file has:
```
## Document Under Review
{prd}

## Topic
{topic}
```

Add `## Reference Files\n\n{source_files}\n\n` before `## Document Under Review`:

```
## Reference Files

{source_files}

## Document Under Review
{prd}

## Topic
{topic}
```

- [ ] **Step 4: Update `prompts/prd_persona_scrum_master.md`**

Same pattern — add before `## Document Under Review`:

```
## Reference Files

{source_files}

## Document Under Review
{prd}

## Topic
{topic}
```

- [ ] **Step 5: Update `prompts/prd_persona_product_owner.md`**

Same pattern — add before `## Document Under Review`:

```
## Reference Files

{source_files}

## Document Under Review
{prd}

## Topic
{topic}
```

- [ ] **Step 6: Run full suite to verify prompt changes don't break tests**

```bash
uv run pytest tests/ --tb=short -q
```

Expected: all tests PASS. (Tests mock `render()` so prompt content changes don't affect them directly; the test coverage for prompt injection is in Task 2's tests.)

- [ ] **Step 7: Commit**

```bash
git add prompts/prd_builder.md prompts/prd_challenger.md prompts/prd_persona_architect.md prompts/prd_persona_scrum_master.md prompts/prd_persona_product_owner.md
git commit -m "feat(prompts): add {source_files} block to builder, challenger, and persona prompts"
```

---

### Task 4: Config file updates

**Files:**
- Modify: `configs/prd_template.yaml`
- Modify: `configs/iris_prd.yaml`

- [ ] **Step 1: Update `configs/prd_template.yaml`**

Add a `source_files:` section after the existing `source_material:` line:

```yaml
  # Optional: path or URL to seed material (existing doc, RFC, notes).
  source_material: ""

  # Optional: companion files injected into agent prompts.
  # Paths are relative to this config file's directory. Globs supported.
  # Roles: builder, challenger, any persona name, or "all".
  source_files: []
  # Example:
  # source_files:
  #   - path: docs/**/*.md
  #     roles: [builder, architect]
  #   - path: docs/product/*.md
  #     roles: [all]
  #   - path: /absolute/path/to/file.md
  #     roles: [builder, product_owner]
```

- [ ] **Step 2: Update `configs/iris_prd.yaml`**

Add the Iris companion files. Current file has `source_material` pointing to the PRD path. Replace `source_material` with `source_files` targeting the full document package:

```yaml
  source_material: ""

  source_files:
    # Primary PRD — builder sees it as seed material
    - path: /Users/josefigueredo/Desktop/AI-R/PRD.md
      roles: [builder]

    # Architecture decisions — architect and builder need them
    - path: /Users/josefigueredo/Desktop/AI-R/docs/architecture/adr/*.md
      roles: [builder, architect]
    - path: /Users/josefigueredo/Desktop/AI-R/docs/architecture/PLATFORM_ARCH.md
      roles: [builder, architect]
    - path: /Users/josefigueredo/Desktop/AI-R/docs/architecture/strategy/*.md
      roles: [builder, architect]

    # Product docs — product_owner and scrum_master
    - path: /Users/josefigueredo/Desktop/AI-R/docs/product/*.md
      roles: [builder, product_owner, scrum_master]

    # Design docs — product_owner
    - path: /Users/josefigueredo/Desktop/AI-R/docs/design/*.md
      roles: [builder, product_owner]

    # Reference and companion
    - path: /Users/josefigueredo/Desktop/AI-R/docs/reference/*.md
      roles: [builder]
    - path: /Users/josefigueredo/Desktop/AI-R/docs/companion/*.md
      roles: [builder, architect]
```

- [ ] **Step 3: Run full suite one final time**

```bash
uv run pytest tests/ --tb=short -q
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add configs/prd_template.yaml configs/iris_prd.yaml
git commit -m "feat(config): add source_files examples to prd_template and iris_prd configs"
```
