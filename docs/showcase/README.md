# Showcase

Visual and interactive artifacts for the Multi-LLM Adversarial Convergence Framework.

Open [`index.html`](./index.html) in a browser for the full hub — every entry below is linked from there.

---

## Presentations

| File | Slides | Description |
|------|--------|-------------|
| [`deck/clean.html`](./deck/clean.html) | 34 | **Main deck** — the problem, Karpathy's loop, 11 agentic design patterns, and a full adversarial demo run |
| [`deck/strategies.html`](./deck/strategies.html) | 7 | **Strategies deep-dive** — all 6 execution strategies (single, ensemble, parallel, serial, specialist, adversarial) as individual flow diagrams |
| [`presenter/control.html`](./presenter/control.html) | — | **Presenter view** — synced speaker notes for `clean.html`, cross-tab navigation via `localStorage` |

Navigation: `→` / `Space` next · `←` / `PgUp` prev · `Home` / `End` jump · `#N` deep-link to slide N.

---

## Interactive Tools

| File | Description |
|------|-------------|
| [`widgets/dashboard-for-slide.html`](./widgets/dashboard-for-slide.html) | **Live replay dashboard** — step through the real `aws_api_gateway_opus_sonnet_codex` run iteration by iteration: score sparkline, dimension grid, state machine, cost block |
| [`widgets/shell-demo.html`](./widgets/shell-demo.html) | **Shell demo** — standalone animated terminal playback |

---

## Reference

| File | Description |
|------|-------------|
| [`glossary/glossary.html`](./glossary/glossary.html) | **Concept glossary** — bilingual (es / en) static explanations for mixed technical and non-technical audiences |
| [`common/HARNES.md`](./common/HARNES.md) | Engineering framing for the harness layer (OS analogy, three-layer stack, responsibilities) — used as speaker prep material |

---

## Showcase Outputs — AWS API Gateway Research

Three HTML reports produced from the **main demo run** (`aws_api_gateway_opus_sonnet_codex`) by changing only `reporting.output_style`:

| File | Style | Report |
|------|-------|--------|
| [`aws-api-gateway/report-default.html`](./aws-api-gateway/report-default.html) | `default` | Exploratory synthesis — recommendations first, then dimensions and caveats |
| [`aws-api-gateway/report-paper.html`](./aws-api-gateway/report-paper.html) | `paper` | Research-paper structure — abstract, methodology, discussion, deterministic references |
| [`aws-api-gateway/report-technical.html`](./aws-api-gateway/report-technical.html) | `technical_doc` | Engineering decision format — comparison tables, ADR-style recommendation, disqualifiers |

Full run artifacts (audit trail, synthesis, results, citations, etc.) live in `output/aws_api_gateway_opus_sonnet_codex/`.

---

## Legacy (Marp-based)

Older Marp-rendered decks kept for historical reference. The current `deck/clean.html` supersedes all of these.

| File | Notes |
|------|-------|
| [`legacy/demo_merged_pro.html`](./legacy/demo_merged_pro.html) | Most recent Marp iteration before the clean-deck rewrite |
| [`legacy/demo_merged_commented_es_vbg.html`](./legacy/demo_merged_commented_es_vbg.html) | Spanish-commented version with video background |
| [`legacy/demo.html`](./legacy/demo.html) | Original 30-minute presentation |
| [`legacy/dashboard.html`](./legacy/dashboard.html) | Legacy dashboard view |

---

## Shared Assets

| Path | Description |
|------|-------------|
| `common/animation-veryslow.mp4` | Persistent background video used by all HTML artifacts |
| `common/patterns/*.svg` | 12 agentic design pattern diagrams (`00` – `11`) in the CRT/phosphor palette |
