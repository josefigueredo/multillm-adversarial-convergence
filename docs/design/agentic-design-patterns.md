# Agentic Design Patterns in This Framework

A reference for senior engineers and solutions architects on the agentic design
patterns employed in this system. For each pattern: **what it is**, **why it
matters architecturally**, **how it is implemented here**, and **where to go
deeper**.

---

## Table of Contents

1. [Evaluator-Optimizer (Iterative Refinement Loop)](#1-evaluator-optimizer-iterative-refinement-loop)
2. [Orchestrator / Subagents](#2-orchestrator--subagents)
3. [Parallelization (Ensemble Fan-out)](#3-parallelization-ensemble-fan-out)
4. [Prompt Chaining (Serial Pipeline)](#4-prompt-chaining-serial-pipeline)
5. [Routing / Specialist Dispatch](#5-routing--specialist-dispatch)
6. [Adversarial Critique (Multi-Agent Debate)](#6-adversarial-critique-multi-agent-debate)
7. [LLM-as-Judge](#7-llm-as-judge)
8. [Reflection / Self-Compression](#8-reflection--self-compression)
9. [Tool Use with Sandboxed Execution](#9-tool-use-with-sandboxed-execution)
10. [Multi-Agent Collaboration (Role Topology)](#10-multi-agent-collaboration-role-topology)
11. [Human-in-the-Loop (HITL)](#11-human-in-the-loop-hitl)

---

## 1. Evaluator-Optimizer (Iterative Refinement Loop)

### What it is

A closed feedback loop in which one agent (the *optimizer*) proposes a
candidate output and a second agent (the *evaluator*) scores it. The loop
continues — discarding or accepting each candidate — until a convergence
criterion is met. Inspired by Karpathy's
[autoresearch](https://github.com/karpathy/autoresearch): the same
`propose → execute → score → keep/discard → compress` shape, but applied to
knowledge synthesis instead of gradient descent.

### Why it matters architecturally

Single-pass generation is non-deterministic and unverifiable. Iterative
evaluation introduces a signal that can gate quality: only candidates that
clear a scoring threshold accumulate. This is the architectural equivalent of
CI/CD for knowledge — you don't ship until the build is green.

The pattern also decouples *generation* from *evaluation*, making each
independently replaceable, testable, and auditable.

### How it is implemented here

`src/research_loop.py` owns the cycle: hypothesis generation → backend call →
`heuristic_score` + `quality_score_from_judge` → `combine_scores` →
`IterationDecision` (KEEP / DISCARD / EXHAUST_DIMENSION). The loop terminates
on `max_iterations`, `target_dimensions_total`, or a stop signal.

`src/orchestrator.py` wires the loop to the lifecycle: artifact writing,
cost tracking, corpus compression, and final synthesis all happen outside the
tight loop.

### Reference

→ [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
*(Evaluator-Optimizer workflow)*

---

## 2. Orchestrator / Subagents

### What it is

A **single coordinator** (the orchestrator) owns the high-level lifecycle:
goal decomposition, prompt rendering, cost tracking, artifact writing, and
stopping conditions. **Narrow-contract subagents** (backends) execute a single
task and return a result. They have no awareness of lifecycle state.

This is the agentic equivalent of a service mesh: the orchestrator is the
control plane; backends are the data plane.

### Why it matters architecturally

When agents are allowed to self-direct, costs and execution paths become
unpredictable. Centralizing lifecycle control in one coordinator gives you:

- **Observability** — every call is instrumented at one boundary.
- **Cost governance** — token budgets, timeout enforcement, retry policies
  are applied uniformly.
- **Replaceability** — swap any backend without touching lifecycle logic.
- **Failure isolation** — a backend crash is caught by the orchestrator; it
  does not corrupt shared state.

### How it is implemented here

`src/orchestrator.py` is the orchestrator. It instantiates backends via
`src/backends/`, renders prompts via `src/prompts.py`, invokes strategies
(which route calls to backends), and owns the full artifact pipeline
(`src/artifacts.py`, `src/audit_trail.py`).

Backends in `src/backends/` implement a narrow `Backend.invoke()` contract and
have no knowledge of loop state or output paths.

### Reference

→ [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
*(Orchestrator-Workers)*

---

## 3. Parallelization (Ensemble Fan-out)

### What it is

All available research backends are dispatched **simultaneously** on the same
task. Results are collected as they complete, then either merged (ensemble) or
competed (parallel — best score wins). This is a fan-out / fan-in pattern: one
input, N concurrent executions, one aggregated output.

### Why it matters architecturally

LLMs are non-deterministic and model-biased. Different models trained on
different corpora will surface different evidence, use different framing, and
miss different gaps. Running them in parallel:

- **Increases coverage** — complementary blind spots cancel out.
- **Reduces latency vs. serial** — wall-clock time is bounded by the slowest
  backend, not the sum.
- **Provides natural redundancy** — if one backend is throttled or fails, the
  others still produce output.

The `parallel` strategy then applies a judge to select the best candidate,
turning diversity of outputs into a quality signal.

### How it is implemented here

`EnsembleStrategy` and `ParallelStrategy` in `src/strategy.py` use
`concurrent.futures.ThreadPoolExecutor` to dispatch calls. `ResearchCandidate`
objects are collected via `as_completed()`. The judge backend then scores
candidates and the highest-scoring result is promoted to `ResearchResult`.

### Reference

→ [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
*(Parallelization)*

---

## 4. Prompt Chaining (Serial Pipeline)

### What it is

Backends execute **sequentially**. Each backend receives the output of its
predecessor as additional context, progressively refining the artifact.
This is the pipeline pattern applied to LLM calls: stage N+1 builds on
stage N.

### Why it matters architecturally

Chaining is suited to tasks where quality improves through *progressive
specialization*: a first pass establishes breadth; a second pass adds depth;
a third refines language or structure. Each stage can be tuned for its role
(e.g., a research-oriented model for retrieval, a reasoning-heavy model for
synthesis).

The tradeoff vs. parallelization: higher latency, lower cost, tighter
sequential dependency — a cascade failure in stage N propagates.

### How it is implemented here

`SerialStrategy` in `src/strategy.py` iterates through `research_backends`,
passing each result as context to the next call. The `refine` and `plan` modes
also embody chaining at the mode level: `src/implement/` orchestrates a
draft → critique → rewrite cycle across backends.

### Reference

→ [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
*(Prompt Chaining)*

---

## 5. Routing / Specialist Dispatch

### What it is

Each research dimension (sub-topic) is routed to the backend best suited for
it, based on declared persona or capability. The router assigns work
to specialists rather than broadcasting to all.

This is analogous to topic-based routing in a message broker: producers emit
tasks tagged by type; consumers are subscribed by specialty.

### Why it matters architecturally

Not all models are equally good at all tasks. A code-execution-capable model
is better for implementation analysis; a retrieval-heavy model is better for
literature synthesis. Routing lets you compose a heterogeneous backend pool
into a single coherent research agent that applies the best tool to each
sub-problem.

It also constrains cost: you don't pay for a premium model on every dimension
when a cheaper specialist suffices.

### How it is implemented here

`SpecialistStrategy` in `src/strategy.py` maps dimensions to backends based on
the `specialist_roles` declared in `BackendsConfig`. The orchestrator's
dimension scheduling surfaces the next dimension to the strategy, which then
dispatches to the assigned backend.

### Reference

→ [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
*(Routing)*

---

## 6. Adversarial Critique (Multi-Agent Debate)

### What it is

Three agents take distinct, adversarial roles in a single iteration:

1. **Researcher** — generates findings on the current dimension.
2. **Critic** — independently reviews those findings for errors, gaps,
   unsupported claims, and logical inconsistencies.
3. **Arbitrator** — weighs the findings and critique, produces a refined
   synthesis.

By design, these three roles are filled by *different* backends. The critic
has no loyalty to the researcher's output.

### Why it matters architecturally

A model reviewing its own output is a weak signal — it has the same priors and
blind spots as the generator. A different model trained on a different corpus
and with different RLHF characteristics will catch different classes of errors.

This maps directly to the **adversarial review** practice in security (red
team / blue team), architecture reviews (devil's advocate), and academic peer
review. The convergence guarantee is probabilistic, not formal, but empirically
the adversarial loop raises the floor on output quality more reliably than
self-critique.

### How it is implemented here

`AdversarialStrategy` in `src/strategy.py` issues three sequential invocations
per iteration: research call on `primary`, critique call on `judge` (with the
findings as input), arbitration call on `utility` (with both findings and
critique). The `CritiqueResult` dataclass carries the critique text and its
cost, which is tracked separately for cost attribution.

### Reference

→ [arXiv 2305.19118 — Encouraging Divergent Thinking in LLMs through Multi-Agent Debate](https://arxiv.org/abs/2305.19118)

---

## 7. LLM-as-Judge

### What it is

A designated backend acts as an **automated evaluator**: it receives a
candidate output and a structured scoring rubric, and returns a numeric score
with a justification. The judge backend is distinct from the backend that
produced the candidate — no self-grading.

The score is a *probabilistic quality signal*, not ground truth. It is combined
with a deterministic heuristic score to reduce susceptibility to judge
manipulation (a model that learns to "write for the judge").

### Why it matters architecturally

Human evaluation does not scale to hundreds of iterations across multiple
dimensions. LLM-as-Judge is the enabling mechanism that makes automated
iterative refinement tractable: it provides a per-iteration quality gate
without human involvement.

The architectural key is **judge independence**: the judge backend must be
isolated from the generator's optimization pressure. Using a different model
family, or at minimum a different system prompt context, is essential.

Caveats: judge scores can reflect model biases (verbosity preference, style
matching). Hybrid scoring — combining a rule-based heuristic with the LLM
judge — is the standard mitigation.

### How it is implemented here

`src/scorer.py` implements `heuristic_score` (deterministic, 40% weight) and
`quality_score_from_judge` (LLM call, 60% weight). `combine_scores` produces
the `IterationScore`. The judge backend is configured via
`backends.judge` in the YAML config, defaulting to `primary` if unset.

### Reference

→ [agentic-design.ai — LLM as Judge](https://agentic-design.ai/patterns/reflection/llm-as-judge)
→ [arXiv 2410.10934 — Agent-as-a-Judge](https://arxiv.org/abs/2410.10934)

---

## 8. Reflection / Self-Compression

### What it is

Every N iterations, the agent invokes a **compression backend** that reads
the accumulated knowledge corpus and produces a distilled, denser
representation. The original corpus is replaced by the distillate. The agent
continues the loop with a tighter, higher-signal knowledge base.

This is the agentic analogue of **gradient accumulation with periodic
checkpointing**: you don't carry raw gradients forever; you periodically
consolidate.

### Why it matters architecturally

LLM context windows are finite and expensive. Naively accumulating raw
iteration findings degrades synthesis quality (signal-to-noise drops as the
corpus grows) and increases per-call cost. Periodic compression:

- **Preserves context budget** for new research, not old verbosity.
- **Forces prioritization** — the compression model must decide what matters,
  which is itself a quality filter.
- **Reduces per-call token cost** for all subsequent iterations.

The compression step also acts as a form of reflection: the agent re-reads
its own prior work and produces a more coherent world model before continuing.

### How it is implemented here

The compression interval is set via `research.compress_every_n` in config.
`src/run_state.py` tracks iteration count and triggers corpus distillation by
calling the `utility` backend with a compression prompt from `prompts/`.
The distilled corpus is written back to the in-memory knowledge base used
by hypothesis generation in subsequent iterations.

### Reference

→ [Andrew Ng — Agentic AI Design Patterns (Reflection)](https://www.deeplearning.ai/the-batch/how-agents-can-improve-llm-performance/)

---

## 9. Tool Use with Sandboxed Execution

### What it is

Backends are granted a **capability set** — a declared list of tools they may
invoke (web search, file reads, shell commands, etc.). A **capability registry**
classifies every tool by risk tier. A **sandbox executor** intercepts every
tool dispatch at runtime and enforces:

- **Write-boundary policy** — filesystem writes restricted to
  `output/<run>/.workspace/`.
- **Network policy** — web-only, internal-only, or none.
- **Capability whitelist** — unclassified or disallowed tools are denied with
  a structured `reason_code`.

All denials, write intents, and policy events are appended to
`audit_trail.jsonl`.

### Why it matters architecturally

Agentic systems that can execute tools are no longer stateless; they can cause
side effects in the host environment. Without a policy layer, a
sufficiently autonomous agent can exfiltrate data, overwrite arbitrary files,
or make outbound network calls to attacker-controlled infrastructure — even
unintentionally.

The sandbox is the **defense-in-depth boundary** between the agent's execution
surface and the host. It enforces least-privilege at the capability level, not
just at the process level. This is the same architectural principle as IAM
roles with minimal permissions or a Kubernetes PodSecurityPolicy.

### How it is implemented here

`src/policy/tool_capabilities.py` defines the capability registry.
`src/policy/sandbox_executor.py` wraps tool dispatch and enforces policy.
`src/policy/security_runtime.py` applies the `security:` config section to
build the active policy at run startup.
`src/policy/policy_denial.py` emits structured denial records.

Config surface:

```yaml
security:
  tool_execution_mode: sandboxed     # direct | sandboxed
  allow_host_bash: false
  sandbox:
    filesystem_access: workspace_only
    network_access: web_only
```

### Reference

→ [Anthropic — Writing Effective Tools for AI Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

---

## 10. Multi-Agent Collaboration (Role Topology)

### What it is

The system defines a **named role topology**: `primary`, `judge`, `utility`,
and `research` (a pool). Each role has a specific function in the loop and can
be filled by a different backend. This is not just multi-model; it is
**multi-role** — the same model can fill multiple roles, but roles are
architecturally distinct.

This is closer to an **actor model** than a flat ensemble: agents have identity
(role), a mailbox (prompt), and produce typed outputs (`ResearchResult`,
`CritiqueResult`, `IterationScore`).

### Why it matters architecturally

Role separation enables specialization without tight coupling. You can:

- Assign a fast/cheap model to the `utility` role (compression, formatting)
  and a slow/expensive model to `primary` (deep research).
- Swap the `judge` role for a domain-specific model without touching strategy
  logic.
- Route cost attribution per role for granular billing analysis.

It also provides a clean extension point: adding a new role (e.g., a
`fact_checker` backend) requires only a new role declaration in config and a
new strategy hook — no changes to orchestrator lifecycle.

### Reference

→ [arXiv 2405.10467 — Agent Design Pattern Catalogue](https://arxiv.org/abs/2405.10467)

---

## 11. Human-in-the-Loop (HITL)

### What it is

Designated checkpoints in the execution lifecycle where the agent **pauses and
surfaces a decision** to a human operator. The human can approve, reject, or
modify the agent's proposed next step before execution continues. HITL is
opt-in and configurable per-run.

### Why it matters architecturally

Fully autonomous agents operating in agentic loops accumulate compounding
risk: an early wrong decision propagates through every subsequent iteration.
HITL gates are **circuit breakers** for high-stakes or irreversible actions.

From an enterprise architecture perspective, HITL is also a **compliance
boundary**: regulated industries require human sign-off before an automated
system takes actions that affect external systems, data, or commitments. HITL
makes that boundary explicit and auditable.

The tradeoff: HITL breaks unattended execution. In practice, it is used
selectively — at phase transitions (e.g., before final synthesis export) or
before tool calls that cross the workspace boundary.

### How it is implemented here

`src/policy/hitl.py` implements the checkpoint protocol. HITL gates are
declared via `security.hitl_checkpoints` in config. When a checkpoint is
reached, execution blocks on stdin until the operator responds. The decision
(approve/reject/modify) is recorded in `audit_trail.jsonl`.

### Reference

→ [LangGraph — Human-in-the-Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/)

---

## Pattern Interaction Map

```
                    ┌──────────────────────────────────────────┐
                    │            ORCHESTRATOR (#2)             │
                    │  (lifecycle, cost, artifacts, stopping)  │
                    └───────────────┬──────────────────────────┘
                                    │ dispatches
                    ┌───────────────▼──────────────────────────┐
                    │         STRATEGY LAYER                   │
                    │                                          │
                    │  #3 Parallel  #4 Serial  #5 Specialist   │
                    │  #6 Adversarial                          │
                    └──────────┬──────────────────┬────────────┘
                               │                  │
              ┌────────────────▼──┐       ┌───────▼──────────────┐
              │  RESEARCH AGENTS  │       │  JUDGE AGENT (#7)    │
              │  (primary / pool) │       │  (scores candidates) │
              └────────────────┬──┘       └───────┬──────────────┘
                               │                  │
                    ┌──────────▼──────────────────▼────────────┐
                    │       EVALUATOR-OPTIMIZER LOOP (#1)       │
                    │  propose → score → keep/discard          │
                    └──────────────────┬───────────────────────┘
                                       │ every N iterations
                    ┌──────────────────▼───────────────────────┐
                    │       REFLECTION / COMPRESSION (#8)      │
                    └──────────────────────────────────────────┘
                                    │
                    ┌───────────────▼──────────────────────────┐
                    │  TOOL USE + SANDBOX (#9)                 │
                    │  HITL GATES (#11)                        │
                    │  ROLE TOPOLOGY (#10)                     │
                    └──────────────────────────────────────────┘
```

---

## Further Reading

| Topic | Resource |
|---|---|
| Practical agent architectures | [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) |
| Multi-agent debate | [arXiv 2305.19118](https://arxiv.org/abs/2305.19118) |
| LLM evaluation | [arXiv 2410.10934 — Agent-as-a-Judge](https://arxiv.org/abs/2410.10934) |
| Reflection pattern | [Andrew Ng — Agentic AI Design Patterns](https://www.deeplearning.ai/the-batch/how-agents-can-improve-llm-performance/) |
| Pattern catalogue (18 patterns) | [arXiv 2405.10467](https://arxiv.org/abs/2405.10467) |
| Tool security for agents | [Anthropic — Writing Effective Tools](https://www.anthropic.com/engineering/writing-tools-for-agents) |
| Human-in-the-loop | [LangGraph — HITL](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) |
| LLM-as-Judge pattern | [agentic-design.ai](https://agentic-design.ai/patterns/reflection/llm-as-judge) |
