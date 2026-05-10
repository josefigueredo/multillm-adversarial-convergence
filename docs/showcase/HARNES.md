# Harness Engineering Framing

This note captures the presentation framing for introducing harness engineering
before the agentic design patterns section.

## Core Claim

A raw LLM is not an agent. It is a reasoning engine inside a control system.

The harness is the orchestration and infrastructure layer around the model. It
decides what the model sees, what tools it may use, how state persists, how
failures are handled, and when the loop stops.

This is a stronger opening than jumping directly into agentic patterns because
it gives the audience the missing abstraction: the patterns are not isolated
tricks; they are harness design patterns.

## OS Analogy

| OS analogy | Agent system |
| --- | --- |
| CPU | LLM |
| RAM | Context window |
| Disk | Files, vector databases, durable artifacts |
| Device drivers | Tool adapters, MCP servers, APIs |
| Kernel / operating system | Harness |
| Applications | Task-specific agents and workflows |

The useful point is not that the analogy is perfect. The useful point is that
model capability alone is not enough. The surrounding control system determines
what work the model can actually perform.

## Harness Responsibilities

- Context construction: decide what instructions, evidence, memory, and current
  state enter each model call.
- Tool mediation: expose tools through stable interfaces and enforce permission
  boundaries before side effects happen.
- State persistence: write durable artifacts that survive context truncation,
  restarts, retries, and delegation.
- Contracts: define required inputs, required outputs, validation gates, retry
  rules, and stop conditions.
- Verification: score, test, judge, cite-check, or otherwise evaluate candidate
  outputs.
- Recovery: retry, repair, rollback partial work, resume from completed state,
  and classify failure modes.
- Coordination: route work across roles, subagents, backends, and parallel or
  serial execution plans.
- Observability: record audit trails, tool traces, cost, scores, decisions, and
  provenance.

## Three-Layer Stack

```text
Natural-Language Agent Harness
roles · stages · task contracts · failure modes · strategy

Runtime Charter
state semantics · contract binding · budgets · child-agent lifecycle · policy

Backend Layer
models · tools · shell/browser · filesystem · sandbox · adapters
```

### Backend Layer

Components: model backends, terminal/browser access, filesystem access, tool
adapters, MCP servers, child-agent surfaces, deterministic scripts.

Duty: provide actual capabilities. This is where the system can read, write,
execute, search, browse, call APIs, or delegate.

### Runtime Charter Layer

Components: contract semantics, state rules, orchestration semantics, budgets,
permissions, child-agent lifecycle, retry and resume rules.

Duty: define the universal execution physics shared across harnesses. This is
the part that says what it means for a contract to bind, where state lives, how
delegation is supervised, and what policy gates apply.

### Natural-Language Agent Harness Layer

Components: roles, stages, task-specific contracts, adapters, state conventions,
and failure taxonomy.

Duty: encode the task-family strategy and behavior in an inspectable,
changeable artifact. This lets a developer compare, ablate, or replace harness
logic while keeping the runtime constant.

## Mapping To This Project

This project is best framed as a research harness:

> An orchestration system that turns multiple raw LLM backends into an
> auditable, resumable, adversarial research agent.

The current agentic patterns are implementation choices inside that harness:

- Evaluator-Optimizer: outer control loop.
- LLM-as-Judge: scoring contract.
- Reflection / Self-Compression: state and context management.
- Orchestrator / Subagents: lifecycle ownership and delegation.
- Multi-Agent Role Topology: role-to-backend mapping.
- Routing / Specialist Dispatch: task-aware backend selection.
- Parallelization / Ensemble: fan-out and merge.
- Prompt Chaining / Serial: staged execution.
- Adversarial Critique: verification strategy.
- Tool Use + Sandboxed Execution: runtime policy and action boundary.
- Human-in-the-Loop: approval gates at phase transitions.

## Suggested Deck Insertion

Add a short "Harness Engineering" section before "Agentic Design Patterns".

### Slide: Raw LLM vs Agent

Headline:

> A raw LLM is not an agent.

Body:

> It predicts text and stops. A harness gives it tools, memory, contracts,
> verification, recovery, and a loop.

### Slide: The Harness Is The Operating Layer

Use the OS analogy table:

| OS analogy | Agent system |
| --- | --- |
| CPU | LLM |
| RAM | Context window |
| Disk | Durable artifacts |
| Device drivers | Tool adapters |
| OS | Harness |

### Slide: The Three-Layer Stack

Show:

```text
Harness Layer        task-specific roles · stages · failure modes
Runtime Charter      state · contracts · budgets · permissions
Backend Layer        models · tools · filesystem · sandbox
```

Then transition:

> Now the patterns have a home: they are reusable designs inside the harness.

## Sources

- Natural-Language Agent Harnesses, arXiv:2603.25723:
  https://arxiv.org/abs/2603.25723
- Meta-Harness: End-to-End Optimization of Model Harnesses, arXiv:2603.28052:
  https://arxiv.org/abs/2603.28052
- Amazon Bedrock AgentCore harness overview:
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html

