## Concise Summary

Local AWS emulation matters more in 2026 because LocalStack changed its licensing/distribution model on **March 23, 2026**: it moved to a unified image that requires **`LOCALSTACK_AUTH_TOKEN`** even for free use. The old unauthenticated Community Edition is no longer the normal path, although “sunset” overstates it slightly because a free tier still exists. The cutoff was also **not** simply “3.8 or earlier”: unauthenticated images remained available through releases before **`2026.03.0`**, including some later 4.x versions published before March 23. LocalStack still documented carve-outs such as a **Student plan** and an **open-source license application path**, but the practical effect is unchanged: many teams now want a replacement that still works on **port 4566**, needs no auth token, and fits existing LocalStack-style workflows. That replacement market is led by **Floci** and **MiniStack**; **Moto**, **ElasticMQ**, and **MinIO** remain useful, but mostly in narrower roles.

### What the main contenders are

**Floci** (`floci-io/floci`) is a **Java/Quarkus/GraalVM-native** AWS emulator under **MIT** license, no auth required, centered on **port 4566**. Its architecture is hybrid: many services are **in-process**, while heavier components such as **Lambda, RDS, ElastiCache, MSK, ECS, EKS, OpenSearch, and ECR** run as **real Docker-backed infrastructure**. Its headline metrics are unusually strong: roughly **90 MB image size**, **~13 MiB idle RAM**, and **~24 ms startup**. It supports broad Lambda runtimes through official AWS runtime images and stands out on **IAM enforcement** and **STS coverage**. Floci claims **35 services** and **1,800+ AWS SDK compatibility tests** with **100% pass rate**, but that pass-rate claim is **self-reported**, not independently verified.

**MiniStack** (`ministackorg/ministack`) is a **Python-based** AWS emulator, also **MIT** licensed, also on **port 4566**, installable via **Docker** or **`pip install ministack`**. It uses an **in-process Python gateway** for many services, mostly **in-memory state**, and Docker-backed execution for selected workloads such as **RDS, ElastiCache, ECS**, and some Lambda modes. Its strengths are different: simpler Python-native installation, strong event-pipeline support, **multi-tenant isolation** using **12-digit access-key-derived account IDs**, **Athena via DuckDB** with real SQL execution, and lower-friction migration in some LocalStack-compatible setups. Published resource numbers are about **270 MB image size**, **~21 MB idle RAM** in the README (though the website has shown **~30 MB**), and **startup under 2 seconds**. MiniStack’s docs changed quickly in April 2026, so older service matrices became stale fast: API Gateway REST v1, Cognito, KMS, hostname overrides, and broader persistence were all understated in earlier research.

**Moto** is the oldest and most mature **Python-first AWS mocking library**. Its primary mode is in-process mocking for boto3 tests, with a server mode for non-Python SDKs. It covers **90+ services**, but it is fundamentally a **mocking/test helper**, not a high-fidelity local cloud. It is best for **unit tests**, quick feedback, and Python-first SDK interaction testing. Older claims that Moto “never executes Lambda” are outdated: current docs do support Lambda execution in Docker in some modes. Even so, Moto remains weaker than Floci/MiniStack for **cross-service integration**, **event pipelines**, and **IAM-style enforcement**.

**ElasticMQ** is **SQS-only**. It is extremely lightweight and useful for isolated SQS contract testing. Earlier summaries calling it purely in-memory were incomplete; it supports persistence options too. But it is still a **single-service** tool, not a LocalStack replacement.

**MinIO** is **S3-compatible object storage only**. It is excellent for binary/object workloads and throughput-heavy storage use cases, but it does **not** replace event pipelines or broader AWS service integration.

### Core service coverage and the practical differences

For the mainstream local-AWS/serverless use case—**S3, SQS, SNS, Lambda, DynamoDB, API Gateway, IAM, CloudFormation**—the only serious general-purpose contenders here are **Floci** and **MiniStack**. Both support the core stack, run on **4566**, and go beyond pure mocking into real cross-service workflows.

#### API Gateway
This was one of the biggest corrections versus earlier research. **Floci** clearly documents support for both **API Gateway REST v1** and **HTTP v2**. **MiniStack** was initially reported as **v2-only**, but later official docs listed **REST v1** as well. So the earlier conclusion that MiniStack was a non-starter for REST API Gateway workloads no longer holds. The safer, evidence-aligned comparison is:

- **Floci**: strong, clearly documented **v1 + v2** support.
- **MiniStack**: now also claims **v1 + v2**, but documentation changed quickly enough that teams should verify against current docs or real tests.

MiniStack added an especially important improvement in **v1.3.6 (2026-04-20)**: a **path-based API Gateway data plane** through `localhost:4566`, which avoids the earlier reliance on `*.execute-api.localhost` Host-header routing. That materially reduces friction for browsers, strict HTTP clients, and local testing environments where wildcard localhost DNS is awkward.

#### IAM and STS
This is still one of Floci’s clearest technical advantages.

- **Floci**: configurable **IAM policy enforcement** via `enforcement-enabled: true`; **STS** coverage for **all 7 major operations**.
- **MiniStack**: IAM CRUD support is documented, but earlier evidence did **not** show equivalent policy enforcement; reviewed STS coverage was only **4 operations**.

That makes **Floci more credible for catching authorization bugs locally**: missing permissions, bad role assumptions, and IAM-policy mismatches. Moto’s IAM story is weaker and more limited.

#### Lambda
Both Floci and MiniStack support real Lambda execution, but the details differ.

- **Floci** uses **real Docker AWS Lambda runtime images**, with broad runtime coverage: **Java, Python, Node.js, Ruby, .NET, Go**, and custom runtimes.
- **MiniStack** uses **warm workers** for **Python and Node.js** and Docker/RIE-based execution for other runtimes.

So:

- For **polyglot teams**, especially **Java/.NET/Go-heavy** stacks, **Floci** looks stronger and more transparent.
- For **Python/Node-heavy** teams, **MiniStack’s warm-worker model** can be simpler and fast.

But there are important fidelity caveats. Floci had several significant open Lambda bugs in April 2026:
- **#432**: Lambda containers could not reach S3 via default virtual-hosted-style hostnames; SDK calls timed out unless callers forced path-style access.
- **#485**: timeouts leaked container handles and drained the warm pool, causing escalating cold starts and orphaned Docker processes.
- **#547**: nested Python/Node handler paths such as monorepo-style module paths were rejected at create time, unlike AWS.

MiniStack had fixed the nested-handler class of bug and had an end-to-end **SQS → Lambda event source mapping** test in its suite. For Python/Node specifically, MiniStack’s Lambda behavior looked steadier in reviewed evidence. Floci still retained the broader runtime advantage.

#### DynamoDB and event pipelines
Both Floci and MiniStack are far ahead of Moto, ElasticMQ, and MinIO for actual event-driven integration testing: **S3 → Lambda**, **SNS → SQS**, **SNS → Lambda**, **SQS → Lambda**, **Kinesis → Lambda**, **DynamoDB Streams → Lambda**, and **EventBridge targets** are part of the serious comparison only for Floci/MiniStack.

But the DynamoDB fidelity picture shifted meaningfully. Two critical Floci bugs were identified in late April 2026:
- **#587**: **GSI query pagination** could loop incorrectly when multiple items shared the same index sort key because `LastEvaluatedKey` omitted base-table keys.
- **#571**: **concurrent UpdateItem atomic counters** were not serialized correctly, producing duplicate counter values under concurrency.

Those are not cosmetic issues; they can break application logic. MiniStack’s DynamoDB test suite looked materially deeper in the reviewed evidence and had **no corresponding open DynamoDB bugs** identified at that time. MiniStack also validated details like **ConsumedCapacity** precision, **Streams**, and **PITR defaults**.

So despite Floci’s breadth advantages elsewhere, **MiniStack looked stronger on DynamoDB behavioral fidelity in April 2026**, at least based on the bugs and test evidence reviewed.

#### Cognito, KMS, MSK, EKS, Firehose, advanced platform services
Floci still looks broader and better evidenced for advanced platform services:
- **Cognito**
- **KMS**
- **MSK/Kafka**
- **EKS**
- **Firehose**
- **OpenSearch**
- **ECR**

MiniStack’s later docs contradicted older research by claiming **Cognito** and **KMS**, but Floci still appears broader and better evidenced for these more advanced platform needs.

#### Athena
This is one of MiniStack’s clearest specialized wins.

- **MiniStack**: real Athena-like SQL execution via **DuckDB**
- **Floci**: Athena query lifecycle mocked, but results effectively **empty**

If local workflows depend on **actual Athena queries**, MiniStack has the clear edge.

### CloudFormation, Terraform, CDK, and SAM: the biggest selection risk

The single most important unresolved area for many teams is not service count, but **IaC correctness**.

#### Floci CloudFormation
Direct source analysis of Floci’s `CloudFormationResourceProvisioner.java` was one of the strongest pieces of evidence in the research. It showed that Floci provisions many resource types correctly—S3, SQS, DynamoDB, Lambda, several IAM resources, SSM, KMS, Secrets Manager, nested stacks, ECR, Route53, EventBridge, API Gateway v1/v2—but **unsupported types fall through to a default stub path**.

The critical trap: certain resources, including at least:
- **`AWS::Lambda::EventSourceMapping`**
- **`AWS::Lambda::Permission`**
- **`AWS::SNS::Subscription`**
- **`AWS::StepFunctions::StateMachine`**
- some CloudWatch/Logs/ECS/Cognito-related CFN paths

could end up marked **`CREATE_COMPLETE`** even when no real resource was provisioned. That means a stack can “succeed” while critical event wiring is absent.

For IaC-heavy teams, that is not a minor gap. It means **silent failure semantics**, especially dangerous for **CDK/SAM** users who rely on CloudFormation to wire triggers like **SQS → Lambda** or **API Gateway → Lambda**.

#### MiniStack CloudFormation
MiniStack’s evidence base was weaker in one sense—much of it came from the README/resource matrix rather than direct provisioner source analysis—but it still documented materially broader CloudFormation behavior:
- `AWS::Lambda::Permission`
- `AWS::Lambda::EventSourceMapping`
- more intrinsic functions, including **`Fn::If`**, **`Fn::Equals`**, **`Fn::And`**, **`Fn::Or`**, **`Fn::Not`**, **`Fn::ImportValue`**, **`Fn::Split`**, **`Fn::Select`**, **`Fn::GetAZs`**, **`Fn::Cidr`**
- pseudo-parameters including **`AWS::NoValue`**
- documented failure behavior for unsupported resource types: **`CREATE_FAILED`** rather than silent success

That makes MiniStack **materially safer for CloudFormation-mediated serverless stacks**, even if some of the evidence is still “documented support” rather than independently reproduced runtime proof. The key asymmetry is robust: **Floci had strong evidence of silent stubbing; MiniStack had stronger evidence of explicit support plus fail-loud semantics.**

#### Terraform
Terraform is more favorable to Floci than CDK/SAM because Terraform usually talks directly to AWS APIs rather than going through CloudFormation.

Important corrections from peer review:
- Earlier claims that Floci’s official Terraform path used only `AWS_ENDPOINT_URL` were wrong.
- Floci’s checked-in compat suite used **provider `~> 6.0`** and an explicit **`endpoints {}` block**.
- The safest Terraform guidance is still explicit endpoints, path-style S3, and the usual skip flags:
  - `s3_use_path_style` / `s3_force_path_style`
  - `skip_credentials_validation = true`
  - `skip_requesting_account_id = true`
  - often `skip_metadata_api_check = true`

Floci had a real **compat-terraform** suite covering resources such as:
- **S3**
- **SQS + DLQ + redrive**
- **SNS + SQS subscription**
- **DynamoDB**
- **IAM**
- **SSM**
- **Secrets Manager**
- **RDS**
- **Cognito User Pool**
- **CloudWatch metric alarm**

That gives Floci a real Terraform confidence advantage.

MiniStack documented Terraform compatibility too, and likely supports the same **4566 + explicit endpoints** pattern, but it did **not** have an equivalent committed CI compatibility suite in the reviewed evidence.

#### CDK
This is where the migration experience diverges sharply.

- **Floci** had an official CDK compatibility harness using **`cdklocal`** plus `LOCALSTACK_HOSTNAME` and `EDGE_PORT` in its test setup.
- **MiniStack** documentation was somewhat inconsistent across channels, but plain **`cdk` + `AWS_ENDPOINT_URL`** appears supported, and its README documented a simpler native CDK path.

Floci’s CDK suite did validate some important scenarios, including **DockerImageFunction / ECR / Lambda image** flows. That is a meaningful strength. But the CloudFormation stub risk makes Floci more dangerous for CDK stacks that rely on CFN event wiring.

MiniStack appears more attractive for CDK if your stack uses:
- **Lambda event source mappings**
- **cross-stack exports (`Fn::ImportValue`)**
- **conditional templates**
- a desire to avoid `cdklocal`

But that conclusion should be read as “stronger documented support” more than “fully end-to-end proven.”

#### SAM
The SAM story is still less certain. The reviewed evidence supports these cautious conclusions:
- **Floci**: likely workable for some SAM flows, but CloudFormation stub semantics create risk for event wiring.
- **MiniStack**: more promising for SAM-deployed serverless stacks because `Lambda::Permission` and `Lambda::EventSourceMapping` are documented as supported.

Still, the strongest safe recommendation for either tool remains **validate your actual SAM deploy path** rather than assume parity.

### Migration effort from LocalStack

At the network and SDK layer, both Floci and MiniStack are close to drop-in replacements:
- same **port 4566**
- same endpoint override pattern
- same `--endpoint-url http://localhost:4566`

But “no changes required” is too absolute. Migration usually touches:
- Docker Compose
- health checks
- Testcontainers
- init hooks
- CI service config
- hostname generation
- persistence settings
- IaC wrappers

#### Shared migration changes
Typical changes for both:
- swap the Docker image
- remove **`LOCALSTACK_AUTH_TOKEN`**
- remove **`SERVICES`** if present (it was optional in LocalStack, not required)
- keep Docker socket mounting if you need Docker-backed services

#### Health checks and container networking
- **MiniStack** clearly documents **`/_ministack/health`** and compatibility aliases such as **`/_localstack/health`**. That is a real migration advantage.
- **Floci** health/readiness documentation was weaker and less consistent in reviewed evidence.

For multi-container setups:
- **Floci** documents **`FLOCI_HOSTNAME`**
- **MiniStack** documents **`MINISTACK_HOST`**

So both support hostname tuning; Floci is not uniquely advantaged here.

#### Persistence
Earlier research had unfairly understated MiniStack here.

- **Floci** documents richer storage modes: **memory**, **persistent**, **hybrid**, **wal**
- but official docs were inconsistent about the default
- **MiniStack** documents broader persistence via **`PERSIST_STATE=1`** across services, not just S3

Corrected conclusion:
- **Floci** has richer documented persistence semantics
- **MiniStack** supports broader persistence than earlier summaries claimed
- exact defaults and durability should still be verified

#### Testcontainers
For Java users, this is a real migration friction point.

- **Floci**: official Testcontainers module
- **MiniStack**: official Testcontainers module too

MiniStack’s path appeared simpler in some reports, but the evidence was mixed and sometimes outdated on versions/docs. The practical conclusion is just that **both now have an official Testcontainers story**, which reduces migration pain substantially compared with ad hoc container management.

### CI/CD and Docker-in-Docker constraints

Both Floci and MiniStack work well in CI for **in-process services** and do **not fundamentally require privileged mode** for normal API emulation. But Docker-backed services still bring standard Docker-out-of-Docker constraints:
- Lambda
- RDS
- ElastiCache
- ECS
- MSK
- EKS
- OpenSearch

In those cases, the emulator container usually talks to the host Docker daemon through **`/var/run/docker.sock`**. That is normal Docker-out-of-Docker, not full nested DinD, but portability still depends on your runner configuration.

Important CI nuances:
- In **GitHub Actions**, endpoint choice depends on whether the job runs on the **host** (`localhost`) or **inside a container** (use the service hostname).
- Floci’s docs had at least one real inconsistency: CI docs still showed the older **`hectorvent/floci`** image even after the project announced the move to **`floci/floci`**.
- GitLab guidance for both tools remained weaker.

#### CI footprint
Floci has a clear raw efficiency edge:
- **~24 ms startup**
- **~13 MiB idle**
- **~90 MB image**

MiniStack is still much lighter than LocalStack, but larger:
- **<2 s startup**
- **~21–30 MB idle**
- **~270 MB image**

In real CI cost, the biggest advantage is often **image pull size**, not startup latency alone. So Floci’s strongest CI efficiency edge is usually the **smaller image**, especially on fresh runners.

One operational caveat: MiniStack had an open issue around Docker-mode Lambda execution when MiniStack itself ran inside a container and tried to spawn sibling Lambda containers using host bind mounts. That suggests **more fragility in some containerized CI topologies**, especially when Lambda uses Docker execution rather than warm local workers.

### Community maturity and maintenance risk

The largest shared risk is simply that **both projects are very young**.

As of **April 23, 2026**:
- **Floci**: about **65 days old**
- **MiniStack**: about **30 days old**

Neither has gone through a full year of AWS changes or a post-hype maintenance cycle.

#### Floci community signals
Reported metrics:
- **~4,140 stars**
- **~280 forks**
- **~60 contributors**
- **~380 commits** in ~65 days
- roughly **2–3 releases per week**
- older Docker image with **50,000+ pulls**

Its contribution pattern looked more distributed:
- top author around **29% of commits**
- org-owned repo
- broader contributor spread

That suggests **medium bus-factor risk**, not catastrophic concentration.

#### MiniStack community signals
Reported metrics:
- **~2,186 stars**
- **~36 contributors**
- **~260 commits** in ~30 days
- roughly **1+ release per day**
- combined Docker pulls around **19,500**

Velocity was impressive, but maintainer concentration was much higher:
- primary author around **54% of commits**
- more centralized release control

That implies **higher bus-factor risk** than Floci.

These numbers themselves had some methodology caveats—mixed snapshots, naming inconsistencies, repo lineage confusion—so the durable conclusion is qualitative, not exact: **Floci looks larger and more distributed; MiniStack is growing faster but more centralized; both remain early-stage bets.**

### Decision framework

Choose **Floci** when you prioritize:
- the broadest documented AWS surface area
- stronger **IAM policy enforcement**
- better **STS**
- broader advanced-service coverage (**Cognito, KMS, MSK, EKS, OpenSearch, ECR**)
- broader **polyglot Lambda** support
- smaller CI footprint and faster startup
- a better-validated **Terraform** story

Choose **MiniStack** when you prioritize:
- **Python/Node** ergonomics
- real **Athena SQL** via DuckDB
- stronger local **CloudFormation/CDK/SAM** safety signals
- cleaner health-check compatibility and LocalStack-like migration touches
- built-in **multi-tenant account isolation**
- better evidence for end-to-end event wiring through CFN
- stronger DynamoDB fidelity in the reviewed period

Choose **Moto** when you want:
- fast **Python unit tests**
- in-process AWS mocking
- quick SDK-interaction feedback
- no need for high-fidelity infrastructure behavior

Choose **ElasticMQ** or **MinIO** only when you explicitly want:
- **one service only**
- minimum overhead over broader AWS fidelity

### Biggest unresolved questions

The most important open risks are still architectural:

1. **CloudFormation / IaC depth**  
   Especially for real-world serverless stacks, nested resources, and complex CDK/SAM/Terraform patterns.

2. **IAM correctness in Floci**  
   Floci is the only contender with documented enforcement, but how closely its policy evaluation matches AWS is still not deeply proven.

3. **MiniStack documentation drift**  
   Docs changed quickly enough in April 2026 to invalidate earlier conclusions. Teams should verify against current releases/docs, not stale matrices.

4. **Long-term sustainability**  
   Both tools are too young to judge on durability.

5. **Runtime fidelity gaps vs documented support**  
   README matrices and release notes are useful, but they are weaker than source-confirmed implementation or end-to-end reproduction.

### Bottom line

For teams replacing LocalStack in 2026, **Floci and MiniStack are the only serious general-purpose successors in this comparison**. **Moto, ElasticMQ, and MinIO remain specialized tools**, not broad LocalStack replacements.

The durable comparison is not “which tool has more green boxes,” but:

- **Floci** currently looks stronger on **breadth**, **security/auth fidelity**, **polyglot runtime coverage**, **Terraform validation**, and **CI efficiency**.
- **MiniStack** currently looks stronger on **Athena realism**, **Python/Node ergonomics**, **CloudFormation-mediated event wiring**, **DynamoDB fidelity in the reviewed evidence**, **LocalStack-compatibility conveniences**, and some migration ergonomics.

The most important caution is not vendor service matrices but **workload validation**. Teams should test the **3–5 workflows that matter most**—especially **IaC deployment path, Lambda runtimes, CI topology, event-source wiring, and auth behavior**—before standardizing on either emulator.

## Key Learnings:
1. The strongest stable conclusion is that **Floci and MiniStack are the only broad LocalStack alternatives here with real multi-service/event-driven ambition**; Moto, ElasticMQ, and MinIO remain specialized.
2. **Floci’s main advantages are breadth, IAM/STS/security fidelity, polyglot Lambda support, Terraform validation, and CI footprint**.
3. **MiniStack’s main advantages are Athena realism, Python/Node ergonomics, stronger CloudFormation safety signals, and better reviewed DynamoDB/event-wiring behavior in April 2026**.
4. The biggest selection risks are **IaC depth, event-wiring correctness, CI topology constraints, maturity, and documentation drift**—not just headline service counts.
5. The right selection method is **not** “pick the tool with the bigger matrix”; it is **validate your exact workflows before adopting**.