# Iris PoC Curriculum — Lab Syllabus Design

**Date:** 2026-04-18
**Author:** Jose Figueredo
**Status:** Approved — pending implementation plan

---

## Purpose

This document defines the structure, content, and sequencing of the Iris Proof-of-Concept curriculum. The curriculum validates every architectural decision in the Iris platform through hands-on, agent-executed experiments before source code implementation begins.

Each PoC is a formal lab unit with academic rigor: stated learning objectives, theoretical background, ADR traceability, acceptance criteria, and reflection prompts. The agent executes; the engineer directs and validates.

---

## How to Use This Curriculum

1. **Sequential execution is mandatory.** PoC N is locked until all acceptance criteria of PoC N-1 are satisfied. No skipping.
2. **Agent-driven execution.** Pass the Experiment Specification section verbatim to an agent. The agent builds; you validate against Acceptance Criteria.
3. **Gate validation is binary.** Every AC must be satisfied before proceeding. Partial completion does not unlock the next lab.
4. **Reflection is not optional.** Reflection prompts exist to internalize understanding, not to document. Answer them mentally or in a scratchpad before moving on.
5. **Phase gates.** Completing Phase I unlocks Phase II. Completing Phase II unlocks Phase III. Phase III is the capstone.

---

## Phases

| Phase | PoCs | Theme |
|-------|------|-------|
| I — Infrastructure Foundations | 01–07 | Core runtime components |
| II — Security & Policy Plane | 08–12 | Zero-trust, policy-as-code, GitOps |
| III — Integration & Pipeline Spine | 13–15 | Convergence toward v1-alpha |

---

## Lab Unit Template

Each lab unit follows this exact structure:

1. **Learning Objectives** — numbered LO-1, LO-2... Observable competencies gained.
2. **Theoretical Background** — concepts, the WHY, references to papers or official docs.
3. **ADR Traceability** — which Iris ADR(s) this PoC validates and how.
4. **Prerequisites** — prior PoCs and tooling required.
5. **Experiment Specification** — what the agent builds. Precise enough to pass as an agent prompt.
6. **Acceptance Criteria** — numbered AC-1, AC-2... Binary observable conditions. No ambiguity.
7. **Reflection Prompts** — 3–5 questions to internalize understanding after validation.

---

## Phase I — Infrastructure Foundations

### PoC 01 — `k8s-local`

**Learning Objectives**
- LO-1: Bootstrap a `kind` cluster and verify control plane health.
- LO-2: Understand the relationship between Pods, Namespaces, Services, and ConfigMaps as Kubernetes primitive abstractions.
- LO-3: Establish `kubectl` as the primary observability instrument for cluster state.

**Theoretical Background**
Kubernetes implements a reconciliation loop: the control plane continuously compares desired state (manifests) with actual state (running resources) and drives toward convergence. This loop is the architectural foundation for the Iris Operator, which manages platform-level desired state through four CRDs (`IrisPlatform`, `IrisTenant`, `IrisPipeline`, `IrisExperiment`).

Namespaces are not merely organizational — they are the primary isolation boundary for network policies, RBAC, and resource quotas. In Iris, one namespace per tenant is the enforcement unit.

References: [Kubernetes architecture docs](https://kubernetes.io/docs/concepts/architecture/); Brendan Burns et al., "Borg, Omega, and Kubernetes" (ACM Queue, 2016).

**ADR Traceability**
Validates **ADR-007** (Kubernetes as cloud-agnostic runtime). Understanding primitives here is prerequisite to understanding why the Iris Operator (ADR-016, `controller-runtime`) is necessary and why cloud-managed Kubernetes (EKS/GKE/AKS) is an operational decision, not an architectural one.

**Prerequisites**
- Tooling: `kind`, `kubectl`, Docker Desktop or OrbStack.
- Prior PoCs: none.

**Experiment Specification**
Bootstrap a `kind` cluster named `iris-lab-01`. Create namespace `iris-lab`. Deploy a pod running `nginx:alpine` in that namespace. Expose it via a ClusterIP Service named `nginx-svc`. Create a ConfigMap named `iris-config` with key `TENANT_ID=bims`. Mount the ConfigMap as environment variables into the pod. Verify the pod reads the value. Write all commands and manifests to a `poc-01/README.md`. Tear down the cluster.

**Acceptance Criteria**
- AC-1: `kubectl get nodes` returns 1 node in `Ready` state.
- AC-2: Pod in namespace `iris-lab` reaches `Running` state.
- AC-3: `kubectl exec` into the pod confirms `TENANT_ID=bims` is present as an environment variable.
- AC-4: `poc-01/README.md` exists and documents all commands and manifests used.

**Reflection Prompts**
1. What does the reconciliation loop do when you delete the pod manually without a Deployment?
2. How does a Service know which pods to route traffic to — what mechanism does it use?
3. Why does Iris use one namespace per tenant instead of relying on labels alone?
4. How does the concept of desired state relate to the Iris Operator managing `IrisTenant` resources?

---

### PoC 02 — `k8s-nats`

**Learning Objectives**
- LO-1: Deploy NATS with JetStream enabled on Kubernetes.
- LO-2: Understand the difference between core NATS (at-most-once) and JetStream (at-least-once, durable).
- LO-3: Model the Iris subject hierarchy (`iris.<tier>.<tenant>.jobs`) as a tenant isolation primitive.
- LO-4: Observe consumer lag as an operational signal.

**Theoretical Background**
NATS JetStream adds persistence and acknowledgement semantics to NATS core. A *stream* is a named, ordered log bound to a subject filter. A *consumer* is a durable cursor into that log. Consumer lag (unacknowledged messages) is the primary signal for pipeline backpressure in Iris.

The subject hierarchy (`iris.standard.bims.jobs`, `iris.regulated.example-org.jobs`) enforces tenant isolation at the messaging layer without requiring separate brokers per tenant — a deliberate cost and operational tradeoff documented in ADR-010. Contrast with Kafka topic-per-tenant (higher ops cost) and Redis Pub/Sub (no durability).

References: [NATS JetStream docs](https://docs.nats.io/nats-concepts/jetstream); ADR-010.

**ADR Traceability**
Validates **ADR-010** (NATS JetStream over Kafka and Redis). The PoC demonstrates the subject-hierarchy isolation model that makes per-tenant namespacing viable without dedicated broker instances for standard tenants.

**Prerequisites**
- Prior PoCs: 01 completed and AC satisfied.
- Tooling: `helm`, `nats` CLI.

**Experiment Specification**
Deploy NATS with JetStream enabled via Helm into namespace `nats-system` on the `iris-lab-01` cluster. Create a stream named `IRIS_JOBS` bound to subject `iris.standard.*.jobs`. Create a durable push consumer named `worker`. Publish 5 messages to `iris.standard.bims.jobs` using the `nats` CLI. Consume and acknowledge all messages. Publish 3 more messages without consuming — observe and document consumer lag. Write findings to `poc-02/README.md`.

**Acceptance Criteria**
- AC-1: NATS pod in `nats-system` reaches `Running` state with JetStream enabled (`nats server info` confirms JetStream: enabled).
- AC-2: Stream `IRIS_JOBS` exists and is bound to subject filter `iris.standard.*.jobs`.
- AC-3: 5 published messages are consumed and acknowledged — consumer lag returns to 0.
- AC-4: After publishing 3 unconsumed messages, consumer lag shows 3 pending in `nats consumer info`.
- AC-5: `poc-02/README.md` documents stream config, consumer config, and lag observation.

**Reflection Prompts**
1. What happens to messages in JetStream if the consumer pod crashes mid-processing?
2. Why does the wildcard `*` in `iris.standard.*.jobs` matter for multi-tenancy? What's the risk if you use `>`?
3. How would you implement backpressure if a tenant's consumer falls 10,000 messages behind?
4. Why did ADR-010 choose NATS over Kafka for the standard tier?

---

### PoC 03 — `k8s-postgresql`

**Learning Objectives**
- LO-1: Deploy PostgreSQL on Kubernetes and connect from a Job pod.
- LO-2: Execute a schema migration as a versioned, reproducible artifact.
- LO-3: Understand PostgreSQL's role as both the Iris control plane database and the Temporal backend.

**Theoretical Background**
PostgreSQL is the operational backbone of Iris: control plane state (tenant config, pipeline registry, audit logs), Temporal workflow history, and evidence storage all reside in PostgreSQL. Schema migrations are not deployment scripts — they are versioned, ordered, idempotent artifacts that must be applied before application startup. `golang-migrate` enforces this through numbered migration files and a `schema_migrations` tracking table.

The `pgvector` extension enables vector similarity search directly in PostgreSQL — relevant context for understanding why Qdrant (PoC 05) is chosen for Resolution Memory at scale rather than pgvector: operational isolation of vector workloads from transactional workloads.

References: [golang-migrate docs](https://github.com/golang-migrate/migrate); PostgreSQL docs on schemas and roles.

**ADR Traceability**
Validates **ADR-011** (PostgreSQL as control plane database). Demonstrates the schema-per-tenant isolation model for standard tenants and establishes the migration discipline required before Temporal deployment (PoC 04).

**Prerequisites**
- Prior PoCs: 01, 02 completed and AC satisfied.
- Tooling: `psql`, `golang-migrate` CLI.

**Experiment Specification**
Deploy PostgreSQL 16 via Helm into namespace `iris-db`. Create two schemas: `iris_control` and `tenant_bims`. Using `golang-migrate`, write and apply two migration files: (1) create `tenants` table in `iris_control`; (2) create `evidence` table in `tenant_bims`. Verify migrations applied by connecting from a Kubernetes Job pod and querying `schema_migrations`. Roll back migration 2 and verify. Write findings to `poc-03/README.md`.

**Acceptance Criteria**
- AC-1: PostgreSQL pod in `iris-db` reaches `Running` state.
- AC-2: Both schemas `iris_control` and `tenant_bims` exist after migration.
- AC-3: `schema_migrations` table shows both migrations applied (version 1 and 2).
- AC-4: After rollback, only migration version 1 remains in `schema_migrations` and `tenant_bims.evidence` table does not exist.
- AC-5: `poc-03/README.md` documents migration files, apply command, and rollback command.

**Reflection Prompts**
1. Why is schema-per-tenant preferable to table-prefix-per-tenant for standard tier isolation?
2. What is the risk of running migrations inside application startup rather than a dedicated Job?
3. How does `pgvector` differ from Qdrant in terms of operational characteristics?
4. Why does Temporal require PostgreSQL rather than a simpler store like SQLite?

---

### PoC 04 — `k8s-temporal`

**Learning Objectives**
- LO-1: Deploy Temporal server and UI backed by PostgreSQL on Kubernetes.
- LO-2: Write and execute a hello-world workflow with one activity in Go.
- LO-3: Understand durable execution: workflow history, activity retry semantics, and worker polling.

**Theoretical Background**
Temporal implements durable execution: a workflow function's execution state is persisted as an event history in PostgreSQL. If a worker crashes mid-execution, the next worker replaying the history resumes exactly where execution left off — without the calling code handling retries, state persistence, or failure recovery.

This is architecturally critical for Iris: a pipeline run (ingest → normalize → cluster → rank → recommend) may take minutes. Individual activities (LiteLLM call, Qdrant upsert) can fail transiently. Temporal absorbs all of this complexity transparently. Contrast with cron jobs (no durability), message queues (no state), or Step Functions (AWS lock-in, ADR-001 reasoning).

References: [Temporal docs: core concepts](https://docs.temporal.io/concepts); ADR-001.

**ADR Traceability**
Validates **ADR-001** (Temporal self-hosted on EKS). The PoC demonstrates why self-hosted is non-negotiable for regulated tenants: Temporal Cloud does not offer dedicated namespace isolation at the compute layer required for regulated compliance.

**Prerequisites**
- Prior PoCs: 01–03 completed and AC satisfied.
- Tooling: Go 1.22+, `temporal` CLI.

**Experiment Specification**
Deploy Temporal server (single-node) and Temporal UI via Helm into namespace `temporal-system`, backed by the PostgreSQL instance from PoC 03. Write a Go worker with one workflow (`HelloWorkflow`) and one activity (`FormatGreeting`). The workflow calls the activity and returns a greeting string. Register the worker against the `iris-task-queue` task queue. Trigger a workflow execution via `temporal workflow start`. Observe the execution in Temporal UI. Introduce an artificial failure in the activity (panic on first attempt) and observe retry behavior in the UI. Write findings to `poc-04/README.md`.

**Acceptance Criteria**
- AC-1: Temporal server and UI pods reach `Running` state.
- AC-2: Worker connects to Temporal and registers on `iris-task-queue` (visible in UI under Workers).
- AC-3: `HelloWorkflow` completes successfully — result visible in Temporal UI.
- AC-4: After introducing the panic, Temporal retries the activity automatically and the workflow eventually completes — retry count visible in event history.
- AC-5: `poc-04/README.md` documents workflow code, activity code, and retry observation.

**Reflection Prompts**
1. What is the difference between a workflow and an activity in Temporal's execution model?
2. Why is it unsafe to make a network call directly inside a workflow function (not in an activity)?
3. How does Temporal's event history replay model guarantee exactly-once activity side effects?
4. How does the `iris-task-queue` map to the concept of a pipeline worker in Iris?

---

### PoC 05 — `k8s-qdrant`

**Learning Objectives**
- LO-1: Deploy Qdrant on Kubernetes and interact with it via the REST API.
- LO-2: Insert a batch of fake embeddings and execute a nearest-neighbor query.
- LO-3: Understand why Qdrant is chosen for Resolution Memory over pgvector.

**Theoretical Background**
Vector similarity search operates on high-dimensional numerical representations (embeddings) of text, code, or structured data. A nearest-neighbor query returns the K vectors most similar (by cosine similarity or dot product) to a query vector — enabling semantic retrieval rather than exact keyword matching.

Resolution Memory in Iris is a vector-indexed corpus of historical problem→resolution pairs. When Iris identifies a recurring pattern, it queries Qdrant for the K most semantically similar past incidents with confirmed resolutions. This grounds recommendations in historical precedent rather than pure inference.

Qdrant is chosen over pgvector (ADR-002) because vector workloads (large batch upserts, approximate nearest neighbor) are operationally distinct from transactional workloads. Running them in the same PostgreSQL instance introduces resource contention and complicates capacity planning.

References: [Qdrant docs](https://qdrant.tech/documentation/); Johnson et al., "Billion-scale similarity search with GPUs" (FAISS paper, 2017).

**ADR Traceability**
Validates **ADR-002** (Qdrant self-hosted). The PoC demonstrates the collection-per-tenant isolation model and validates that Qdrant is operationally manageable on Kubernetes before committing to it for Resolution Memory.

**Prerequisites**
- Prior PoCs: 01–04 completed and AC satisfied.
- Tooling: `curl` or a Python/Go Qdrant client.

**Experiment Specification**
Deploy Qdrant via Helm into namespace `qdrant-system`. Create a collection named `resolution-memory-bims` with 1536-dimensional vectors (OpenAI embedding dimensions) and cosine distance. Insert 20 fake embeddings (random vectors) each with a payload containing `incident_id`, `summary`, and `resolution` fields. Run a nearest-neighbor query with a random query vector (k=5). Inspect results in the Qdrant UI. Write findings to `poc-05/README.md`.

**Acceptance Criteria**
- AC-1: Qdrant pod in `qdrant-system` reaches `Running` state and UI is accessible.
- AC-2: Collection `resolution-memory-bims` exists with correct vector dimension (1536) and distance metric (Cosine).
- AC-3: 20 points are inserted and visible in the Qdrant UI.
- AC-4: Nearest-neighbor query returns exactly 5 results with payload fields intact.
- AC-5: `poc-05/README.md` documents collection config, insertion code, and query results.

**Reflection Prompts**
1. Why is cosine similarity preferred over Euclidean distance for text embeddings?
2. What is the operational risk of storing vectors and transactional data in the same PostgreSQL instance at scale?
3. How would you implement per-tenant isolation in Qdrant — collection-per-tenant vs. payload filter?
4. What happens to Resolution Memory quality if embeddings are generated by inconsistent models over time?

---

### PoC 06 — `k8s-litellm`

**Learning Objectives**
- LO-1: Deploy LiteLLM as the `ai-service` gateway on Kubernetes.
- LO-2: Route a completion call through the gateway to a real or stubbed provider.
- LO-3: Understand the provider failover chain and cost tagging as first-class operational concerns.

**Theoretical Background**
An AI gateway abstracts provider-specific APIs behind a single OpenAI-compatible interface, enabling provider failover, cost attribution, rate limiting, and audit logging without changes to calling services. LiteLLM proxies calls to Bedrock, Vertex AI, Azure OpenAI, and OpenAI using a unified routing model.

In Iris, every AI call (classification, clustering, recommendation generation) is routed through `ai-service` (LiteLLM). This ensures: (1) provider lock-in is eliminated at the call site; (2) cost is tagged per tenant and per pipeline run; (3) provider failures trigger automatic fallback without application-level handling. AWS Bedrock is primary because it operates within the Iris AWS account boundary, avoiding data egress.

References: [LiteLLM proxy docs](https://docs.litellm.ai/docs/proxy/quick_start); ADR-012.

**ADR Traceability**
Validates **ADR-012** (LiteLLM as AI gateway). Demonstrates provider-agnostic routing and confirms that the gateway is operationally manageable before it is integrated into the Temporal pipeline (PoC 14).

**Prerequisites**
- Prior PoCs: 01–05 completed and AC satisfied.
- Tooling: OpenAI API key OR LiteLLM mock mode enabled.

**Experiment Specification**
Deploy LiteLLM proxy via Helm into namespace `ai-service`. Configure it with one model entry: `gpt-3.5-turbo` routing to OpenAI (or to LiteLLM's built-in mock mode if no key is available). Add a fallback model entry. Enable spend tracking. Send a `/chat/completions` request from a curl command inside the cluster. Verify the response and check LiteLLM logs for the model used and cost recorded. Write findings to `poc-06/README.md`.

**Acceptance Criteria**
- AC-1: LiteLLM pod in `ai-service` namespace reaches `Running` state.
- AC-2: `/chat/completions` POST returns a valid completion response with HTTP 200.
- AC-3: LiteLLM logs show the model used and a non-zero cost entry (or mock cost in mock mode).
- AC-4: Disabling the primary model causes automatic fallback to the secondary model — verified in logs.
- AC-5: `poc-06/README.md` documents config, request, response, and fallback observation.

**Reflection Prompts**
1. Why is provider lock-in at the call site dangerous for a multi-year platform like Iris?
2. How does cost tagging per tenant enable chargeback in a multi-tenant SaaS?
3. What is the risk of routing all AI calls through a single gateway pod — how would you address it?
4. How does LiteLLM's mock mode change the testing strategy for the Temporal pipeline (PoC 14)?

---

### PoC 07 — `k8s-otel-grafana`

**Learning Objectives**
- LO-1: Deploy the full OTel + Grafana OSS observability stack on Kubernetes.
- LO-2: Instrument a minimal Go service with traces, metrics, and logs.
- LO-3: View correlated signals (trace + log + metric) in Grafana using a shared trace ID.

**Theoretical Background**
The three pillars of observability (traces, metrics, logs) are only useful when correlated. A trace tells you where time was spent; a log tells you what happened at a point in time; a metric tells you the aggregate state. Correlation requires a shared identifier — in Iris, `pipeline_run_id` serves this role.

OpenTelemetry is a vendor-neutral instrumentation standard. The OTel Collector receives, processes, and exports signals to backend stores. Grafana OSS provides the unified query surface: Tempo for traces, Loki for logs, Mimir for metrics. This stack avoids DataDog/New Relic vendor lock-in while providing equivalent capability — the tradeoff being operational overhead, justified in ADR-013.

References: [OpenTelemetry docs](https://opentelemetry.io/docs/); Charity Majors et al., *Observability Engineering* (O'Reilly, 2022); ADR-013.

**ADR Traceability**
Validates **ADR-013** (OpenTelemetry + Grafana OSS over SaaS vendors). The PoC validates that the stack is deployable and correlated signals are achievable before it is required in the full spine (PoC 15).

**Prerequisites**
- Prior PoCs: 01–06 completed and AC satisfied.
- Tooling: Go 1.22+, `helm`.

**Experiment Specification**
Deploy OTel Collector, Grafana Tempo, Grafana Loki, Grafana Mimir, and Grafana OSS via Helm into namespace `observability`. Write a minimal Go HTTP service that: (1) emits a trace span for each request using the OTel Go SDK; (2) logs the trace ID in a structured JSON log; (3) increments a `requests_total` counter metric. Deploy the service to Kubernetes. Send 10 requests. In Grafana, locate a trace in Tempo, jump to the correlated log in Loki using the trace ID, and verify the metric in Mimir. Write findings to `poc-07/README.md`.

**Acceptance Criteria**
- AC-1: All observability pods (OTel Collector, Tempo, Loki, Mimir, Grafana) reach `Running` state.
- AC-2: A trace for a request is visible in Grafana Tempo with at least one span.
- AC-3: The trace ID from Tempo is used to locate the correlated log entry in Loki.
- AC-4: `requests_total` metric is queryable in Grafana with a count of 10 after 10 requests.
- AC-5: `poc-07/README.md` documents the instrumentation code, Grafana queries used, and a screenshot description of the correlated view.

**Reflection Prompts**
1. Why is `pipeline_run_id` a better correlation key for Iris than a per-request trace ID?
2. What is the operational cost of running Tempo, Loki, and Mimir vs. using a SaaS like DataDog?
3. How would you detect a broken instrumentation (service running but emitting no traces)?
4. What is the difference between a span and a trace?

---

## Phase Gate I → II

All 7 PoCs (01–07) must have all acceptance criteria satisfied before proceeding to Phase II.

Checklist:
- [ ] PoC 01 — all 4 AC satisfied
- [ ] PoC 02 — all 5 AC satisfied
- [ ] PoC 03 — all 5 AC satisfied
- [ ] PoC 04 — all 5 AC satisfied
- [ ] PoC 05 — all 5 AC satisfied
- [ ] PoC 06 — all 5 AC satisfied
- [ ] PoC 07 — all 5 AC satisfied

---

## Phase II — Security & Policy Plane

> **Cluster note:** PoC 08 (Cilium) requires a dedicated `kind` cluster with `disableDefaultCNI: true`. This cluster is destroyed after PoC 08. PoCs 09–12 resume on the standard `iris-lab-01` cluster.

> **Negative test requirement:** Every acceptance criteria set in Phase II includes at least one negative test — confirming that the security control DENIES what it is supposed to deny, not just that it ALLOWS what it should allow.

---

### PoC 08 — `k8s-cilium`

**Learning Objectives**
- LO-1: Bootstrap a `kind` cluster with Cilium as the CNI (replacing the default).
- LO-2: Understand eBPF as the enforcement mechanism: kernel-level vs. iptables.
- LO-3: Apply a `CiliumNetworkPolicy` and verify cross-namespace traffic is denied.

**Theoretical Background**
Cilium uses eBPF (extended Berkeley Packet Filter) to enforce network policies at the Linux kernel level, bypassing iptables entirely. This provides: (1) lower latency enforcement; (2) identity-aware policies (SPIFFE identity, not just IP); (3) L7 visibility (HTTP method, path-level policies).

For Iris, Cilium is the zero-trust enforcement layer for tenant isolation. A misconfigured standard tenant pod must not be able to reach another tenant's namespace — this is a hard security boundary, not a soft convention. Cilium makes this enforcement kernel-level and auditable.

The choice to use Cilium over Calico or Flannel is irreversible at cluster bootstrap: CNI replacement requires cluster recreation. This makes PoC 08 the highest-stakes infrastructure decision to validate early.

References: [Cilium docs](https://docs.cilium.io/); [eBPF.io](https://ebpf.io/); ADR-008.

**ADR Traceability**
Validates **ADR-008** (Cilium eBPF over Calico/Flannel). Confirms that Cilium is installable on `kind`, that `CiliumNetworkPolicy` is enforceable, and that cross-namespace denial works before committing to it as the production CNI.

**Prerequisites**
- Prior PoCs: 01–07 completed and AC satisfied (familiarity, not dependency).
- **Dedicated cluster required**: create a new `kind` cluster with `disableDefaultCNI: true`.
- Tooling: `helm`, `cilium` CLI.

**Experiment Specification**
Bootstrap a new `kind` cluster named `iris-cilium` with `disableDefaultCNI: true` and no kube-proxy. Install Cilium via Helm with kube-proxy replacement enabled. Create two namespaces: `tenant-bims` and `tenant-acme`. Deploy an `nginx` pod in each. Apply a `CiliumNetworkPolicy` in `tenant-bims` that denies all ingress from `tenant-acme`. Verify denial: `curl` from `tenant-acme` pod to `tenant-bims` pod must time out. Verify allowance: `curl` within `tenant-bims` must succeed. Write findings to `poc-08/README.md`. Destroy the `iris-cilium` cluster after completion.

**Acceptance Criteria**
- AC-1: `cilium status` reports all components healthy.
- AC-2: `curl` from `tenant-acme` to `tenant-bims` times out (denial confirmed).
- AC-3: `curl` within `tenant-bims` returns HTTP 200 (allowance confirmed).
- AC-4: `cilium monitor` shows a dropped packet event for the denied request.
- AC-5: `poc-08/README.md` documents the `CiliumNetworkPolicy` manifest, both curl tests, and the monitor output.

**Reflection Prompts**
1. Why is CNI selection irreversible at cluster bootstrap — what makes it different from other infrastructure choices?
2. What is the difference between a `NetworkPolicy` (Kubernetes native) and a `CiliumNetworkPolicy`?
3. How would you write a Cilium policy that allows a pod to reach the PostgreSQL namespace but not the NATS namespace?
4. Why does Iris use Cilium for tenant isolation rather than relying on Kubernetes RBAC alone?

---

### PoC 09 — `k8s-spire`

**Learning Objectives**
- LO-1: Deploy SPIRE Server and Agent on Kubernetes via Helm.
- LO-2: Verify SVID issuance for a workload.
- LO-3: Establish mTLS between two services using their SVIDs — and confirm rejection without a valid certificate.

**Theoretical Background**
SPIFFE (Secure Production Identity Framework For Everyone) defines a standard for workload identity using URIs of the form `spiffe://<trust-domain>/<path>`. SPIRE implements SPIFFE: the Server is the certificate authority; the Agent runs on each node and attests workload identity via Kubernetes Service Account tokens.

In Iris, every service (connector, pipeline worker, ai-service) receives a SVID — a short-lived X.509 certificate proving its identity. mTLS between services uses these SVIDs: no static API keys, no long-lived credentials, automatic rotation. This is the zero-trust identity layer that Cilium network policies alone cannot provide (Cilium knows IP; SPIRE knows identity).

References: [SPIFFE spec](https://spiffe.io/docs/latest/spiffe-about/overview/); [SPIRE docs](https://spiffe.io/docs/latest/deploying/); ADR-009.

**ADR Traceability**
Validates **ADR-009** (SPIFFE/SPIRE for workload identity). Confirms SVID issuance works on Kubernetes and that mTLS with SVIDs is achievable before it is required for service-to-service communication in the full platform.

**Prerequisites**
- Prior PoCs: 01–07 completed and AC satisfied.
- **Cluster**: resume `iris-lab-01` (not the Cilium cluster).
- Tooling: `helm`, `spire-server` CLI (available via exec into the server pod).

**Experiment Specification**
Deploy SPIRE Server and SPIRE Agent via Helm into namespace `spire-system`. Register two workload entries: `spiffe://iris.local/connector` and `spiffe://iris.local/worker`. Write two minimal Go services: `connector` and `worker`. Each fetches its SVID from the SPIRE Agent socket. `connector` starts an mTLS server; `worker` connects to it using its SVID as client certificate, verifying the server's SVID. Confirm successful mTLS handshake. Then attempt connection from a third pod without a registered SVID — confirm TLS handshake failure. Write findings to `poc-09/README.md`.

**Acceptance Criteria**
- AC-1: SPIRE Server and Agent pods reach `Running` state.
- AC-2: `spire-server entry show` lists both workload entries.
- AC-3: `connector` pod fetches a valid SVID (confirmed via log output showing SPIFFE URI).
- AC-4: `worker` successfully completes mTLS handshake with `connector` — connection established.
- AC-5: Third pod without registered SVID fails TLS handshake — connection refused or certificate error logged.
- AC-6: `poc-09/README.md` documents workload entries, mTLS code, and both test outcomes.

**Reflection Prompts**
1. Why are short-lived SVIDs (default: 1 hour) preferable to long-lived TLS certificates?
2. What is the difference between authentication (SPIRE) and authorization (Cilium/OPA)?
3. How does SPIRE attest a workload's identity in Kubernetes — what does it verify?
4. How would you integrate SPIRE identity with Cilium policies for identity-aware network enforcement?

---

### PoC 10 — `k8s-eso`

**Learning Objectives**
- LO-1: Deploy HashiCorp Vault (dev mode) and External Secrets Operator on Kubernetes.
- LO-2: Sync a Vault secret into a Kubernetes Secret via an `ExternalSecret` resource.
- LO-3: Observe automatic secret rotation without pod restart.

**Theoretical Background**
The principle of secrets management is separation of concerns: the application does not own its credentials; a dedicated secrets store does. External Secrets Operator (ESO) bridges the gap between the secrets store (Vault in PoC; AWS Secrets Manager in production) and Kubernetes Secrets, syncing on a configurable interval.

In production Iris, ESO syncs secrets from AWS Secrets Manager using IRSA (IAM Roles for Service Accounts) — each tenant's service account has a dedicated IAM role with least-privilege access to its own secrets only. No static AWS credentials in pods. No manual `kubectl create secret`. No secrets in Git.

References: [ESO docs](https://external-secrets.io/); [HashiCorp Vault dev mode](https://developer.hashicorp.com/vault/docs/concepts/dev-server); ADR-014.

**ADR Traceability**
Validates **ADR-014** (External Secrets Operator for secrets management). Confirms the `ExternalSecret` → Kubernetes Secret sync model works before it is required for database credentials, AI provider keys, and NATS credentials in the full platform.

**Prerequisites**
- Prior PoCs: 01–07 completed and AC satisfied.
- Tooling: `helm`, `vault` CLI.

**Experiment Specification**
Deploy HashiCorp Vault in dev mode into namespace `vault-system`. Deploy ESO into namespace `external-secrets`. Write a secret `iris/bims/db-password` with value `supersecret` in Vault. Create a `SecretStore` pointing to Vault. Create an `ExternalSecret` that syncs `iris/bims/db-password` to a Kubernetes Secret named `bims-db-credentials`. Verify the Kubernetes Secret contains the correct value. Update the Vault secret to `rotated-secret`. Wait for the sync interval. Verify the Kubernetes Secret is updated without pod restart. Write findings to `poc-10/README.md`.

**Acceptance Criteria**
- AC-1: Vault and ESO pods reach `Running` state.
- AC-2: Kubernetes Secret `bims-db-credentials` is created and contains `db-password: supersecret`.
- AC-3: After Vault secret rotation to `rotated-secret`, the Kubernetes Secret is updated within the sync interval.
- AC-4: No pod restart is required for the secret update to propagate (confirmed via pod age in `kubectl get pods`).
- AC-5: `poc-10/README.md` documents the `SecretStore`, `ExternalSecret`, and rotation observation.

**Reflection Prompts**
1. What is the risk of storing secrets directly in Kubernetes Secrets without ESO?
2. How does IRSA eliminate static AWS credentials in production Iris pods?
3. What is the sync interval tradeoff — frequent sync vs. API rate limits on AWS Secrets Manager?
4. How would you handle a secret that ESO fails to sync — what is the fallback behavior?

---

### PoC 11 — `k8s-gatekeeper`

**Learning Objectives**
- LO-1: Deploy OPA/Gatekeeper on Kubernetes as an admission webhook.
- LO-2: Write a `ConstraintTemplate` in Rego that enforces a resource limits policy.
- LO-3: Confirm admission-time rejection of non-compliant pods and acceptance of compliant ones.

**Theoretical Background**
OPA/Gatekeeper implements policy-as-code at the Kubernetes admission layer. When a pod creation request arrives at the API server, Gatekeeper's admission webhook evaluates the request against all active `Constraint` resources. If any constraint is violated, the request is rejected before the pod is scheduled — shift-left enforcement.

In Iris, Gatekeeper enforces: (1) all pods must declare resource limits (preventing noisy-neighbor resource exhaustion in standard tier); (2) no pod may use `hostNetwork: true` or privileged containers; (3) all pods must have tenant labels. Policy violations are rejected at admission time with a structured error, creating an audit trail without human intervention.

References: [OPA Gatekeeper docs](https://open-policy-agent.github.io/gatekeeper/); [Rego language reference](https://www.openpolicyagent.org/docs/latest/policy-language/); ADR-015.

**ADR Traceability**
Validates **ADR-015** (OPA/Gatekeeper for admission-time policy enforcement). Confirms that policy-as-code enforcement is achievable and that Rego `ConstraintTemplate` authoring is understood before policies are required for the full platform.

**Prerequisites**
- Prior PoCs: 01–07 completed and AC satisfied.
- Tooling: `helm`.

**Experiment Specification**
Deploy OPA/Gatekeeper via Helm into namespace `gatekeeper-system`. Write a `ConstraintTemplate` named `K8sRequireResourceLimits` that rejects pods missing CPU or memory limits on any container. Instantiate a `Constraint` applying it to all namespaces. Attempt to deploy a pod without resource limits in namespace `iris-lab` — confirm rejection with a descriptive error message. Deploy a compliant pod with resource limits — confirm acceptance. Write findings to `poc-11/README.md`.

**Acceptance Criteria**
- AC-1: Gatekeeper pods reach `Running` state and the admission webhook is registered (`kubectl get validatingwebhookconfiguration`).
- AC-2: `ConstraintTemplate` `K8sRequireResourceLimits` is created and active.
- AC-3: Non-compliant pod deployment is rejected by the API server with an error message referencing the constraint.
- AC-4: Compliant pod (with resource limits) is accepted and reaches `Running` state.
- AC-5: `poc-11/README.md` documents the `ConstraintTemplate` Rego policy, both test manifests, and the rejection error message.

**Reflection Prompts**
1. What is the difference between a `ConstraintTemplate` and a `Constraint` in Gatekeeper?
2. Why is admission-time enforcement preferable to a post-deployment audit for resource limits?
3. How would you write a Gatekeeper policy that requires all Iris pods to have a `tenant-id` label?
4. What is the risk of a Gatekeeper misconfiguration that rejects all pods — how do you recover?

---

### PoC 12 — `k8s-argocd`

**Learning Objectives**
- LO-1: Deploy ArgoCD on Kubernetes and point an `Application` at a Git repository.
- LO-2: Observe GitOps sync: a manifest change in Git propagates to the cluster automatically.
- LO-3: Observe drift detection and auto-remediation: a manually deleted resource is restored.

**Theoretical Background**
GitOps (Weaveworks model) treats Git as the single source of truth for cluster state. The desired state is declared in Git; a controller (ArgoCD) continuously reconciles actual cluster state toward it. Imperative `kubectl apply` commands are eliminated from the deployment path — the only valid way to change cluster state is to merge to Git.

In Iris, ArgoCD manages all platform components: NATS, Temporal, Qdrant, PostgreSQL, the Iris Operator, and all tenant namespace configurations. Drift detection ensures that manual interventions (emergency patches, accidental deletions) are detected and remediated within seconds. The Git history is the audit trail.

References: [ArgoCD docs](https://argo-cd.readthedocs.io/); Weaveworks, "GitOps — Operations by Pull Request" (2017); ADR-017.

**ADR Traceability**
Validates **ADR-017** (ArgoCD GitOps for delivery). Confirms that GitOps sync and drift detection work before ArgoCD is responsible for delivering the full Iris platform.

**Prerequisites**
- Prior PoCs: 01–07 completed and AC satisfied.
- Tooling: `helm`, `argocd` CLI, a Git repository (GitHub or local Gitea).

**Experiment Specification**
Deploy ArgoCD via Helm into namespace `argocd`. Create an ArgoCD `Application` pointing to a Git repo containing a single nginx Deployment manifest (1 replica). Sync the application — confirm the Deployment is created in the cluster. Change the replica count to 3 in Git and push. Observe ArgoCD auto-sync updating the Deployment. Manually delete the Deployment using `kubectl delete`. Observe ArgoCD detecting drift and restoring the Deployment within 3 minutes. Write findings to `poc-12/README.md`.

**Acceptance Criteria**
- AC-1: ArgoCD pods reach `Running` state and UI is accessible.
- AC-2: `Application` shows `Synced` status after initial sync.
- AC-3: After replica count change in Git, the Deployment is updated to 3 replicas within the sync window.
- AC-4: After manual deletion, ArgoCD detects drift and restores the Deployment without manual intervention.
- AC-5: `poc-12/README.md` documents the Application manifest, sync observation, and drift detection timeline.

**Reflection Prompts**
1. What is the difference between ArgoCD sync and ArgoCD auto-sync?
2. Why is `kubectl apply` dangerous in a GitOps model — what problem does it create?
3. How would you handle a hotfix that needs to be applied faster than a Git merge allows?
4. How does ArgoCD's drift detection change the operational model for the Iris platform team?

---

## Phase Gate II → III

All 5 PoCs (08–12) must have all acceptance criteria satisfied before proceeding to Phase III.

Checklist:
- [ ] PoC 08 — all 5 AC satisfied
- [ ] PoC 09 — all 6 AC satisfied
- [ ] PoC 10 — all 5 AC satisfied
- [ ] PoC 11 — all 5 AC satisfied
- [ ] PoC 12 — all 5 AC satisfied

---

## Phase III — Integration & Pipeline Spine

> Phase III is the convergence of all prior PoCs. Components deployed in Phase I are required. Phase II components (Cilium, SPIRE, ESO, Gatekeeper, ArgoCD) are not required for the integration PoCs — they are the production hardening layer applied after the pipeline spine is validated.

---

### PoC 13 — `nats-temporal`

**Learning Objectives**
- LO-1: Wire a NATS JetStream consumer to trigger a Temporal workflow on message arrival.
- LO-2: Observe end-to-end flow: `nats pub` → consumer → Temporal workflow → completion.
- LO-3: Understand the subject-hierarchy routing pattern as the pipeline entry point.

**Theoretical Background**
Event-driven workflow triggering is the primary ingestion pattern for Iris. When a connector (Jira, GitHub, Slack) produces normalized evidence, it publishes to `iris.<tier>.<tenant>.jobs`. A NATS consumer polls this subject and, upon receiving a message, starts a Temporal workflow for that tenant's pipeline. The workflow is the durable execution unit; NATS is the durable delivery mechanism.

This separation is deliberate: NATS handles delivery guarantees and backpressure; Temporal handles execution state and retry. Neither is responsible for what the other does. Consumer lag on NATS is the signal that pipeline workers are overloaded; Temporal activity failures are the signal that individual steps are failing.

References: ADR-010 (NATS); ADR-001 (Temporal); Iris PLATFORM_ARCH.md.

**ADR Traceability**
Validates the integration of **ADR-010** (NATS) with **ADR-001** (Temporal). This is the event-driven pipeline entry point that all Iris connectors will use.

**Prerequisites**
- Prior PoCs: 01–07 completed and AC satisfied.
- Components running: NATS (PoC 02), Temporal + PostgreSQL (PoC 04).

**Experiment Specification**
Deploy NATS and Temporal on the `iris-lab-01` cluster (from PoC 02 and PoC 04). Write a Go NATS consumer that subscribes to `iris.standard.*.jobs`. On message receipt, start a Temporal workflow (`ProcessJobWorkflow`) passing the message payload. The workflow has two activities: (1) `ParseJob` (log the payload); (2) `MarkComplete` (log completion). Publish a message to `iris.standard.bims.jobs` using `nats pub`. Verify in Temporal UI that `ProcessJobWorkflow` starts and completes. Write findings to `poc-13/README.md`.

**Acceptance Criteria**
- AC-1: NATS consumer starts and subscribes to `iris.standard.*.jobs`.
- AC-2: After `nats pub` to `iris.standard.bims.jobs`, `ProcessJobWorkflow` appears in Temporal UI as `Running`.
- AC-3: Workflow completes successfully with both activities visible in event history.
- AC-4: Publishing to `iris.standard.acme.jobs` also triggers the workflow (wildcard routing confirmed).
- AC-5: `poc-13/README.md` documents the consumer code, workflow code, and Temporal UI observation.

**Reflection Prompts**
1. What happens if the NATS consumer crashes after receiving a message but before starting the Temporal workflow — is the message lost?
2. Why is the NATS consumer a thin dispatcher (just starts workflows) rather than a full processor?
3. How does the subject hierarchy (`iris.standard.bims.jobs`) map to tenant isolation in the pipeline?
4. What would consumer lag of 500 messages indicate about the health of the Temporal worker pool?

---

### PoC 14 — `temporal-litellm-pg`

**Learning Objectives**
- LO-1: Build the minimal pipeline worker pattern: Temporal workflow → LiteLLM call → PostgreSQL write.
- LO-2: Understand activity idempotency and why it matters for AI calls.
- LO-3: Validate that structured AI output can be reliably persisted as a pipeline result.

**Theoretical Background**
This PoC implements the minimal Iris pipeline worker pattern. A Temporal workflow orchestrates two activities: (1) `ClassifyEvidence` — calls LiteLLM with a prompt and returns a structured JSON classification; (2) `PersistResult` — writes the classification to PostgreSQL. This is the atomic unit that every Iris pipeline stage is built from.

Activity idempotency is critical: if `ClassifyEvidence` succeeds but `PersistResult` fails, Temporal retries `PersistResult` — not `ClassifyEvidence`. This avoids double AI billing. Temporal achieves this by recording activity completion in workflow history before executing the next activity.

Structured output (JSON mode) is the contract between the AI layer and the storage layer. LiteLLM's provider-agnostic interface means the same structured output contract works regardless of whether the provider is Bedrock, OpenAI, or Vertex AI.

References: ADR-001 (Temporal); ADR-012 (LiteLLM); ADR-011 (PostgreSQL).

**ADR Traceability**
Validates the integration of **ADR-001** (Temporal), **ADR-012** (LiteLLM), and **ADR-011** (PostgreSQL). This is the core pipeline worker pattern for every Iris compute stage.

**Prerequisites**
- Prior PoCs: 01–07 completed and AC satisfied.
- Components running: Temporal + PostgreSQL (PoC 04), LiteLLM (PoC 06).

**Experiment Specification**
Deploy Temporal, PostgreSQL, and LiteLLM on `iris-lab-01`. Write a Go Temporal workflow `ClassifyEvidenceWorkflow` with two activities: (1) `ClassifyEvidence` — calls LiteLLM `/chat/completions` with a prompt asking for JSON classification of a fake support ticket (fields: `category`, `severity`, `confidence`); (2) `PersistResult` — inserts the JSON result into a `classifications` table in PostgreSQL. Trigger the workflow. Verify the classification is written to PostgreSQL. Simulate a `PersistResult` failure (return error on first attempt) and confirm Temporal retries only `PersistResult`, not `ClassifyEvidence`. Write findings to `poc-14/README.md`.

**Acceptance Criteria**
- AC-1: `ClassifyEvidenceWorkflow` completes successfully and a row exists in `classifications` table.
- AC-2: The row contains valid JSON with `category`, `severity`, and `confidence` fields.
- AC-3: After simulating `PersistResult` failure, Temporal event history shows `ClassifyEvidence` executed once and `PersistResult` retried — not `ClassifyEvidence` retried.
- AC-4: PostgreSQL row is correctly written on retry without duplicate `ClassifyEvidence` call.
- AC-5: `poc-14/README.md` documents the workflow, activities, idempotency test, and PostgreSQL row contents.

**Reflection Prompts**
1. Why would retrying `ClassifyEvidence` on `PersistResult` failure be costly for Iris at scale?
2. How does Temporal's activity completion recording in event history guarantee idempotency?
3. What is the risk of using unstructured AI output (free text) instead of JSON mode for pipeline results?
4. How would you add a `pipeline_run_id` to this pattern to enable OTel correlation in PoC 15?

---

### PoC 15 — `full-spine` (Capstone)

**Learning Objectives**
- LO-1: Wire all prior components into an end-to-end pipeline spine.
- LO-2: Propagate `pipeline_run_id` as a correlation key across NATS, Temporal, LiteLLM, PostgreSQL, and Qdrant.
- LO-3: View a fully correlated distributed trace in Grafana Tempo spanning all services.
- LO-4: Evaluate the spine as an architectural fitness function for the Iris v1-alpha pipeline.

**Theoretical Background**
A distributed trace is the proof that a system is coherent. In a microservices architecture, it is easy to have a system where each component works in isolation but the end-to-end flow is broken due to missing context propagation, incorrect span parenting, or dropped trace IDs. The full spine PoC is the first moment where Iris's architectural coherence can be empirically validated.

`pipeline_run_id` is the Iris-specific correlation key. It is generated when a job message enters NATS and must appear as a span attribute, log field, PostgreSQL column, and Qdrant payload field across the entire execution. A missing `pipeline_run_id` in any service is a signal of a broken instrumentation contract.

The full spine is also an architectural fitness function: if the end-to-end trace is clean, coherent, and observable, the architecture is sound. If it is fragmented or missing spans, the architecture has integration problems that would compound at scale.

References: ADR-001, ADR-002, ADR-010, ADR-011, ADR-012, ADR-013; Iris PLATFORM_ARCH.md; Ford et al., *Building Evolutionary Architectures* (O'Reilly, 2017) — fitness functions.

**ADR Traceability**
Validates the integration of **ADR-001, ADR-002, ADR-010, ADR-011, ADR-012, ADR-013** simultaneously. This is the convergence point for all foundational architecture decisions.

**Prerequisites**
- Prior PoCs: 01–14 completed and ALL AC satisfied.
- Components running: NATS (02), PostgreSQL (03), Temporal (04), Qdrant (05), LiteLLM (06), OTel + Grafana (07).

**Experiment Specification**
Deploy all six components on `iris-lab-01`. Write a Go NATS consumer that: on message receipt to `iris.standard.bims.jobs`, generates a `pipeline_run_id` (UUID) and starts a Temporal workflow `FullSpineWorkflow`. The workflow has four activities:
1. `ClassifyEvidence` — calls LiteLLM with the message payload; returns JSON classification tagged with `pipeline_run_id`.
2. `PersistClassification` — writes to PostgreSQL `classifications` table with `pipeline_run_id` column.
3. `EmbedResolution` — calls LiteLLM to generate a 1536-dim embedding for the classification text.
4. `UpsertToQdrant` — inserts the embedding into Qdrant collection `resolution-memory-bims` with `pipeline_run_id` as payload field.

All services instrument OTel spans with `pipeline_run_id` as a span attribute. Logs include `pipeline_run_id` as a structured field. Publish one message to NATS and trace the full execution in Grafana Tempo. Write findings to `poc-15/README.md`.

**Acceptance Criteria**
- AC-1: A single `nats pub` to `iris.standard.bims.jobs` results in a `FullSpineWorkflow` completion in Temporal UI.
- AC-2: A PostgreSQL row exists in `classifications` with the correct `pipeline_run_id`.
- AC-3: A Qdrant point exists in `resolution-memory-bims` with `pipeline_run_id` matching the PostgreSQL row.
- AC-4: A single correlated trace in Grafana Tempo spans NATS consumer → Temporal worker → LiteLLM → PostgreSQL → Qdrant with `pipeline_run_id` as a span attribute on every span.
- AC-5: The `pipeline_run_id` is locatable in Loki logs from at least three different services.
- AC-6: No manual intervention is required between `nats pub` and Grafana trace visualization.
- AC-7: `poc-15/README.md` documents the full spine architecture, `pipeline_run_id` propagation strategy, Grafana trace screenshot description, and all AC observations.

**Capstone Reflection**
1. Which component is the most likely single point of failure in production? How would you address it?
2. Where in the spine would you add a circuit breaker — and what would trigger it?
3. How does this spine map to the Iris evidence ingestion → recommendation pipeline defined in PLATFORM_ARCH.md?
4. Which ADR would you revisit or challenge after running this PoC end-to-end, and why?
5. What is missing from this spine that the v1-alpha pipeline requires — what is the next engineering step?

---

## Appendix A — ADR Coverage Matrix

| ADR | Title | PoC(s) that validate it |
|-----|-------|------------------------|
| ADR-001 | Temporal self-hosted | 04, 13, 14, 15 |
| ADR-002 | Qdrant self-hosted | 05, 15 |
| ADR-007 | Kubernetes runtime | 01 (all PoCs depend on it) |
| ADR-008 | Cilium eBPF | 08 |
| ADR-009 | SPIFFE/SPIRE | 09 |
| ADR-010 | NATS JetStream | 02, 13, 15 |
| ADR-011 | PostgreSQL control plane | 03, 04, 13, 14, 15 |
| ADR-012 | LiteLLM AI gateway | 06, 14, 15 |
| ADR-013 | OTel + Grafana OSS | 07, 15 |
| ADR-014 | External Secrets Operator | 10 |
| ADR-015 | OPA/Gatekeeper | 11 |
| ADR-017 | ArgoCD GitOps | 12 |

---

## Appendix B — Tooling Prerequisites

Install before beginning:

```bash
brew install kind kubectl helm nats-io/nats-tools/nats
brew install go   # 1.22+
brew install vault argocd cilium-cli
```

Docker Desktop or OrbStack required for `kind`.

---

*End of Iris PoC Curriculum — Lab Syllabus Design*
