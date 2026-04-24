# Iteration 001 — AWS service coverage (S3, SQS, SNS, Lambda, DynamoDB, API Gateway, IAM, CloudFormation)

**Status:** keep  
**Scores:** coverage=76.2, quality=52.5, total=62.0  
**Timestamp:** 2026-04-24T00:56:59.986122+00:00  

---

I now have sufficient data to write the full research report.

---

## Findings

### Context: The LocalStack Inflection Point

As of **March 23, 2026**, LocalStack sunset its Community Edition entirely. The core GitHub repository was archived (read-only), and the `localstack/localstack:latest` Docker image now requires a `LOCALSTACK_AUTH_TOKEN` for all use cases — including the free "Hobby" tier, which is restricted to non-commercial, personal use. Commercial use requires paid subscriptions [starting at $39/month](https://www.infoq.com/news/2026/02/localstack-aws-community/). Teams that pinned to `localstack/localstack:3.8` or earlier retain a working image but receive no future security patches or service updates. [This InfoQ article](https://www.infoq.com/news/2026/02/localstack-aws-community/) and [this blog post](https://kkm-mako.com/en/blog/articles/localstack-github-archived-account-required/) confirm the timeline. This has triggered rapid growth in alternatives.

---

### Tool 1: MiniStack (ministackorg/ministack)

**What it is:** A Python-based, MIT-licensed AWS emulator started as a direct response to LocalStack's commercial pivot. Formerly at `nahuelnucera/ministack`, now maintained at [`ministackorg/ministack`](https://github.com/ministackorg/ministack). Runs on a single port (4566), installable via `pip install ministack` or Docker.

**Architecture:** Python 3.12 process acting as a gateway router for all services, using in-memory state for most services and Docker containers (via the Docker socket) for RDS, ElastiCache, and ECS workloads.

#### Service Coverage Matrix (MiniStack)

| Service | Coverage | Notes |
|---------|----------|-------|
| **S3** | ✅ Full | Versioning, encryption, lifecycle, CORS, ACL, Object Lock (retention + legal hold), replication stubs, multipart upload, event notifications (→Lambda), S3 EventBridge notifications |
| **SQS** | ✅ Full | Standard + FIFO with deduplication, DLQ, visibility timeout, batch ops; both Query API and JSON protocol |
| **SNS** | ✅ Full | → SQS fanout, → Lambda fanout (synchronous invocation); FIFO topics with dedup and sequence numbers |
| **DynamoDB** | ✅ Full | GSI/LSI, transactions, TTL (background reaper), PITR, Streams (INSERT/MODIFY/REMOVE with StreamViewType) |
| **Lambda** | ✅ Functional | Python + Node.js warm worker pool (no Docker spin-up); `provided.al2023`/`provided.al2` via Docker RIE; SQS, Kinesis, DynamoDB Streams ESMs; Function URLs; Layers; Aliases; Concurrency |
| **IAM** | ⚠️ Partial | Full CRUD (users, roles, policies, groups, instance profiles, OIDC providers); no documented access-control enforcement for API calls |
| **STS** | ⚠️ Limited | `GetCallerIdentity`, `AssumeRole`, `GetSessionToken`, `AssumeRoleWithWebIdentity` — 4 of ~10 AWS operations |
| **CloudFormation** | ✅ Listed | Present in service list; depth of resource-type coverage [unverified] — no published operation count |
| **API Gateway v1 (REST)** | ❌ **Missing** | Not listed in the service table. Only API Gateway v2 (HTTP + WebSocket) is documented |
| **API Gateway v2 (HTTP)** | ✅ Full | Full control+data plane; Lambda proxy, HTTP proxy, MOCK integrations; JWT/Lambda authorizers; WebSocket `$connect`/`$disconnect`/`$default`; path-based dispatch (no DNS override needed) |
| **EventBridge** | ✅ Full | Custom buses, rules, Lambda/SQS/S3 targets, replays, API destinations, EventBridge Scheduler |
| **Kinesis** | ✅ Functional | Streams, shards, put/get records; AWS limits enforced (1 MB/record) |
| **Step Functions** | ✅ Full | Full ASL interpreter (Pass/Task/Choice/Wait/Map/Parallel); TestState API; SFN_MOCK_CONFIG for AWS SFN Local-compatible testing; `waitForTaskToken`; nested startExecution.sync |
| **RDS** | ✅ Real Docker | Actual PostgreSQL/MySQL containers launched per `CreateDBInstance` |
| **ElastiCache** | ✅ Real Docker | Real Redis container |
| **ECS** | ✅ Real Docker | Real container lifecycle |
| **Athena** | ✅ Real SQL | Powered by DuckDB — actual SQL execution |
| **Secrets Manager** | ✅ Functional | Versioning, rotation, resource policies |
| **SSM Parameter Store** | ✅ Full | String, SecureString, StringList; history; labels |
| **CloudWatch Logs/Metrics** | ✅ Functional | FilterLogEvents with glob/AND/exclusion; alarms; dashboards; CBOR + JSON |
| **SES / SES v2** | ✅ Functional | Stored in-memory (not actually sent) |
| **ACM** | ✅ Functional | Auto-issued certs, DNS validation records, SAN support |
| **WAF v2** | ✅ Functional | WebACL, IP sets, rule groups, associations |
| **EC2** | ✅ Functional | Instances, VPCs, subnets, security groups, Elastic IPs |
| **Cognito** | ❌ Not found | Not listed in reviewed service table |
| **KMS** | ❌ Not found | Not listed in reviewed service table |
| **MSK / Kafka** | ❌ Not found | Not listed |

**Cross-service integration:** SNS→SQS fanout ✅, SNS→Lambda ✅, S3→Lambda event notifications ✅, S3→EventBridge ✅, EventBridge→Lambda ✅, SQS/Kinesis/DynamoDB Streams → Lambda ESM ✅. The full S3→Lambda→SNS→SQS pipeline works end-to-end.

**Multi-tenancy:** A 12-digit numeric access key ID is used as the Account ID, enabling complete resource isolation between tenants on a single endpoint — useful for shared CI environments.

---

### Tool 2: Floci (floci-io/floci, formerly hectorvent/floci)

**Important note:** The Docker image has moved. `hectorvent/floci` receives **no further updates**. The current canonical image is `floci/floci:latest` at [`floci-io/floci`](https://github.com/floci-io/floci).

**What it is:** A Java-based (JAX-RS / Vert.x) AWS emulator compiled to a GraalVM native binary. MIT licensed, no auth required. Claims 35 services and **100% pass rate on 1,800+ AWS SDK compatibility tests** [(floci.io)](https://floci.io/).

**Architecture:** Three execution tiers: (1) stateless in-process services (SSM, SQS, SNS, IAM, etc.), (2) stateful in-process services (S3, DynamoDB), and (3) real Docker container services (Lambda, RDS, ElastiCache, MSK, ECS, EKS, OpenSearch, ECR). All services on port 4566.

#### Service Coverage Matrix (Floci)

| Service | Coverage | Notes |
|---------|----------|-------|
| **S3** | ✅ Full | Versioning, multipart, pre-signed URLs, Object Lock (COMPLIANCE/GOVERNANCE), event notifications |
| **SQS** | ✅ Full | Standard + FIFO, DLQ, visibility timeout, batch, tagging |
| **SNS** | ✅ Full | Topics, subscriptions, → SQS / Lambda / HTTP delivery |
| **DynamoDB** | ✅ Full | GSI/LSI, Query, Scan, TTL, transactions, batch operations |
| **DynamoDB Streams** | ✅ Full | Shard iterators, records, **Lambda ESM trigger** |
| **Lambda** | ✅ Real Docker | AWS ECR runtime images (java25/21/17/11/8, python3.14-3.9, nodejs24.x-16.x, ruby3.4-3.2, dotnet10/9/8/6, go1.x, provided.al2023/al2); warm container pool; SQS/Kinesis/DDB Streams ESM; Function URLs; aliases |
| **API Gateway REST (v1)** | ✅ Full | Resources, methods, stages, Lambda proxy, MOCK integrations, AWS integrations |
| **API Gateway v2 (HTTP)** | ✅ Full | Routes, integrations, JWT authorizers, stages |
| **IAM** | ✅ Configurable enforcement | Users, roles, groups, policies, instance profiles, access keys; `enforcement-enabled: true` activates real policy evaluation |
| **STS** | ✅ Full | All 7 operations (AssumeRole, AssumeRoleWithWebIdentity, AssumeRoleWithSAML, GetFederationToken, GetSessionToken, GetCallerIdentity, DecodeAuthorizationMessage) |
| **CloudFormation** | ✅ Listed | Stacks, change sets, resource provisioning; [DeepWiki analysis](https://deepwiki.com/floci-io/floci/6.3-cloudformation-service) confirms implementation; depth [unverified] |
| **Cognito** | ✅ Functional | User pools, app clients, auth flows, JWKS / OpenID well-known endpoints |
| **KMS** | ✅ Functional | Encrypt/decrypt, sign/verify, data keys, key rotation, aliases |
| **Kinesis** | ✅ Full | Streams, shards, enhanced fan-out, split/merge |
| **EventBridge** | ✅ Full | Custom buses, rules, SQS/SNS/Lambda targets; Scheduler with DLQ support |
| **CloudWatch Logs/Metrics** | ✅ Functional | Log groups, streams, filtering, custom metrics, alarms |
| **Secrets Manager** | ✅ Full | Versioning, resource policies, tagging |
| **SSM Parameter Store** | ✅ Full | Version history, labels, SecureString |
| **Step Functions** | ✅ Functional | ASL execution, task tokens, execution history |
| **RDS** | ✅ Real Docker | PostgreSQL 16 / MySQL 8.0 / MariaDB 11; IAM auth; JDBC-compatible |
| **ElastiCache** | ✅ Real Docker | Valkey/Redis, ACL-based IAM auth, SigV4 validation |
| **MSK** | ✅ Real Docker | Kafka-compatible via Redpanda |
| **ECS** | ✅ Real Docker | Clusters, task definitions, tasks, services, health checks |
| **EKS** | ✅ Real Docker | Real k3s Kubernetes API server per cluster |
| **OpenSearch** | ✅ Real Docker | Full OpenSearch 2 engine |
| **ECR** | ✅ Real OCI Registry | Real `registry:2` container; `docker push`/`docker pull` work natively |
| **Athena** | ⚠️ Mock only | Query state machine accepted; results are empty — no DuckDB/real SQL |
| **Data Firehose** | ✅ Functional | Streaming delivery; records flushed as NDJSON to S3 |
| **Bedrock Runtime** | ⚠️ Stub | Dummy responses for `Converse` and `InvokeModel`; streaming returns 501 |
| **SES / SES v2** | ✅ Functional | Email stored in-memory |
| **ACM** | ✅ Functional | Certificate issuance and validation lifecycle |
| **AppConfig / AppConfigData** | ✅ Functional | Applications, environments, profiles, dynamic retrieval |
| **Glue** | ✅ Functional | Data Catalog for metadata management |

**Cross-service integration:** The full event pipeline is wired: S3 event notifications → Lambda ✅, SNS → SQS fanout ✅, SNS → Lambda ✅, EventBridge rules → SQS/SNS/Lambda ✅, DynamoDB Streams → Lambda ESM ✅, SQS → Lambda ESM ✅, Kinesis → Lambda ESM ✅. Data Firehose → S3 ✅.

**Storage modes:** `memory` (ephemeral CI), `persistent` (saved at shutdown), `hybrid` (default: in-memory + async flush every 5s), `wal` (write-ahead log for maximum durability).

---

### Tool 3: Moto (Python library)

[**Moto**](https://github.com/getmoto/moto) is the most mature AWS mocking library, predating LocalStack's commercial pivot. It is not an emulator process but a Python in-process decorator/context-manager.

| Aspect | Details |
|--------|---------|
| License | Apache 2.0 |
| Mechanism | Intercepts boto3 calls via `unittest.mock` / `responses` library — **no real network, no Docker** |
| Service count | 90+ services ([docs index](https://docs.getmoto.org/en/latest/docs/services/index.html)) |
| Lambda | ❌ **No real code execution** — `Invoke` returns a simulated response; your handler never runs |
| API Gateway | ⚠️ REST API (v1) basic; HTTP API (v2) very limited |
| IAM | ✅ CRUD; ❌ **No policy enforcement** — IAM policies are stored but never evaluated against API calls |
| CloudFormation | ✅ Common resource types (S3, Lambda, DynamoDB, SQS, SNS, IAM, EC2, RDS); nested stacks and custom resources not supported |
| Cross-service events | ⚠️ Simulated only — S3 event notification metadata created but Lambda handler never invoked |
| Language support | **Python only** (via pytest/unittest decorators) |
| Startup overhead | None (in-process) |

**Critical limitation:** Moto is ideal for **unit testing AWS SDK call shapes and return values** but is a **non-starter for integration testing** of actual Lambda business logic, or for polyglot teams using Go, Java, or Node.js outside of moto-server mode.

---

### Tool 4: ElasticMQ

[**ElasticMQ**](https://github.com/softwaremill/elasticmq) (SoftwareMill) is a **SQS-only** in-memory message queue server. It does not emulate Lambda, S3, IAM, or any other service. DLQ, FIFO, and visibility timeout are supported. No cross-service event delivery. Best for isolated SQS contract testing when you need **zero overhead** and nothing else.

---

### Tool 5: MinIO

[**MinIO**](https://min.io) is an S3-compatible **object storage server only**. It does not emulate Lambda, IAM, SQS, or event notifications. It is production-grade for high-throughput S3 workloads (binary data, large objects) but offers **no AWS event pipeline integration**. Bucket notifications can be configured to webhooks/Kafka/NATS but not AWS SNS/SQS protocol.

---

## Evidence

| Data Point | Value | Source |
|-----------|-------|--------|
| LocalStack community edition sunset date | March 23, 2026 | [GitHub issue thread](https://github.com/elgohr/go-localstack/issues/1021) |
| LocalStack Hobby tier requirement | Account + auth token, personal use only | [LocalStack blog](https://blog.localstack.cloud/2026-upcoming-pricing-changes/) |
| LocalStack commercial entry price | $39/month | [InfoQ](https://www.infoq.com/news/2026/02/localstack-aws-community/) |
| MiniStack Docker image size | ~270 MB | [GitHub README](https://github.com/ministackorg/ministack) |
| MiniStack idle RAM | ~21 MB | [GitHub README](https://github.com/ministackorg/ministack) |
| MiniStack startup time | < 2 seconds | [GitHub README](https://github.com/ministackorg/ministack) |
| MiniStack service count (claimed) | 40+ | [GitHub README](https://github.com/ministackorg/ministack) |
| Floci Docker image size | ~90 MB | [GitHub README](https://github.com/floci-io/floci) |
| Floci idle RAM | ~13 MiB | [GitHub README / floci.io](https://floci.io/) |
| Floci startup time (API-ready) | ~24 ms | [GitHub README](https://github.com/floci-io/floci) |
| Floci service count | 35 | [GitHub README](https://github.com/floci-io/floci) |
| Floci AWS SDK compatibility tests | 1,800+ tests, 100% pass rate | [floci.io](https://floci.io/) — [unverified, self-reported] |
| LocalStack idle RAM (old community) | ~143 MiB (pre-sunset) | [Floci README comparison table](https://github.com/floci-io/floci) |
| LocalStack Docker image size (old) | ~1.0 GB | [Floci README comparison table](https://github.com/floci-io/floci) |
| MiniStack Lambda cold start (warm worker) | < 10 ms locally | [Dev.to benchmark](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p) — [unverified, self-reported by project author] |
| Floci Lambda cold start (Docker container) | 10–24 ms | [Dev.to benchmark](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p) — [unverified] |
| MiniStack pip install | `pip install ministack` | [GitHub README](https://github.com/ministackorg/ministack) |
| Floci Lambda runtimes supported | java25/21/17/11/8, python3.14-3.9, nodejs24.x-16.x, ruby3.4-3.2, dotnet10/9/8/6, go1.x, provided.al2023 | [GitHub README](https://github.com/floci-io/floci) |
| Moto services (approximate) | 90+ | [Moto docs index](https://docs.getmoto.org/en/latest/docs/services/index.html) |

> ⚠️ **Benchmark caveat:** The April 2026 performance benchmark ([Dev.to](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p)) was authored by MiniStack's own creator (nahuel990). Numbers should be independently validated before use in architectural decisions.

---

## Trade-offs

### Floci vs MiniStack: Head-to-Head

| Dimension | Floci Advantage | MiniStack Advantage |
|-----------|----------------|-------------------|
| **Resource efficiency** | 13 MiB idle, 90 MB image, 24 ms startup — exceptional for CI | Slightly larger (21 MB RAM, 270 MB image, <2s startup) |
| **Lambda runtime breadth** | Full matrix: Java 8–25, Python 3.9–3.14, Node 16–24, Ruby, .NET, Go, custom runtimes | Python + Node warm workers only; other runtimes via Docker RIE (good but different model) |
| **API Gateway** | Both REST (v1) **and** HTTP (v2) | **HTTP (v2) only** — critical gap for REST API workloads |
| **IAM enforcement** | Opt-in real policy evaluation (`enforcement-enabled: true`) | CRUD only — no documented enforcement |
| **STS coverage** | All 7 operations (incl. SAML federation) | 4 operations |
| **Athena** | Mock only (empty results) | Real SQL via DuckDB — actual query execution |
| **Cognito** | Full user pool + auth flows + JWKS | Not found in documented service list |
| **KMS** | Encrypt/decrypt, sign/verify, data keys | Not found in documented service list |
| **MSK / Kafka** | Real Redpanda broker | Not found |
| **EKS** | Real k3s cluster per EKS cluster | Not found |
| **Data Firehose** | NDJSON delivery to S3 | Not found |
| **Bedrock Runtime** | Stub (returns 501 for streaming) | Not found |
| **Step Functions** | ASL execution | Full ASL interpreter + SFN_MOCK_CONFIG + TestState API |
| **Maturity/community** | Newer; Slack community, Discussions | PyPI package; growing community |
| **Language** | GraalVM native (any language via Docker endpoint) | Python process; also any language via endpoint |

### Critical Non-Starters

**If your workload uses REST API Gateway (v1):** MiniStack is a **non-starter**. Floci supports both v1 and v2; MiniStack documents only v2. This affects the majority of serverless microservices deployed before ~2021.

**If you need real IAM policy evaluation:** Only Floci offers it (opt-in). Both MiniStack and Moto only store IAM resources without enforcing access. This means IAM-related bugs (missing policy statements, incorrect conditions) will not surface locally.

**If you need real Lambda code execution for integration tests:** Moto is a **non-starter** — it never runs your handler code. Both Floci and MiniStack run actual Lambda containers.

**If you need Go/Java/Ruby/Rust Lambda runtimes:** MiniStack requires Docker socket access for `provided.al2023` runtimes. Floci resolves all runtimes to official AWS ECR images, making this transparent.

**For ElasticMQ / MinIO:** These are appropriate only as supplements, not replacements. A CI pipeline using ElasticMQ for SQS and MinIO for S3 cannot test S3→Lambda triggers or SNS fanout to SQS without additional tooling.

### Cross-Service Pipeline Fidelity

The full serverless event pipeline (S3 upload → Lambda invocation → SNS publish → SQS delivery) is:
- **Floci:** End-to-end wired ✅ — real Lambda containers invoked by real S3 event notifications
- **MiniStack:** End-to-end wired ✅ — documented SNS→SQS, SNS→Lambda, S3→Lambda, EventBridge→Lambda
- **Moto:** Simulated only ⚠️ — S3 notification metadata created, Lambda handler never runs
- **ElasticMQ + MinIO combo:** Broken — no cross-service event delivery

### When to Choose Each Tool

| Scenario | Recommendation |
|----------|---------------|
| Full serverless stack (Lambda + API Gateway v1 + SQS/SNS + DynamoDB) CI/CD | **Floci** — v1 REST Gateway + real Lambda execution + full ESMs |
| Full serverless stack with HTTP API v2 only | **Floci or MiniStack** — both capable |
| Real Athena SQL query testing | **MiniStack** — DuckDB-backed; Floci returns empty results |
| Cognito-dependent auth flows | **Floci** — MiniStack has no documented Cognito |
| Python unit tests (no containers, no integration) | **Moto** — fastest, no Docker dependency |
| S3-only workloads needing production-grade throughput | **MinIO** — designed for high-throughput object storage |
| SQS-only contract testing in lightweight CI | **ElasticMQ** — minimal footprint |
| MSK / Kafka local testing | **Floci** — real Redpanda broker |
| Team needs IaC testing via Terraform/CDK/Pulumi | **Floci or MiniStack** — both claim compatibility |
| Multi-tenant shared CI endpoint (many pipelines, one container) | **MiniStack** — 12-digit key = account isolation built-in |

---

## Confidence

| Conclusion | Confidence | Rationale |
|-----------|-----------|-----------|
| LocalStack community edition is gone, auth required | **High** | Confirmed by multiple independent sources (InfoQ, GitHub issues, blog posts) with specific dates |
| Floci supports API Gateway REST v1; MiniStack does not | **High** | Directly read from both GitHub READMEs; MiniStack README has no REST API entry in service table |
| Both Floci and Moto support real Lambda execution via Docker | **High** | Floci README explicitly lists AWS ECR runtime images; MiniStack documents warm workers + RIE |
| Moto does NOT enforce IAM policies | **High** | Confirmed by Moto's own documentation and multiple community sources |
| Floci's 1,800-test / 100% pass rate claim | **Low** | Self-reported by project; no independent third-party test reproduction found |
| CloudFormation resource-type depth for either Floci or MiniStack | **Unresolved** | Both projects list CloudFormation in service tables, but no published coverage matrix of supported `AWS::*` resource types exists for either |
| Performance benchmarks (cold starts, RAM) | **Medium** | Image sizes confirmed from Docker Hub badges in READMEs; cold start and RAM numbers sourced partly from a benchmark authored by MiniStack's creator |
| MiniStack missing Cognito/KMS | **Medium** | Neither service appeared in the detailed service tables reviewed, but the README may not be exhaustive; should be verified by running `aws cognito-idp create-user-pool` against MiniStack |

---

## New Questions

1. **CloudFormation resource-type coverage depth:** Neither Floci nor MiniStack publishes a list of supported `AWS::*::*` CloudFormation resource types comparable to the CloudFormation Registry. What percentage of a typical Terraform/CDK deployment (covering S3, Lambda, API Gateway, SQS, SNS, IAM, DynamoDB, Step Functions) succeeds end-to-end against each emulator? This is the #1 unknown for IaC-driven workflows.

2. **IAM policy enforcement correctness in Floci:** Floci's opt-in `enforcement-enabled: true` IAM mode is mentioned but undocumented in terms of which policy features are evaluated (conditions, resource ARN matching, principal constraints, `aws:sourceIp`, SCPs). How close is it to real AWS IAM evaluation for deny/allow decisions? Testing this against real-world least-privilege policies would reveal whether it can catch IAM misconfiguration bugs locally.

3. **Ecosystem maturity and production adoption signals:** Both Floci and MiniStack were created in response to the March 2026 LocalStack sunset and are very new (months old). What is the actual production adoption, open issue count, bug rate, and maintainer responsiveness? GitHub star count, Docker Hub pull count, and open issue tracker review would quantify project health and risk for a long-term infrastructure commitment.

---

## Peer Review (codex-cli)

I found **12 issues**.

### Issue 1: Wrong cutoff for unauthenticated LocalStack versions
- **Type**: factual error
- **Location**: “Teams that pinned to `localstack/localstack:3.8` or earlier retain a working image”
- **Problem**: This cutoff appears wrong. LocalStack’s auth-token requirement starts with **2026.03.0** on **March 23, 2026**. The archived repo still shows **v4.14.0** released on **February 26, 2026**, which implies unauthenticated pre-2026.03.0 versions are not limited to `3.8` or earlier.
- **Impact**: Misleads readers about viable pinning options and overstates migration urgency.  
  Sources: [LocalStack Mar 23, 2026 release](https://blog.localstack.cloud/localstack-for-aws-release-2026-03-0/), [archived repo/releases](https://github.com/localstack/localstack)

### Issue 2: LocalStack “commercial use requires paid subscriptions” lacks key exceptions
- **Type**: missing nuance
- **Location**: “Commercial use requires paid subscriptions starting at $39/month”
- **Problem**: That omits at least two official carve-outs LocalStack publicized: a **Student plan** and a **free Open Source license** application path. The commercial/non-commercial framing is too absolute.
- **Impact**: Overstates lockout risk and weakens trust in the pricing summary.  
  Sources: [LocalStack Mar 5, 2026 post](https://blog.localstack.cloud/localstack-single-image-next-steps/), [Mar 23, 2026 release](https://blog.localstack.cloud/localstack-for-aws-release-2026-03-0/)

### Issue 3: MiniStack API Gateway v1 claim is directly contradicted by the project’s own site
- **Type**: factual error
- **Location**: “**API Gateway v1 (REST)** | ❌ **Missing**”
- **Problem**: MiniStack’s official site currently lists **API Gateway v1** explicitly: “REST APIs, resources, methods, integrations, stages, MOCK, Lambda proxy format 1.0.”
- **Impact**: This is a major product-selection error; it could wrongly disqualify MiniStack.  
  Source: [MiniStack official site](https://ministack.org/)

### Issue 4: MiniStack Cognito claim is wrong
- **Type**: factual error
- **Location**: “**Cognito** | ❌ Not found”
- **Problem**: MiniStack now lists **Cognito** on its official site, including user pools, auth flows, TOTP MFA, identity pools, and federated credentials.
- **Impact**: Undercuts the comparison table and several later recommendations.  
  Source: [MiniStack official site](https://ministack.org/)

### Issue 5: MiniStack KMS claim is wrong
- **Type**: factual error
- **Location**: “**KMS** | ❌ Not found”
- **Problem**: MiniStack now lists **KMS** on its official site.
- **Impact**: Same as above; readers may reject a viable tool for the wrong reason.  
  Source: [MiniStack official site](https://ministack.org/)

### Issue 6: MiniStack service matrix is stale across multiple rows
- **Type**: factual error
- **Location**: the whole “Service Coverage Matrix (MiniStack)”
- **Problem**: The matrix says MiniStack lacks API Gateway v1, Cognito, and KMS, but the official site now advertises **41 services**, including those. The research likely relied on an outdated README/service table.
- **Impact**: This is not a minor detail; it changes the head-to-head conclusion materially.  
  Source: [MiniStack official site](https://ministack.org/)

### Issue 7: Floci Docker image migration claim is unsupported and likely wrong
- **Type**: factual error
- **Location**: “The current canonical image is `floci/floci:latest`”
- **Problem**: Floci’s current official quick-start still uses **`hectorvent/floci:latest`**. I did not find an official source in your evidence proving `floci/floci:latest` is the canonical image.
- **Impact**: Readers may pull the wrong image and fail setup immediately.  
  Sources: [Floci quick start](https://floci.io/floci/getting-started/quick-start/), [Floci homepage](https://floci.io/)

### Issue 8: Floci architecture description does not match official positioning
- **Type**: unsupported claim
- **Location**: “Java-based (JAX-RS / Vert.x) AWS emulator compiled to a GraalVM native binary”
- **Problem**: Floci’s official site describes it as built with **Quarkus Native** / **Quarkus + GraalVM**. Your specific “JAX-RS / Vert.x” framing may be true internally, but it is not sourced here and may be outdated or incomplete.
- **Impact**: Lowers technical credibility; architecture claims should be sourced precisely.  
  Sources: [Floci homepage](https://floci.io/), [quick start](https://floci.io/floci/getting-started/quick-start/)

### Issue 9: Moto section contains multiple factual errors
- **Type**: factual error
- **Location**:  
  - “Intercepts boto3 calls via `unittest.mock` / `responses` library — **no real network, no Docker**”  
  - “Lambda | ❌ **No real code execution**”  
  - “Language support | **Python only**”
- **Problem**: Moto’s docs explicitly say:
  - it has **server mode** for **non-Python SDKs**
  - Lambda **invocation is supported** and runs in a **Docker container**
- **Impact**: This significantly mischaracterizes Moto’s capabilities.  
  Sources: [Moto server mode](https://docs.getmoto.org/en/latest/docs/server_mode.html), [Moto Lambda docs](https://docs.getmoto.org/en/5.1.9/docs/services/lambda.html)

### Issue 10: Moto IAM conclusion is overstated
- **Type**: missing nuance
- **Location**: “❌ **No policy enforcement** — IAM policies are stored but never evaluated”
- **Problem**: Moto’s docs now have **IAM-like Access Control**. They also warn it is **very basic** and defaults to no auth unless enabled. So “never evaluated” is too absolute.
- **Impact**: The conclusion is directionally fair for many teams, but technically inaccurate.  
  Source: [Moto IAM-like access control](https://docs.getmoto.org/en/5.0.21/docs/iam.html)

### Issue 11: The “Moto is a non-starter for integration testing” conclusion is too broad
- **Type**: missing nuance
- **Location**: “Moto is a non-starter for integration testing of actual Lambda business logic”
- **Problem**: Moto can execute Lambda in Docker. The real limitation is narrower: in decorator mode the Lambda container cannot reach Moto’s in-memory state unless you use MotoServer/MotoProxy correctly.
- **Impact**: Overstates the weakness and could cause readers to discard Moto where it may still fit.  
  Sources: [Moto Lambda docs](https://docs.getmoto.org/en/5.1.9/docs/services/lambda.html), [Moto server mode](https://docs.getmoto.org/en/latest/docs/server_mode.html)

### Issue 12: ElasticMQ description omits persistence and deployment nuance
- **Type**: missing nuance
- **Location**: “ElasticMQ is a **SQS-only in-memory** message queue server”
- **Problem**: “SQS-only” is fair, but “in-memory” is incomplete. ElasticMQ supports persisted queue config and SQL-backed persistence for queues/messages.
- **Impact**: Slightly understates ElasticMQ’s usefulness in test environments.  
  Source: [ElasticMQ GitHub](https://github.com/softwaremill/elasticmq)

### Issue 13: Confidence table has an internal contradiction
- **Type**: contradiction
- **Location**: “Both Floci and Moto support real Lambda execution via Docker” with rationale “Floci README explicitly lists AWS ECR runtime images; **MiniStack** documents warm workers + RIE”
- **Problem**: The claim names **Moto**, but the rationale cites **MiniStack** instead.
- **Impact**: Signals sloppy synthesis and makes the confidence section less trustworthy.

### Issue 14: MiniStack/Floci granular feature claims are over-precise relative to evidence
- **Type**: unsupported claim
- **Location**: many rows marked “✅ Full” with detailed subfeatures, e.g. MiniStack S3/Object Lock/replication stubs, DynamoDB PITR/Streams details, Step Functions APIs, Floci deep per-service specifics
- **Problem**: Much of this is presented at fine-grained API depth without corresponding primary-source citations or independent verification. In several cases the official sites give only high-level service bullets.
- **Impact**: Makes the report look more authoritative than the evidence supports.

### Issue 15: Important operational gaps are missing
- **Type**: gap
- **Location**: overall report
- **Problem**: The comparison underweights practical adoption factors:
  - host OS / CPU support
  - ARM vs x86 behavior
  - Docker socket security implications
  - persistence durability semantics
  - CI parallelism behavior
  - maintainer bus factor / issue responsiveness
  - migration friction from existing LocalStack Compose/Testcontainers setups
- **Impact**: Even if service parity were correct, this is still incomplete for real tool selection.

## Summary
- **Issues found**: **15**
- **Overall reliability assessment**: **low to medium**
- **What would most improve the findings**:
  1. Re-verify **MiniStack** against current official docs/site; that section is the most stale.
  2. Rewrite the **Moto** section using current docs; several core claims are now wrong.
  3. Replace granular “✅ Full” feature assertions with either:
     - linked primary evidence, or
     - explicit “claimed by vendor / not independently verified.”
  4. Add an operational-risk section, not just service coverage.
