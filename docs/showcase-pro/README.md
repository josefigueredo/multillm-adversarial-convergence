# Showcase — PRO edition

Same content as `../showcase/`, plus the **slides-template-pro** synchronization layer: the presenter drives every viewer's browser over WebSocket — slide changes, view switches (deck ↔ glossary ↔ demo ↔ dashboard), and inline glossary-term jumps.

Open [`index.html`](./index.html) in a browser for the full hub.

> **To actually synchronize**, the FastAPI control plane in [`../../pro/`](../../pro/) must be running. Without it, the pages render fine but won't sync — they fall back to standalone behavior.

---

## Running the pro stack

```bash
# from repo root (requires uv: https://docs.astral.sh/uv/)
cd pro
make install                                    # one-time: uv sync --extra dev
SLIDES_API_KEY=$(openssl rand -hex 12) make dev # uv run uvicorn … on :8000
```

Then in a browser:

- `http://localhost:8000/showcase/index.html` — viewer landing
- `http://localhost:8000/showcase/deck/deck.html` — the deck
- `http://localhost:8000/showcase/presenter/control.html` — presenter (key is auto-injected from `/api/runtime-config` for local dev)

The presenter POSTs each slide change to `/api/control`; viewers connected to `/ws` follow if they have the corner "follow presenter" toggle enabled (per-viewer, persisted in `localStorage`).

---

## Presentations

| File | Slides | Description |
|------|--------|-------------|
| [`deck/deck.html`](./deck/deck.html) | **42** | **Main deck** — intro · I·Strategies · II·Patterns · III·Demo · IV·Adversarial · spec |
| [`presenter/control.html`](./presenter/control.html) | — | **Presenter view** — speaker notes for all 42 slides, broadcasts via POST `/api/control` |

The merged deck adds the 7-slide **Strategies** section (`single`, `ensemble`, `parallel`, `serial`, `specialist`, `adversarial`) as section I, pushing the original Patterns / Demo / Adversarial sections to II / III / IV.

Navigation: `→` / `Space` next · `←` / `PgUp` prev · `Home` / `End` jump · `#N` deep-link.

---

## Interactive Tools

| File | Description |
|------|-------------|
| [`widgets/dashboard-for-slide.html`](./widgets/dashboard-for-slide.html) | **Live replay dashboard** — step through the `aws_api_gateway_opus_sonnet_codex` run iteration by iteration |
| [`widgets/shell-demo.html`](./widgets/shell-demo.html) | **Shell demo** — standalone animated terminal playback |

---

## Reference

| File | Description |
|------|-------------|
| [`glossary/glossary.html`](./glossary/glossary.html) | **Concept glossary** — bilingual (es / en) static explanations |
| [`common/HARNES.md`](./common/HARNES.md) | Engineering framing for the harness layer — speaker prep material |

---

## Showcase Outputs — AWS API Gateway Research

Three HTML reports produced from the demo run (`aws_api_gateway_opus_sonnet_codex`) by changing only `reporting.output_style`:

| File | Style | Report |
|------|-------|--------|
| [`aws-api-gateway/report-default.html`](./aws-api-gateway/report-default.html) | `default` | Exploratory synthesis |
| [`aws-api-gateway/report-paper.html`](./aws-api-gateway/report-paper.html) | `paper` | Research-paper structure |
| [`aws-api-gateway/report-technical.html`](./aws-api-gateway/report-technical.html) | `technical_doc` | Engineering decision format |

---

## Sync layer

The `sync/` folder carries the pro adapter scripts — already wired into every viewer page in this folder:

| Script | Loaded by | Role |
|--------|-----------|------|
| `sync.js` | every viewer page (`data-role="viewer"`) | WebSocket connect, monotonic-version state filter |
| `deck-sync.js` | `deck/deck.html` | Drive `data-slide` from broadcast `slide` |
| `glossary-sync.js` | `glossary/glossary.html` | Open the broadcast `glossary_term` |
| `glossary-link.js` | `deck/deck.html` | `<span class="g-term">` click → presenter pushes term |
| `glossary-link.css` | `deck/deck.html` | Underline styling for `.g-term` |
| `follow-toggle.js` | every viewer page | Per-viewer "follow presenter" opt-in toggle |

---

## What's different from `../showcase/`

| Aspect | `showcase/` | `showcase-pro/` |
|--------|-------------|-----------------|
| Sync mechanism | `localStorage` (same machine, cross-tab only) | WebSocket via FastAPI / API Gateway (anywhere) |
| Presenter broadcast | `localStorage.setItem('deckCurrentSlide', N)` | `POST /api/control` with `X-API-Key` |
| Deck slide count | 34 (`clean.html`) + 7 standalone (`strategies.html`) | 42 (merged, single file) |
| Section structure | I·Patterns · II·Demo · III·Adversarial | I·Strategies · II·Patterns · III·Demo · IV·Adversarial |
| Glossary-term clicks | None | `.g-term` underline + presenter broadcast |
| Follow-presenter toggle | n/a | Per-viewer opt-in (`localStorage`) |
| Backend required | none (pure static) | FastAPI (local) or Lambda (prod) — see [`../../pro/`](../../pro/) |

Originals are untouched in [`../showcase/`](../showcase/).
