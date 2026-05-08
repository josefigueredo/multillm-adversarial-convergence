---
marp: true
theme: default
paginate: true
size: 16:9
backgroundColor: '#fafafa'
header: 'Multi-LLM Adversarial Convergence Framework'
footer: 'github.com/josefigueredo/multillm-adversarial-convergence'
style: |
  :root {
    --color-primary: #1e3a5f;
    --color-accent: #2563eb;
    --color-warn: #d97706;
    --color-ok: #16a34a;
    --color-subtle: #64748b;
  }
  section {
    font-size: 26px;
    font-family: 'Segoe UI', system-ui, sans-serif;
    color: #1a1a1a;
    padding: 40px 52px;
  }
  section.lead {
    text-align: center;
    justify-content: center;
  }
  section.divider {
    background: #1e3a5f;
    color: #fff;
    text-align: center;
    justify-content: center;
  }
  section.divider h2 {
    color: #93c5fd;
    font-size: 1.8em;
    margin-bottom: 0.2em;
  }
  section.divider p {
    color: #cbd5e1;
    font-size: 0.85em;
  }
  h1 { color: #1e3a5f; font-size: 1.6em; margin-bottom: 0.4em; }
  h2 { color: #2563eb; font-size: 1.25em; margin-top: 0; }
  h3 { color: #374151; font-size: 1em; margin-bottom: 0.3em; }
  code {
    background: #f1f5f9;
    color: #0f172a;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 0.9em;
  }
  pre {
    background: #0f172a;
    color: #e2e8f0;
    padding: 18px 20px;
    border-radius: 8px;
    font-size: 19px;
    line-height: 1.5;
    /* If Marp's auto-fit kicks in, scale toward the top-left edge
       so code reads left-aligned (default origin is center). */
    transform-origin: top left;
  }
  pre code { background: none; color: inherit; padding: 0; }
  table {
    font-size: 20px;
    width: 100%;
    border-collapse: collapse;
  }
  th {
    background: #1e3a5f;
    color: #fff;
    padding: 8px 12px;
    text-align: left;
  }
  td { padding: 7px 12px; border-bottom: 1px solid #e2e8f0; }
  tr:nth-child(even) td { background: #f8fafc; }
  blockquote {
    border-left: 4px solid #2563eb;
    background: #eff6ff;
    padding: 10px 18px;
    margin: 12px 0;
    color: #1e3a5f;
    font-style: normal;
  }
  .tag {
    display: inline-block;
    background: #dbeafe;
    color: #1d4ed8;
    border-radius: 4px;
    padding: 1px 8px;
    font-size: 0.78em;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  footer { font-size: 13px; color: #94a3b8; }
  header { font-size: 13px; color: #94a3b8; }
  /* Density classes — apply per-slide via <!-- _class: tight --> or tighter */
  section.tight { font-size: 22px; padding: 32px 48px; }
  section.tight h1 { font-size: 1.45em; margin-bottom: 0.25em; }
  section.tight h2 { font-size: 1.15em; margin-bottom: 0.25em; }
  section.tight table { font-size: 17px; }
  section.tight th { padding: 6px 10px; }
  section.tight td { padding: 4px 10px; }
  section.tight pre { font-size: 16px; line-height: 1.35; padding: 12px 16px; }
  section.tight blockquote { padding: 8px 14px; margin: 8px 0; font-size: 0.92em; }
  section.tight p, section.tight li { margin: 0.25em 0; }
  section.tighter { font-size: 20px; padding: 28px 44px; }
  section.tighter h1 { font-size: 1.35em; margin-bottom: 0.2em; }
  section.tighter h2 { font-size: 1.1em; margin-bottom: 0.2em; }
  section.tighter pre { font-size: 14px; line-height: 1.3; padding: 10px 14px; }
  section.tighter code { font-size: 0.85em; }
  section.tighter blockquote { padding: 6px 12px; margin: 6px 0; font-size: 0.9em; }
  section.tighter p, section.tighter li { margin: 0.2em 0; }
  /* Pattern-slide layout: image-led, then explanation below */
  section.pattern { font-size: 21px; padding: 28px 48px; }
  section.pattern h2 { font-size: 1.2em; margin-bottom: 0.15em; }
  section.pattern blockquote { font-size: 0.9em; padding: 6px 14px; margin: 4px 0 10px; }
  section.pattern p, section.pattern li { margin: 0.2em 0; }
  section.pattern img { display: block; margin: 4px auto 6px; max-height: 320px; }
  section.pattern .ref { color: #64748b; font-size: 0.85em; margin-top: 6px; }
---

<!--
DEMO RUNBOOK — READ BEFORE PRESENTING
======================================
Format: staged run (real outputs, played back) + full pattern deep-dive.
Length: ~45-50 minutes presented; designed to also be readable self-paced.

This deck merges:
  - demo.md           (the live 30-min staged-demo flow + code snippets)
  - demo_extended.md  (one slide per agentic pattern, with diagrams)

So the demo flow is intact — but every pattern named in the original
"Engine / Topology / Guardrails" group slides is now expanded into its
own slide with mechanism, codebase mapping, and canonical reference.

Terminal pre-work:
  1. cd multillm-adversarial-convergence
  2. Open: configs/research/localstack_alternatives_copilot_codex.yaml
  3. Have open in browser (tabs):
       docs/showcase/localstack-alternatives/raw/report.html
       docs/showcase/localstack-alternatives/paper/report.html
       docs/showcase/localstack-alternatives/technical/report.html
  4. Have ready: cat docs/showcase/localstack-alternatives/technical/audit_trail.jsonl | python3 -m json.tool | head -60
  5. Pre-render diagrams: ./build.sh  (builds patterns/*.mmd → patterns/*.svg + loop.svg)

SLIDE TIMING (~45-50 min full; ~30 min if patterns skimmed)
  Slides 1–4    (intro + origin + loop)             ~5 min
  Slide  5      (divider — patterns)                 ~10 sec
  Slide  6      (why these patterns matter)         ~2 min
  Slides 7–17   (the 11 patterns, ~1 min each)     ~12 min
  Slide  18     (strategy lattice — composition)    ~3 min
  Slide  19     (divider — demo)                    ~10 sec
  Slides 20–21  (config + dry-run)                  ~3 min
  Slide  22     (divider — adversarial)             ~10 sec
  Slides 23–24  (critic + score progression)        ~5 min
  Slides 25–28  (artifacts + 3 output styles)       ~5 min
  Slides 29–31  (replayable + trust + cost)         ~3 min
  Slides 32–33  (takeaways + try it)                ~2 min

STAGING NOTE: Tell the audience on slide 1. Never hide it.
-->

<!-- _class: lead -->
<!-- _paginate: false -->

# Multi-LLM Adversarial Convergence Framework

### Make competing LLMs argue until they converge on the best answer

<br>

> **Staged demo** — this is a real run played back at speed.
> All artifacts shown are live outputs from the actual execution.

---
<!-- TIMING: 1 min — the problem in one sentence before any origin story -->

## The problem

Single-model research is **non-deterministic and unverifiable**.
One LLM, one pass, one perspective.

> You can't know what it missed, what it fabricated with confidence, or whether a different model would have reached the same conclusion.

**This framework's answer:**

- Run multiple backends on the same topic
- Make them **score, critique, and argue with each other**
- Keep only what survives adversarial review
- Emit a full evidence trail so you can audit every claim

---
<!-- TIMING: 2 min — origin story, now that they know what they're watching -->

## Origin: Karpathy's `autoresearch`

The loop isn't original. [Andrej Karpathy's `autoresearch`](https://github.com/karpathy/autoresearch) runs:

> *modify code → train 5 min on GPU → measure loss → keep or revert*

The insight: **this shape applies to anything you can score**.

| Karpathy's `autoresearch` | This framework |
|---|---|
| GPU training run | LLM backend call |
| Loss function | Heuristic 40% + LLM judge 60% |
| Neural network weights | Knowledge corpus |
| ~5 min per iteration | One backend call per iteration |
| Stops when loss plateaus | Stops on `max_iterations` or `target_dimensions_total` |

Same loop. Different substrate: **knowledge instead of weights**.

---
<!-- TIMING: 2 min — loop diagram. Slow down here. This is the mental model for everything that follows. -->

## The loop

![w:1150](loop.svg)

<br>

| | |
|---|---|
| **Critique** (purple) | A *different* backend — different priors, different blind spots |
| **Decide** (amber) | KEEP grows the corpus · DISCARD retries the same dimension |
| **Compress** (teal) | Every N iterations: distill, drop noise, bound context cost |

Stops on `Ctrl+C`, `max_iterations`, or `target_dimensions_total`.

---
<!-- _class: divider -->
<!-- TIMING: transition, 10 sec -->

## Agentic Design Patterns

### Engine · Topology · Guardrails

*11 named patterns from the research literature — each cited, each replaceable.*

---
<!-- _class: tight -->
<!-- TIMING: 2 min — preamble before the pattern parade. Why bother naming them? -->

## Why these patterns matter

This codebase is **not a collection of hacks**.

Every component maps to a named pattern from the agentic-design literature.
That matters for three reasons:

1. **Replaceability** — when a pattern is named, swapping the implementation is mechanical
2. **Defensibility** — code review can ask *"is this Evaluator-Optimizer or Reflection?"* instead of *"is this fine?"*
3. **Onboarding** — new contributors recognise shapes; they don't have to reverse-engineer intent

> The 11 patterns shown here are not all of agentic design — they're the subset that this framework actually composes.
> Roughly: **engine** (3) + **topology** (5) + **guardrails** (3).

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 1: the outer loop itself -->

## 1 · Evaluator-Optimizer

> *The outer loop. Propose, score, keep or discard, repeat.*

![w:880](patterns/01-evaluator-optimizer.svg)

**The pattern** — A generator produces candidates. An evaluator scores them against an objective. The system keeps high-scoring candidates and discards (or revises) the rest. The loop runs until score plateaus or a budget is exhausted.

**In this codebase**
- `src/research_loop.py` — owns the iteration cycle
- `src/scorer.py` — composite score (heuristic 40% + judge 60%); see `IterationScore`
- `KEEP` vs `DISCARD` decision recorded per iteration in `audit_trail.jsonl`

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1.5 min — Pattern 2: the heart of the trust model. Spend a beat on independence. -->

## 2 · LLM-as-Judge

> *A different model scores the candidate. No self-grading.*

![w:920](patterns/02-llm-as-judge.svg)

**The pattern** — The model that *produces* an output cannot reliably *score* it (self-evaluation is biased toward verbosity and confidence). A separate judge model — ideally from a different family — evaluates outputs against a rubric. Its score is one input to the keep/discard decision.

**In this codebase**
- `src/scorer.py` — `judge_response()` calls a non-producer backend
- Hybrid: 40% deterministic heuristic + 60% LLM judge (configurable via `scoring.weights`)
- Multi-judge mode: `evaluation.judges = [...]` enables consensus + disagreement detection (`detect_judge_disagreement()`)

<span class="ref">**Reference:** [agentic-design.ai — LLM-as-Judge](https://agentic-design.ai/patterns/reflection/llm-as-judge) · [arXiv 2410.10934](https://arxiv.org/abs/2410.10934)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 3: why context bound matters. Forced rank-and-prune. -->

## 3 · Reflection / Self-Compression

> *Every N iterations: distill the corpus, drop noise.*

![w:1080](patterns/03-reflection-compression.svg)

**The pattern** — Naive iteration grows context monotonically — every kept claim is added to the working memory. Without compression, runs balloon: token costs explode, the model loses focus, and signal-to-noise drops. Compression is a forced rank-and-prune step where the agent rewrites its own corpus, keeping only what it judges load-bearing.

**In this codebase**
- `compression_interval` config flag (default: every 4 iterations)
- The agent re-reads its own corpus and emits a distilled version
- Audit event: `corpus_compressed` with before/after token counts

<span class="ref">**Reference:** [Andrew Ng — Agentic Patterns](https://www.deeplearning.ai/the-batch/how-agents-can-improve-llm-performance/)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 4: who owns lifecycle. Workers do not call workers. -->

## 4 · Orchestrator / Subagents

> *One owner of lifecycle. Many narrow-contract workers.*

![w:780](patterns/04-orchestrator-subagents.svg)

**The pattern** — Centralise control flow in one component. Backends are *workers* — they receive a task, return a result, and have no awareness of the wider lifecycle. This makes them replaceable, testable, and prevents cross-cutting state from leaking into transport adapters.

**In this codebase**
- `src/orchestrator.py` — the only owner of phase transitions, convergence checks, compression triggers
- `src/backends/` — adapters with a single contract: `run(prompt) → response`
- Backends never call each other; they only return to the orchestrator

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 5: roles vs models. The swap surface. -->

## 5 · Multi-Agent Role Topology

> *Configure roles, not models. Swap backends without changing logic.*

![w:900](patterns/05-role-topology.svg)

**The pattern** — Roles (`primary`, `judge`, `utility`, `research[]`) are abstract names that the codebase reasons about. Each is bound to a concrete backend at config time. The same orchestrator code works whether `judge` is `codex-cli` today and `gemini-api` tomorrow — the indirection is the swap surface.

**In this codebase**
- `configs/research/<topic>.yaml` — `execution.backends` map roles to backend IDs
- `src/config.py` — `BackendsConfig` schema; validates role completeness
- Role names appear in audit events: `role=judge backend=codex-cli`

<span class="ref">**Reference:** [arXiv 2405.10467 — Multi-Agent Role Topology](https://arxiv.org/abs/2405.10467)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 6: dispatch by persona. -->

## 6 · Routing / Specialist Dispatch

> *Each dimension goes to the backend best suited for it.*

![w:920](patterns/06-routing-specialist.svg)

**The pattern** — Different work needs different priors. Coverage-style breadth questions favour a broad-recall model; precision-critique questions favour a model trained for adversarial review. The router inspects the dimension's declared persona and dispatches accordingly.

**In this codebase**
- `src/strategy.py` — `specialist` strategy
- Each dimension declares a persona in config; persona → backend lookup at dispatch time
- Falls back to `primary` if no specialist matches

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 7: variance reduction via redundancy. -->

## 7 · Parallelization (Ensemble)

> *Fan out to all backends in parallel. Merge via judge.*

![w:880](patterns/07-parallel-ensemble.svg)

**The pattern** — Variance reduction. Run the same task across N backends simultaneously; their answers will diverge in interesting ways. A judge picks the strongest, or a vote/merge step combines them. Useful when the cost of a wrong answer is high and budget allows redundancy.

**In this codebase**
- `src/strategy.py` — `ensemble` and `parallel` strategies
- `concurrent.futures.ThreadPoolExecutor` — bounded parallelism
- Judge selects best response or synthesises an ensemble answer

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 8: stage specialisation. -->

## 8 · Prompt Chaining (Serial)

> *Backends take turns. Each stage receives the previous stage's output.*

![w:960](patterns/08-prompt-chaining-serial.svg)

**The pattern** — Specialisation by stage rather than by task. One backend researches; the next critiques; the next refines. Each stage operates on the previous stage's output, so the chain accumulates context. Cheaper than ensemble (no parallel calls) but slower end-to-end.

**In this codebase**
- `src/strategy.py` — `serial` strategy
- Stage N+1's prompt includes stage N's full output as context
- Used when stages have asymmetric specialisations (research → critique → synthesis)

<span class="ref">**Reference:** [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1.5 min — Pattern 9: the demo strategy. Different RLHF = different blind spots. -->

## 9 · Adversarial Critique

> *Researcher · Critic · Arbitrator — across different model families.*

![w:880](patterns/09-adversarial-critique.svg)

**The pattern** — A debate-shaped variant of serial chaining. The researcher proposes claims; the critic — *deliberately a different model family* — looks for errors, weak citations, and logical gaps; the arbitrator (different family again) renders a verdict. Different RLHF training produces different blind spots, so weaknesses in one model are visible to another.

**In this codebase**
- `src/strategy.py` — `adversarial` strategy (used in the demo run)
- Three roles: `researcher`, `critic`, `arbitrator` — each a different backend family
- Audit log records every critique flag and arbitrator decision

<span class="ref">**Reference:** [arXiv 2305.19118 — Multi-Agent Debate](https://arxiv.org/abs/2305.19118)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1.5 min — Pattern 10: sandbox as IAM. Anchor to enterprise concerns. -->

## 10 · Tool Use + Sandboxed Execution

> *The capability registry is the agentic equivalent of an IAM policy.*

![w:920](patterns/10-tool-use-sandbox.svg)

**The pattern** — Agents need tools (web fetch, code execution, file write) but every tool widens the attack surface. The registry approach: every tool is declared with its capabilities; unclassified calls are denied. Filesystem writes are scoped to a sandbox directory; network access is gated to `web_only` or `none`. Every denial is auditable.

**In this codebase**
- `src/policy/` — capability registry, sandbox executor, audit hooks
- Write boundary: `output/<run>/.workspace/` — outside is read-only
- Network policy: `web_only` (allowlisted endpoints) or `none`
- Audit events: `tool_denied`, `write_intent`, `network_intent`

<span class="ref">**Reference:** [Anthropic — Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)</span>

---
<!-- _class: pattern -->
<!-- TIMING: 1 min — Pattern 11: phase gates. Both decisions recorded. -->

## 11 · Human-in-the-Loop (HITL)

> *Phase-transition gates. Operator approves before irreversible actions.*

![w:920](patterns/11-human-in-the-loop.svg)

**The pattern** — Some actions are too consequential to trust to a fully autonomous agent: deploys, irreversible writes, large spends. HITL inserts an explicit pause at phase boundaries; the operator reviews artifacts, plan diffs, and cost estimates, then approves or aborts. Both decisions are recorded so the run remains fully auditable.

**In this codebase**
- `src/policy/hitl.py` — phase-transition gate
- Configurable per-phase: `hitl.gates = [research_to_synthesis, plan_approve, ...]`
- Audit events: `hitl_approved`, `hitl_aborted` — both with operator identity

<span class="ref">**Reference:** [LangGraph — Human-in-the-Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)</span>

---
<!-- _class: tight -->
<!-- TIMING: 3 min — composition. The demo run is a tuple over the layers. -->

## How they compose — the strategy lattice

The 11 patterns are not orthogonal — they layer:

| Layer | Patterns | Concern |
|---|---|---|
| **Engine** | Evaluator-Optimizer · LLM-as-Judge · Reflection | What makes a single iteration meaningful |
| **Topology** | Orchestrator · Role Topology · Routing · Parallel · Serial | How backends are wired and dispatched |
| **Guardrails** | Adversarial Critique · Sandbox · HITL | What prevents the agent from doing the wrong thing |

> **A configured strategy is a tuple over the layers.** The demo run = `Adversarial Critique` (guardrail) over `Serial Chaining` (topology) using `Evaluator-Optimizer + LLM-as-Judge` (engine), with `Sandbox` always on.

> Patterns are **mix-and-match**, not a menu of mutually exclusive options.

---
<!-- _class: divider -->
<!-- TIMING: transition, 10 sec -->

## Demo

### LocalStack alternatives — a real research question

*"LocalStack went fully paid. Should our team pay Pro or migrate to an open-source alternative?"*

---
<!-- TIMING: 2 min — show config in terminal. Key things to point out:
  - strategy: adversarial
  - three backends: claude-cli (primary), copilot-cli (researcher), codex-cli (adversary+judge)
  - 8 dimensions, max 10 iterations
  - allowed_tools: real web tools, not mocked
-->

<!-- _class: tighter -->

## The config — three backends, adversarial strategy

```yaml
# configs/research/localstack_alternatives_copilot_codex.yaml
research:
  topic: >
    Compare alternatives to LocalStack for local AWS service emulation.
    LocalStack is moving to a fully paid model. Evaluate MiniStack, Floci,
    and other viable open-source alternatives.
  goal: >
    A decision-ready comparison for a team evaluating LocalStack Pro vs
    open-source migration. Include migration effort, service coverage gaps,
    and a clear recommendation.
  execution:
    strategy: adversarial
    backends:
      primary:   primary_reasoner    # claude-cli (Claude Code)
      research:  [research_coder]    # copilot-cli (GitHub Copilot)
      judge:     adversary_reasoner  # codex-cli   (GPT-5.4) ← critic + judge
      utility:   adversary_reasoner
    max_iterations: 10
    allowed_tools: "WebSearch,WebFetch,Read,Bash,Glob,Grep"
```

Three different model families. Critic and judge are **deliberately different** from the researcher.

---
<!-- TIMING: 1 min — dry-run slide, then 2 min demo terminal -->

## Dry-run first — validate without spending tokens

```bash
# Validate config wiring, provider health, and tool capabilities — no backend calls
uv run python -m src.cli research \
  --config configs/research/localstack_alternatives_copilot_codex.yaml \
  --dry-run
```

Output confirms:
- All backend adapters resolve and are reachable
- Strategy is valid for the declared role topology
- Tool capability registry is satisfied
- Sandbox policy is coherent

Then run for real (this is the staged playback):

```bash
uv run python -m src.cli research \
  --config configs/research/localstack_alternatives_copilot_codex.yaml
```

<!-- PRESENTER: switch to terminal, show the staged run playing back. Point to the iteration log lines — hypothesis, score, KEEP/DISCARD decisions showing in real time. -->

---
<!-- _class: divider -->
<!-- TIMING: transition, 10 sec -->

## Adversarial critique in action

### What the critic actually said — from the real run

---
<!-- TIMING: 3 min — this is the most important slide. Show the critique finding a real error, then show it was fixed. -->

## The critic finds real errors

**Iteration 001** — Researcher (Copilot) delivers AWS service coverage findings. Score: **62.0**

The judge backend (GPT-5.4) reviews and raises:

> *"MiniStack section appears materially stale — API Gateway v1, Cognito, and KMS coverage are asserted without current primary source evidence."*

> *"Moto capabilities are mischaracterized — Lambda execution mode and IAM enforcement nuance are factually wrong."*

> *"Many fine-grained feature claims are overconfident relative to the cited evidence."*

**These are not style comments. They are factual challenges** — a different model, different training data, catching different errors.

The loop forces the next iteration to resolve these gaps or be discarded.

---
<!-- TIMING: 2 min — show the score table, draw attention to the dip in iter 007 (a harder dimension) and the jump to 76.3 in 009. -->

<!-- _class: tight -->

## Score progression — convergence is measurable

Each bar is one iteration. Score = heuristic (40%) + LLM judge (60%).

| Iteration | Dimension | Score | Decision |
|---|---|---|---|
| 001 | AWS service coverage | **62.0** | KEEP |
| 002 | Community activity & bus factor | 63.0 | KEEP |
| 003 | Migration effort | 63.5 | KEEP |
| 004 | CI/CD integration | 63.5 | KEEP |
| 005 | IaC toolchain (Terraform/CDK/SAM) | **69.5** | KEEP |
| 006 | CloudFormation source verification | 68.0 | KEEP |
| 007 | Migration effort by team profile | 63.5 | KEEP *(harder dimension)* |
| 008 | API behavioral fidelity | 66.0 | KEEP |
| **009** | Migration effort (final) | **76.3** | KEEP |

> Iter 007 dipped because the critic flagged under-validated migration estimates.
> The loop forced a harder verification pass. Iter 009 resolved it — **+12.8 points** on the final dimension.

---
<!-- TIMING: 1 min — transition to showing the outputs -->

## From one corpus — three artifacts

The research loop runs **once**. The output style is a rendering decision, not a research decision.

```yaml
reporting:
  output_style: technical_doc   # default | paper | technical_doc | executive_brief | decision_memo
```

Re-render any past run without re-running research:

```bash
uv run python -m src.cli research \
  --config configs/research/localstack_alternatives_copilot_codex_paper.yaml \
  --synthesize   # skips research loop, only re-renders
```

**Same data. Same citations. Different artifact.**

---
<!-- TIMING: 1.5 min — show raw report in browser -->

## Output: `default` — for internal exploration

![bg right:52% fit](localstack-alternatives/images/raw.png)

Quick narrative synthesis, sectioned by dimension, embedded comparison tables.

**Use when:**
- Exploring a topic
- Sharing internal findings
- Fast iteration before committing to a format

**Closest analog:** a thorough Notion research page

---
<!-- TIMING: 1.5 min — show paper report in browser -->

## Output: `paper` — for stakeholders and external review

![bg right:52% fit](localstack-alternatives/images/paper.png)

Abstract, methodology section, evidence-backed claims, deterministic `## References` built from `citations.json`.

**Use when:**
- Writing for external review
- Stakeholder reports where evidence provenance matters
- Anything that will be cited downstream

**Closest analog:** a literature review or RFC with bibliography

---
<!-- TIMING: 1.5 min — show technical report in browser. This is the money slide for engineering audiences. -->

## Output: `technical_doc` — for engineering decisions

![bg right:52% fit](localstack-alternatives/images/technical.png)

Comparison tables, decision matrix, recommendation upfront, structured pros/cons per alternative.

**Use when:**
- Architecture Decision Records (ADRs)
- Vendor / tool evaluation
- Decision memos for engineering teams

**Closest analog:** an RFC or ADR with a verdict

---
<!-- TIMING: 1.5 min — show the output directory in terminal. Point to rerun.sh. -->

<!-- _class: tight -->

## Every run is fully replayable

```
output/localstack_alternatives_copilot_codex/
├── run.log                  ← human-readable operational log
├── audit_trail.jsonl        ← append-only structured trail: steps, tool calls, denials, policy events
├── effective_config.json    ← full normalized config snapshot at run time
├── tool_trace.json          ← per-tool args + truncated outputs
├── prompt_snapshot.json     ← exact prompts sent at run start
├── rerun.sh                 ← runnable exact-replay script
├── iterations/
│   ├── iter_001.md          ← hypothesis + findings + critique + score
│   └── iter_009.md
└── report.html              ← rendered output
```

`rerun.sh` is not documentation — it's an executable that reconstructs the exact run.
No "it worked on my machine."

---
<!-- TIMING: 1 min — audit trail terminal: cat ... | python3 -m json.tool | head -40 -->

<!-- _class: tight -->

## Trust + certainty — every claim is classified

Every entry in `citations.json` and `claims.json` carries a `trust_class`:

| Class | Meaning |
|---|---|
| `untrusted_web_content` | URL citation from live web search — treat as external, unverified |
| `user_provided_source_material` | Operator-provided input files — trusted by the operator |
| `inferred_claim` | LLM-synthesised without a direct citation — explicitly flagged |

Plus PRISMA-style evidence logs:
- `search_log.json` — what was searched, when, from which backend
- `screening_log.json` — what was included or excluded, and why
- `certainty_tables.json` — first-pass certainty score per claim

> Readers know **exactly how strong each conclusion is** before acting on it.

---
<!-- TIMING: 30 sec — cost. Keep it short. Numbers from the real run. -->

<!-- _class: tight -->

## This run

Real execution data from the `localstack_alternatives_copilot_codex` run:

| Metric | Value |
|---|---|
| Backends | `claude-cli` (Claude Sonnet) · `copilot-cli` (Claude Sonnet 4.6) · `codex-cli` (GPT-5.4) |
| Strategy | `adversarial` — researcher + critic + arbitrator |
| Dimensions covered | **8 of 8** |
| Iterations | **9** (+ compression at iter 4) |
| Best score reached | **76.3 / 100** |
| Output formats generated | 3 (`default`, `paper`, `technical_doc`) |
| Execution cost | **$0.00** — all CLI adapters, flat-rate subscriptions |

> CLI adapters reuse existing Claude Pro / Copilot / Codex subscriptions — **flat cost, not per-token**.
> API adapters (for CI/unattended runs) bill per-token. Choose based on context.

---
<!-- TIMING: 1 min — takeaways as conclusions -->

## What you just saw

1. Two different model families **argued about LocalStack alternatives** for 9 iterations
2. The critic (GPT-5.4) caught real factual errors in the researcher's (Copilot) output
3. The loop forced resolution — the final score improved **+14.3 points** from iteration 1 to 9
4. Three publication-ready artifacts were produced from **one research corpus**
5. Every claim carries a `trust_class` — the system is honest about what it doesn't know
6. The full run is **exactly reproducible** via `rerun.sh`

> **The adversarial loop isn't about being clever. It's about the same engineering principle
> as code review: a second set of eyes with different priors catches different bugs.**

---
<!-- _class: tighter -->
<!-- _paginate: false -->

## Try it

```bash
uv sync

CONFIG=configs/research/localstack_alternatives_copilot_codex.yaml

# Validate without spending tokens
uv run python -m src.cli research --config "$CONFIG" --dry-run

# Run for real
uv run python -m src.cli research --config "$CONFIG"
```

Copy a template for your own topic: `configs/research/_template.yaml`

Reference: [`docs/research.md`](../research.md) · [`docs/design/agentic-design-patterns.md`](../design/agentic-design-patterns.md) · [`AGENTS.md`](../../AGENTS.md)

<!--
Render this deck:

  # HTML (best for screen recording)
  npx @marp-team/marp-cli --allow-local-files docs/showcase/demo_merged.md --html -o docs/showcase/demo_merged.html

  # PowerPoint
  npx @marp-team/marp-cli --allow-local-files docs/showcase/demo_merged.md -o docs/showcase/demo_merged.pptx

  # PDF
  npx @marp-team/marp-cli --allow-local-files docs/showcase/demo_merged.md --pdf -o docs/showcase/demo_merged.pdf
-->
