# Local AWS Emulation in 2026: LocalStack Alternatives — Decision Report

**Prepared for:** Senior AWS Cloud Architects  
**Date:** April 24, 2026  
**Status:** Decision-ready draft — gaps noted explicitly

---

## Executive Summary

On **March 23, 2026**, LocalStack changed its distribution model: all images now require a `LOCALSTACK_AUTH_TOKEN`, ending the frictionless free-tier experience that made LocalStack a de facto standard. Teams choosing between paying for LocalStack Pro and migrating to open-source alternatives have two serious general-purpose candidates: **Floci** (`floci-io/floci`) and **MiniStack** (`ministackorg/ministack`). Both run on port 4566, require no auth token, and target LocalStack-style drop-in use. Neither is a safe bet if adopted blindly — both are under 90 days old as of this writing, and each carries specific fidelity risks that must be validated against your actual workloads. **Moto, ElasticMQ, and MinIO remain useful but specialized tools, not LocalStack replacements.** The recommendation is to validate your 3–5 most critical workflows against whichever finalist fits your profile before committing.

---

## Comparison Table

| Dimension | **LocalStack Pro** | **Floci** | **MiniStack** | **Moto** | **ElasticMQ / MinIO** |
|---|---|---|---|---|---|
| **License** | Commercial subscription | MIT | MIT | Apache 2.0 | Apache 2.0 |
| **Auth required** | Yes (token) | No | No | No | No |
| **Port** | 4566 | 4566 | 4566 | 5000 (server mode) | Varies |
| **Primary language** | Python | Java/GraalVM | Python | Python | Scala / Go |
| **Image size** | ~700 MB+ | [unverified] ~90 MB | [unverified] ~270 MB | N/A | Minimal |
| **Idle RAM** | ~300+ MB | [unverified] ~13 MiB | [unverified] ~21–30 MiB | In-process | Minimal |
| **Startup time** | ~5–15 s | [unverified] ~24 ms | [unverified] <2 s | Instant | Fast |
| **S3** | ✅ Full | ✅ | ✅ | ✅ | ✅ (MinIO only) |
| **SQS / SNS** | ✅ Full | ✅ | ✅ | ✅ | ✅ (ElasticMQ SQS only) |
| **Lambda (multi-runtime)** | ✅ Full | ✅ Docker-backed | ✅ Warm (Py/Node) + Docker | ⚠️ Limited | ❌ |
| **DynamoDB** | ✅ Full | ✅ (open bugs: GSI pagination, concurrent counters) | ✅ (stronger tested fidelity) | ✅ | ❌ |
| **API Gateway v1 (REST)** | ✅ Full | ✅ | ✅ (added recently; verify) | ⚠️ Partial | ❌ |
| **API Gateway v2 (HTTP)** | ✅ Full | ✅ | ✅ | ⚠️ Partial | ❌ |
| **IAM enforcement** | ✅ Full | ✅ Configurable | ⚠️ CRUD only | ⚠️ Partial | ❌ |
| **STS operations** | ✅ Full | ✅ 7 operations | ⚠️ 4 operations | ⚠️ Partial | ❌ |
| **CloudFormation** | ✅ Full | ⚠️ Silent stubs for some types | ✅ Broader; fail-loud semantics | ❌ | ❌ |
| **CDK / SAM** | ✅ Full | ⚠️ CFN stub risk | ✅ More events wired in CFN | ❌ | ❌ |
| **Terraform** | ✅ Full | ✅ Committed compat suite | ✅ Documented; no CI suite | ❌ | ❌ |
| **Cognito** | ✅ Full | ✅ | [inference] Claimed; verify | ❌ | ❌ |
| **KMS** | ✅ Full | ✅ | [inference] Claimed; verify | ✅ Partial | ❌ |
| **MSK / EKS / OpenSearch** | ✅ Full | ✅ Docker-backed | [inference] Partial | ❌ | ❌ |
| **Athena** | ✅ Full | ⚠️ Lifecycle mocked; results empty | ✅ Real SQL via DuckDB | ❌ | ❌ |
| **Testcontainers module** | ✅ Official | ✅ Official | ✅ Official | N/A | N/A |
| **Multi-tenant isolation** | ✅ | [unverified] | ✅ 12-digit account IDs | ❌ | ❌ |
| **Community age** | ~7 years | ~65 days | ~30 days | ~10 years | Mature |
| **GitHub stars** | N/A (closed source) | [unverified] ~4,140 | [unverified] ~2,186 | ~8,000+ | Varies |
| **Release cadence** | Monthly | [unverified] 2–3×/week | [unverified] 1+/day | Monthly | Stable |
| **Bus factor risk** | Low (company-backed) | Medium | High (~54% commits, 1 author) | Low | Low |

---

## Detailed Analysis

### 1. The LocalStack Licensing Shift

The trigger for this evaluation: LocalStack's `2026.03.0` release (March 23, 2026) unified the Community and Pro images under a single authenticated image. All containers now require `LOCALSTACK_AUTH_TOKEN` at startup. The old unauthenticated Community Edition path is no longer the default workflow. [inference] A free tier and student/open-source license application path reportedly still exist, but they change the operational dynamic: any CI pipeline or developer environment must now carry an auth credential.

**What this costs at LocalStack Pro pricing:** [unverified] pricing was not captured in the research base. Teams should evaluate the current pricing page directly.

The practical effect is clear regardless of pricing details: teams that relied on LocalStack for zero-credential local and CI use have a real reason to evaluate alternatives.

---

### 2. AWS Service Coverage

#### Core Serverless Stack (S3, SQS, SNS, Lambda, DynamoDB, API Gateway, IAM)

Both Floci and MiniStack cover the core serverless services. The gaps are in **behavioral correctness**, not just presence.

**DynamoDB correctness — important for production-comparable testing:**

Floci has two confirmed open bugs as of late April 2026:
- [unverified - GitHub issue #587] GSI query pagination produces incorrect `LastEvaluatedKey` when multiple items share an index sort key, causing query loops.
- [unverified - GitHub issue #571] Concurrent `UpdateItem` atomic counter operations are not serialized, producing duplicate counter values under load.

These are not edge cases; they affect common access patterns. MiniStack's DynamoDB test suite is materially deeper in reviewed evidence, and no equivalent open bugs were identified at the time of research. **MiniStack wins on DynamoDB behavioral fidelity as of April 2026.**

**Lambda runtimes:**

| Runtime | Floci | MiniStack |
|---|---|---|
| Python | ✅ Docker (AWS runtime image) | ✅ Warm worker |
| Node.js | ✅ Docker (AWS runtime image) | ✅ Warm worker |
| Java | ✅ Docker (AWS runtime image) | ⚠️ Docker/RIE only |
| .NET | ✅ Docker (AWS runtime image) | ⚠️ Docker/RIE only |
| Go | ✅ Docker (AWS runtime image) | ⚠️ Docker/RIE only |
| Ruby | ✅ Docker (AWS runtime image) | [unverified] |
| Custom runtimes | ✅ | [unverified] |

Floci also had three notable Lambda bugs in the reviewed period:
- [unverified - GitHub issue #432] Lambda containers could not reach S3 via default virtual-hosted-style hostnames; path-style access required.
- [unverified - GitHub issue #485] Timeouts leaked container handles, draining the warm pool and creating orphaned Docker processes.
- [unverified - GitHub issue #547] Nested handler paths (monorepo-style module paths) rejected at function creation, unlike AWS behavior.

MiniStack had fixed the nested-handler class of bug and had an end-to-end SQS→Lambda event source mapping test in its suite.

**Bottom line:** For polyglot/Java/.NET/Go teams, Floci is the stronger Lambda story. For Python/Node-primary teams, MiniStack's warm-worker model is simpler and showed steadier behavior in reviewed evidence.

**API Gateway:**

MiniStack added path-based API Gateway data-plane routing in v1.3.6 (April 20, 2026) via `localhost:4566`. This resolves the earlier limitation around wildcard `*.execute-api.localhost` hostname routing, which was awkward in browsers and strict HTTP clients. Both tools now support REST v1 and HTTP v2 — though MiniStack's docs evolved quickly enough that you should verify against current releases.

**IAM and STS:**

This is Floci's clearest head-to-head advantage.

| Capability | Floci | MiniStack |
|---|---|---|
| IAM policy enforcement | ✅ Configurable via `enforcement-enabled: true` | ⚠️ CRUD only |
| STS operations covered | [unverified] ~7 | [unverified] ~4 |

If catching authorization bugs locally (missing permissions, bad role assumptions, IAM policy mismatches) matters to your team, **Floci is the only contender with meaningful enforcement today.**

**Athena:**

MiniStack executes real SQL via DuckDB. Floci mocks the Athena query lifecycle but returns empty results. If your pipelines use Athena, **this is a decisive win for MiniStack.**

**Cognito, KMS, MSK, OpenSearch, EKS, ECR:**

Floci documents these as first-class services backed by real Docker infrastructure. MiniStack's docs have evolved to claim some of these (Cognito, KMS), but Floci has stronger and older evidence for advanced platform services. [inference] Teams using MSK/EKS/OpenSearch should consider Floci the default choice pending MiniStack verification.

---

### 3. CloudFormation, CDK, SAM, and Terraform

This dimension carries the highest selection risk for most teams and the starkest divergence between the two tools.

#### CloudFormation — the silent failure problem in Floci

Direct analysis of Floci's `CloudFormationResourceProvisioner.java` (reviewed, [unverified source URL]) revealed that unsupported CloudFormation resource types fall through to a **default stub path that marks them `CREATE_COMPLETE`** without provisioning the actual resource. Confirmed gap resource types include at minimum:

- `AWS::Lambda::EventSourceMapping`
- `AWS::Lambda::Permission`
- `AWS::SNS::Subscription`
- `AWS::StepFunctions::StateMachine`
- Some CloudWatch/Logs/ECS/Cognito-related paths

The danger is not that Floci doesn't support these — it's that stacks **appear to succeed** while critical event wiring is absent. A CDK or SAM deploy that provisions an SQS trigger for a Lambda function can return a successful stack with no functional trigger wired.

MiniStack's CloudFormation documentation explicitly lists `Lambda::Permission` and `Lambda::EventSourceMapping` as supported, and documents **`CREATE_FAILED`** semantics for unsupported types — the fail-loud behavior that makes gaps visible rather than silent.

MiniStack also covers a broader set of intrinsic functions:

| Function | Floci | MiniStack |
|---|---|---|
| `Fn::If`, `Fn::Equals`, `Fn::And`, `Fn::Or`, `Fn::Not` | [unverified] | ✅ Documented |
| `Fn::ImportValue` (cross-stack exports) | [unverified] | ✅ Documented |
| `Fn::Split`, `Fn::Select`, `Fn::GetAZs`, `Fn::Cidr` | [unverified] | ✅ Documented |
| `AWS::NoValue` | [unverified] | ✅ Documented |

**For CDK and SAM users, MiniStack carries materially lower IaC risk.** The evidence asymmetry is robust: Floci has confirmed silent-stub behavior; MiniStack has documented support plus fail-loud semantics for gaps.

#### Terraform

The situation reverses for Terraform, because Terraform talks directly to AWS APIs rather than through CloudFormation.

Floci has a committed compatibility suite (`compat-terraform/`) that uses provider `~> 6.0` and explicit `endpoints {}` blocks, validated against:

- S3, SQS + DLQ + redrive, SNS + SQS subscription
- DynamoDB, IAM, SSM, Secrets Manager
- RDS, Cognito User Pool
- CloudWatch metric alarms

MiniStack supports Terraform through the same `4566 + explicit endpoints` pattern but does not have an equivalent committed CI compat suite in reviewed evidence.

**Standard Terraform configuration for both tools:**

```hcl
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true

  endpoints {
    s3       = "http://localhost:4566"
    sqs      = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
    # ... all services
  }
}
```

**For Terraform-primary teams, Floci has the stronger validated story.**

#### CDK

Floci ships an official CDK compatibility harness using `cdklocal` with `LOCALSTACK_HOSTNAME` and `EDGE_PORT`. It validated Docker image Lambda functions (ECR/DockerImageFunction flow). However, the CloudFormation silent-stub risk still applies.

MiniStack documents a simpler native CDK path using plain `cdk` + `AWS_ENDPOINT_URL`, without requiring `cdklocal`. Its broader CloudFormation intrinsic function support and explicit `Lambda::EventSourceMapping` coverage make it more reliable for CDK stacks that wire event sources through CloudFormation.

---

### 4. Migration Effort

Both tools target near-drop-in compatibility with LocalStack at the network layer. The realistic migration scope by component:

| Component | Effort | Notes |
|---|---|---|
| Docker image swap | Trivial | Change one line in docker-compose.yml |
| Remove `LOCALSTACK_AUTH_TOKEN` | Trivial | Delete env var |
| Remove `SERVICES` env var | Trivial | Was optional; not needed |
| Docker socket mount | None (keep) | Required for Docker-backed services |
| Health checks | Low | MiniStack provides `/_localstack/health` compatibility alias; Floci health docs weaker |
| Container networking | Low | Floci: `FLOCI_HOSTNAME`; MiniStack: `MINISTACK_HOST` |
| Testcontainers | Low | Both have official modules |
| Persistence config | Low-Medium | Floci: richer modes (memory/persistent/hybrid/wal); MiniStack: `PERSIST_STATE=1` |
| IaC toolchain | Medium-High | CDK/SAM users must validate CFN behavior; Terraform easier |
| SDK endpoint config | Varies | Most AWS SDKs need `--endpoint-url` or env var; same pattern as LocalStack |
| CI pipeline config | Low-Medium | GitHub Actions: endpoint depends on host vs. container job context |
| `cdklocal` removal | Low (MiniStack) / None (Floci) | MiniStack may allow dropping `cdklocal` |
| IAM-sensitive flows | High | Floci enforcement config needed; MiniStack enforcement limited |

**Estimated migration effort by team profile:**

| Profile | Floci estimate | MiniStack estimate |
|---|---|---|
| Python/Node serverless, no IaC | 0.5–1 day | 0.5 day |
| CDK/SAM serverless, event-driven | 2–4 days + validation | 1–3 days + validation |
| Terraform-primary, multi-service | 1–2 days | 2–3 days |
| Java/.NET polyglot, microservices | 1–3 days | 2–4 days |
| Cognito/KMS/MSK heavy | 1–2 days + service testing | Unknown; verify first |
| Athena-dependent pipelines | Not suitable | 0.5–1 day |

All estimates assume no behavioral regressions in tested flows. Add 1–3 days for debugging if your workload hits one of the known open bugs.

---

### 5. CI/CD Integration

**Image pull size** is often the dominant CI cost, not startup latency alone:

| Tool | Image | Startup |
|---|---|---|
| LocalStack | ~700+ MB | 5–15 s |
| Floci | [unverified] ~90 MB | [unverified] ~24 ms |
| MiniStack | [unverified] ~270 MB | [unverified] <2 s |

Floci's raw CI efficiency advantage is real if the benchmarks hold. Both are faster and lighter than LocalStack Pro.

**Docker socket / privileged mode:**  
Neither requires privileged mode for in-process services. Docker-backed services (Lambda, RDS, ElastiCache, ECS, MSK, EKS) require `/var/run/docker.sock` mounting — standard Docker-out-of-Docker, not full DinD.

**GitHub Actions:**  
Both work as service containers. Endpoint is `localhost:4566` when the job runs on the host; use the service hostname when the job runs inside a container.

[unverified - Floci GitHub CI docs] Floci's CI docs still referenced the older `hectorvent/floci` image name even after the project moved to `floci/floci`. Confirm the correct image reference before configuring.

**MiniStack CI caveat:** An open issue was identified around Docker-mode Lambda execution when MiniStack itself ran inside a container and attempted to spawn sibling Lambda containers using host bind mounts. Teams running MiniStack inside a containerized CI job with Docker-backed Lambda should test this topology explicitly.

---

### 6. Community Maturity and Maintenance Risk

Both projects are extremely young. The community signals as of April 23, 2026:

| Signal | Floci | MiniStack |
|---|---|---|
| Project age | [unverified] ~65 days | [unverified] ~30 days |
| GitHub stars | [unverified] ~4,140 | [unverified] ~2,186 |
| Forks | [unverified] ~280 | [unverified] Not captured |
| Contributors | [unverified] ~60 | [unverified] ~36 |
| Commits | [unverified] ~380 | [unverified] ~260 |
| Top author commit % | [unverified] ~29% | [unverified] ~54% |
| Release cadence | [unverified] 2–3×/week | [unverified] 1+/day |
| Docker pulls | [unverified] 50,000+ (older image) | [unverified] ~19,500 |

**Assessment:**  
Floci looks larger and more distributed; MiniStack is growing faster but more centralized. Both represent early-stage bets. Neither has survived a full year of AWS API changes, a contributor attrition cycle, or a post-hype maintenance period.

The practical risk for enterprise teams: if either project slows or forks, you inherit the migration cost back to a supported platform. Neither project has an obvious commercial sustainability model, unlike LocalStack.

---

## Decision Framework

**Choose Floci when your team prioritizes:**

- Broadest documented AWS surface area (Cognito, KMS, MSK, EKS, OpenSearch, ECR, Firehose)
- IAM policy enforcement and security-posture testing locally
- Full STS coverage
- Polyglot Lambda runtimes (Java, .NET, Go, Ruby, custom)
- A validated Terraform compatibility story with an actual CI test suite
- Smallest CI footprint (image size, startup time)
- Docker image Lambda functions (CDK DockerImageFunction flows)

**Choose MiniStack when your team prioritizes:**

- Python/Node-primary serverless workloads
- Real Athena SQL execution (DuckDB-backed)
- CloudFormation/CDK/SAM correctness and fail-loud gap semantics
- Event-source wiring through CloudFormation (`Lambda::EventSourceMapping`, `Lambda::Permission`)
- DynamoDB behavioral fidelity in tested evidence
- LocalStack health-check compatibility aliases for smoother migration
- Multi-tenant account isolation
- Complex CFN intrinsic function support (`Fn::If`, `Fn::ImportValue`, `Fn::Cidr`, etc.)
- Dropping `cdklocal` in favor of native CDK tooling

**Choose Moto when:**

- You need fast Python unit tests with in-process AWS mocking
- You do not need cross-service integration or event pipelines
- SDK interaction correctness is sufficient; infrastructure fidelity is not the goal

**Keep LocalStack Pro when:**

- Your team depends on advanced services where neither alternative has proven coverage
- You need battle-tested IaC support without validation investment
- Regulatory or audit requirements demand a commercially supported tool
- The auth-token operational cost is acceptable and the subscription fits your budget

---

## Ranked Recommendations

**Confidence:** Medium (both tools are too young for high-confidence general endorsement)

### Recommendation 1 — Run a 2-week parallel validation sprint before deciding

**Confidence: High**  
Pick the 3–5 workflows that represent your hardest production requirements. Run them against both Floci and MiniStack concurrently. Focus on:

1. Your IaC deploy path (CDK/SAM/Terraform stack end-to-end)
2. Your event-source wiring (SQS→Lambda, SNS→Lambda, DynamoDB Streams→Lambda)
3. Your Lambda runtime(s), especially any Java/.NET/Go usage
4. Any Athena dependencies
5. Any IAM-sensitive flows with role assumptions

Do not choose based on documentation matrices alone.

---

### Recommendation 2 — Default to MiniStack for CDK/SAM serverless teams

**Confidence: Medium-High**  
The evidence for silent CloudFormation stub behavior in Floci is sourced from direct source analysis. The asymmetry is robust: MiniStack's fail-loud semantics and explicit `Lambda::EventSourceMapping` support make it the safer bet for CDK/SAM teams where CloudFormation is the wiring layer. Validate DynamoDB access patterns against the known Floci GSI/concurrency bugs.

---

### Recommendation 3 — Default to Floci for Terraform-primary or polyglot teams

**Confidence: Medium**  
Floci's committed Terraform compat suite provides meaningful confidence absent from MiniStack's current evidence base. For Java/.NET/Go Lambda runtimes, Floci's Docker-backed model is more transparent and broader. Factor in the open Lambda bugs (#432, #485, #547) and test your exact runtime and S3 access pattern.

---

### Recommendation 4 — Keep a specialized tool stack as a hedge

**Confidence: High**  
If either Floci or MiniStack covers 80% of your needs, consider pairing with a specialist:

- **ElasticMQ** alongside either tool for high-fidelity SQS contract tests where you want no emulation overhead
- **MinIO** for binary/object-heavy workloads with real throughput requirements
- **Moto** for Python unit tests where speed matters more than integration fidelity

---

## Known Gaps and Unresolved Questions

### 1. CloudFormation / IaC depth at real-world scale

The most critical unresolved risk. Floci's stub behavior is confirmed at the provisioner level, but the full scope of stubbed resource types is not enumerated. MiniStack's CloudFormation support is documented but not independently reproduced end-to-end at the time of research. Neither tool has been validated against a representative enterprise-scale CDK or SAM application.

### 2. IAM policy evaluation fidelity in Floci

Floci is the only candidate with enforcement-mode IAM, but how closely its policy evaluation semantics match AWS (condition keys, resource ARN pattern matching, service-linked roles, trust policies) has not been independently tested. Enforcement without correctness can give false confidence.

### 3. MiniStack documentation drift

MiniStack's documentation changed rapidly enough in April 2026 to invalidate research conclusions from the same month. Service matrices, API Gateway routing behavior, Cognito/KMS claims, and persistence behavior all evolved. Any assessment based on snapshots older than a few weeks should be re-verified against current docs and releases.

### 4. Long-term sustainability

Neither project has a clear commercial sustainability model. Floci's contributor distribution (top author ~29%) suggests better resilience than MiniStack (~54%), but both remain early-stage community bets. Enterprise adoption should include a contingency plan for maintainer withdrawal.

### 5. LocalStack free tier and OSS license path

[Inference] LocalStack reportedly retains a Student plan and an open-source license application path. Teams that qualify for either may find the migration effort exceeds the cost of staying. This was not independently verified and should be confirmed on the LocalStack pricing page before ruling it out.

### 6. Runtime fidelity vs. documented support

Throughout this report, "documented support" is weaker evidence than "source-confirmed implementation" or "independently reproduced end-to-end test." Many MiniStack claims are from README matrices that evolved quickly. Where a critical workflow depends on a claim marked `[inference]` or sourced from documentation alone, treat it as unverified until your own tests confirm it.

---

## Confidence Framing

| Claim | Confidence |
|---|---|
| Floci CloudFormation silent stub behavior | **High** — sourced from direct provisioner source analysis |
| MiniStack CloudFormation fail-loud semantics | **Medium** — from documentation, not source analysis |
| Floci DynamoDB GSI/concurrency bugs | **Medium** — from GitHub issues; fix status not confirmed |
| Floci Lambda bugs (#432, #485, #547) | **Medium** — from GitHub issues; fix status not confirmed |
| Floci IAM enforcement capability | **Medium-High** — documented and configuration-confirmed |
| Performance benchmarks (startup, RAM, image) | **Low** — self-reported by respective projects, not independently benchmarked |
| Community metrics (stars, commits, contributors) | **Low-Medium** — snapshot data with methodology caveats |
| MiniStack Cognito/KMS coverage | **Low** — recent documentation claim; not source-confirmed |
| Terraform compat: Floci | **Medium-High** — committed CI test suite observed |
| Terraform compat: MiniStack | **Medium** — documented but no equivalent CI suite observed |

---

*This report synthesizes research conducted April 2026. Given the rapid release cadence of both Floci and MiniStack, specific claims should be re-verified against current releases before any production adoption decision. All performance figures are self-reported by respective projects and should be treated as directional, not benchmarks.*