# Demo Deck v2

Revised 30-minute demo deck for the research mode showcase. Built with [Marp](https://marp.app/).

## What changed from v1

- **Staging disclosure** on the title slide — the audience knows upfront this is a real run played back at speed
- **Value prop before origin story** — one sentence on what the problem is before the Karpathy backstory
- **Agentic design patterns as a central section** — 11 recognized patterns grouped into Engine / Topology / Guardrails, each with a canonical reference
- **Adversarial critique in action** — real critique output from the `localstack_alternatives` run, showing specific factual challenges the critic raised
- **Score progression table** — iter 001 (62.0) → iter 009 (76.3) with the dip at iter 007 explained
- **Rewritten takeaways** — conclusions from what was witnessed, not a feature glossary
- **Real run stats** — backends used, iterations, cost, dimensions, best score
- **Presenter runbook in the comment block** — not a slide the audience sees
- **Slide timing budget** annotated in comments for each section

## Render

The loop diagram (`loop.svg`) is pre-rendered from `loop.mmd` using [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli).
Marp CLI does not execute JavaScript at render time, so Mermaid code blocks won't work in exported files — pre-rendered SVG is the correct approach.

To regenerate the diagram after editing `loop.mmd`:

```bash
mmdc -i docs/showcase/showcase_v2/loop.mmd -o docs/showcase/showcase_v2/loop.svg -b transparent
```

To render the deck:

```bash
# HTML — best for screen recording (self-contained, no server needed)
npx @marp-team/marp-cli --allow-local-files docs/showcase/showcase_v2/demo.md --html -o docs/showcase/showcase_v2/demo.html

# PowerPoint
npx @marp-team/marp-cli --allow-local-files docs/showcase/showcase_v2/demo.md -o docs/showcase/showcase_v2/demo.pptx

# PDF
npx @marp-team/marp-cli --allow-local-files docs/showcase/showcase_v2/demo.md --pdf -o docs/showcase/showcase_v2/demo.pdf
```

## Slide map (23 slides, ~30 min)

| Slides | Section | Time |
|---|---|---|
| 1 | Title + staging disclosure | 1 min |
| 2 | The problem | 1 min |
| 3 | Origin: Karpathy comparison | 2 min |
| 4 | The loop diagram | 2 min |
| 5 | **Patterns divider** | — |
| 6 | Patterns: The Engine (Evaluator-Optimizer, LLM-as-Judge, Reflection) | 3 min |
| 7 | Patterns: The Topology (Orchestrator, Role Topology, Routing, Parallel, Serial) | 2 min |
| 8 | Patterns: The Guardrails (Adversarial Critique, Sandbox, HITL) | 2 min |
| 9 | **Demo divider** | — |
| 10 | The config walkthrough | 2 min |
| 11 | Dry-run + staged run | 3 min |
| 12 | **Adversarial critique divider** | — |
| 13 | The critic finds real errors (real output from iter 001) | 3 min |
| 14 | Score progression (iter 001–009) | 2 min |
| 15 | From one corpus — three artifacts | 1 min |
| 16 | Output: `default` | 1.5 min |
| 17 | Output: `paper` | 1.5 min |
| 18 | Output: `technical_doc` | 1.5 min |
| 19 | Every run is fully replayable | 1.5 min |
| 20 | Trust + certainty | 1 min |
| 21 | This run (cost + stats) | 0.5 min |
| 22 | Takeaways (as conclusions) | 1 min |
| 23 | Try it | 1 min |

## Related

- Original deck: [`../demo.md`](../demo.md)
- Showcase artifacts: [`../localstack-alternatives/`](../localstack-alternatives/)
- Patterns reference: [`../../design/agentic-design-patterns.md`](../../design/agentic-design-patterns.md)
