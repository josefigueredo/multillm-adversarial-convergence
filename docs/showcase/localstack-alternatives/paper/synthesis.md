# Local AWS Service Emulation in 2026: A Decision-Ready Evaluation of LocalStack Alternatives

---

## Abstract

On March 23, 2026, LocalStack consolidated its distribution into a single image requiring a mandatory authentication token, effectively ending the unauthenticated Community Edition workflow that many engineering teams had embedded into local development and CI/CD pipelines. This report evaluates the principal open-source alternatives available to teams facing a decision between adopting LocalStack's paid tier and migrating to a community-maintained emulator. The candidates under primary examination are Floci (`floci-io/floci`) and MiniStack (`ministackorg/ministack`), with Moto, ElasticMQ, and MinIO assessed as specialized narrow-scope tools rather than full replacements. Evidence was gathered from official documentation, checked-in source code, open issue trackers, compatibility test suites, and community activity metrics, supplemented by version-specific release notes through April 2026. Both Floci and MiniStack present credible general-purpose alternatives operating on port 4566, but they differ substantially in architectural approach, service coverage depth, IaC safety semantics, Lambda runtime breadth, and community maturity. Neither tool has yet completed a full year of maintenance. The report presents empirical findings across eight evaluation dimensions and concludes with a single Decision section recommending a workload-specific validation protocol rather than a categorical ranking, given the evidence quality available at this time.

---

## Research Question

This study addresses the following primary question: *For a team currently using LocalStack in local development and CI/CD pipelines, what open-source alternatives exist, and under what conditions does each constitute a viable migration target?* Secondary questions concern the magnitude of migration effort by team archetype, the fidelity of service emulation relative to real AWS behavior, the risk profile of Infrastructure-as-Code toolchains, and the long-term sustainability of candidate projects given their recency.

---

## Methodology

Research proceeded over eight documented iterations, each targeting a distinct evaluation dimension: AWS service coverage, community activity, migration effort, CI/CD integration, CloudFormation and IaC compatibility, MiniStack provisioner behavior, migration effort stratified by team profile, and API compatibility and behavioral fidelity. Evidence collection methods included direct review of checked-in source files (notably `CloudFormationResourceProvisioner.java` for Floci), analysis of open GitHub issues on both primary repositories, review of official documentation snapshots, inspection of committed compatibility test suites (`compat-terraform`, `compat-cdk` subdirectories), and community metric sampling (stars, forks, contributor counts, commit frequency, Docker pull counts) collected around April 23, 2026.

Where official documentation contradicted prior research summaries—as occurred with MiniStack's API Gateway and Cognito coverage in mid-April 2026—the most recent authoritative source was treated as superseding the earlier claim, and the contradiction is explicitly noted in the relevant finding. Claims that could not be sourced to a directly observed artifact are marked `[unverified]` or `[inference]`.

Evidence quality is deliberately heterogeneous. Source-code analysis provides the strongest signal; README matrices and release-note claims provide weaker signal; community metrics provide directional signal only. This hierarchy is maintained throughout the findings and is revisited in the Limitations section.

---

## Findings

### 4.1 LocalStack Licensing Context

LocalStack's distribution model changed materially on March 23, 2026. The project moved to a unified image that requires a valid `LOCALSTACK_AUTH_TOKEN` environment variable at startup. The version boundary is not simply "3.8 or earlier"; unauthenticated images remained available through certain 4.x releases published prior to the March 23 cutoff, specifically those predating build `2026.03.0`. A free tier, a Student plan, and an open-source license application path were documented by LocalStack at the time of the change, but the practical effect is that teams embedded in automation pipelines—where token injection is non-trivial—face immediate friction. The older unauthenticated Community Edition images remain available on Docker Hub by digest but are not the supported path going forward.

The commercial tier (LocalStack Pro and Enterprise) continues to offer the broadest AWS surface area of any local emulator, mature Testcontainers integration, and multi-year production deployment history. The marginal cost question reduces to whether the service coverage and behavioral fidelity premium justifies the subscription cost, given that credible open-source alternatives now exist for the first time.

### 4.2 Candidate Overview

**Floci** (`floci-io/floci`) is a Java/Quarkus/GraalVM-native AWS emulator, released under the MIT license, with no authentication requirement. It operates on port 4566 and uses a hybrid architecture: many services run in-process within the JVM image, while heavier infrastructure components—Lambda, RDS, ElastiCache, MSK, ECS, EKS, OpenSearch, and ECR—run as real Docker-backed processes spawned by the emulator container. [Unverified self-reported] claimed figures include an image size of approximately 90 MB, idle RAM of approximately 13 MiB, and startup latency of approximately 24 ms. The project [unverified] claims 35 services and a 100% pass rate across 1,800+ AWS SDK compatibility tests. The repository was approximately 65 days old as of April 23, 2026.

**MiniStack** (`ministackorg/ministack`) is a Python-based AWS emulator, also MIT licensed and operating on port 4566. It is installable via Docker or via `pip install ministack`. Its architecture is also hybrid: an in-process Python gateway handles many services with mostly in-memory state, while Docker-backed execution serves selected workloads including RDS, ElastiCache, ECS, and certain Lambda execution modes. [Unverified] published resource figures are approximately 270 MB image size, 21–30 MB idle RAM, and startup under 2 seconds. MiniStack's documentation changed substantially and rapidly during April 2026, invalidating several earlier service-coverage assessments. The repository was approximately 30 days old as of April 23, 2026.

**Moto** is a mature Python-first AWS mocking library with in-process primary mode and a server mode for non-Python SDKs. It covers 90+ services but is architecturally a mocking and test-helper tool, not a high-fidelity local cloud. It remains the strongest available choice for Python unit tests requiring rapid feedback and in-process SDK interaction, but it is substantially weaker than Floci or MiniStack for cross-service integration, event pipelines, and IAM-style enforcement.

**ElasticMQ** and **MinIO** are single-service tools—SQS and S3-compatible object storage, respectively—and are not general LocalStack replacements. They are relevant only when a team's requirements are scoped to one of those services.

### 4.3 AWS Service Coverage

For the mainstream serverless development profile—S3, SQS, SNS, Lambda, DynamoDB, API Gateway, IAM, and CloudFormation—Floci and MiniStack are the only candidates with multi-service and event-driven ambition. Moto, ElasticMQ, and MinIO do not constitute viable general replacements for this profile.

**API Gateway** coverage was one of the most significant corrections in the research timeline. Floci clearly documents support for both API Gateway REST v1 and HTTP v2. MiniStack was initially assessed as v2-only; subsequent official documentation listed REST v1 as well. The earlier conclusion that MiniStack was a non-starter for REST-type API Gateway workloads no longer holds. Additionally, MiniStack v1.3.6 (released April 20, 2026) introduced a path-based API Gateway data plane through `localhost:4566`, eliminating the earlier reliance on wildcard `*.execute-api.localhost` Host-header routing that many HTTP clients handle poorly. Floci's documented v1/v2 support remains the stronger and more consistently evidenced position, but the gap closed materially.

**IAM and STS** remain Floci's clearest technical advantage. Floci documents configurable IAM policy enforcement via an `enforcement-enabled: true` configuration flag, and its STS coverage extends to all seven major operations. MiniStack documents IAM CRUD support, but the reviewed evidence did not surface equivalent policy enforcement semantics; STS coverage extended to four operations in the reviewed period. This difference is not cosmetic: IAM enforcement at the emulator layer is the primary mechanism by which teams can catch missing permissions, bad role assumptions, and policy mismatches before deployment.

**Lambda runtime coverage** differs by architectural approach. Floci uses real Docker AWS Lambda runtime images and documents broad runtime coverage: Java, Python, Node.js, Ruby, .NET, Go, and custom runtimes. MiniStack uses warm workers for Python and Node.js and Docker/RIE-based execution for other runtimes. For polyglot teams with Go, Java, or .NET Lambda functions, Floci's approach is more transparent and consistent. However, Floci carried several significant open Lambda defects during the research period: [GitHub issue floci-io/floci#432] documented Lambda containers failing to reach S3 via default virtual-hosted-style hostnames (SDK calls timed out unless path-style access was forced); [GitHub issue floci-io/floci#485] documented timeout-induced container handle leaks that exhausted the warm pool and left orphaned Docker processes; [GitHub issue floci-io/floci#547] documented rejection of nested module handler paths common in monorepo structures. MiniStack had resolved the nested-handler class of defect and had a committed end-to-end SQS → Lambda event source mapping test. For Python and Node.js workloads specifically, MiniStack's Lambda behavior appeared steadier in the reviewed evidence.

**DynamoDB fidelity** shifted the balance toward MiniStack. Two critical Floci defects were identified in late April 2026: [GitHub issue floci-io/floci#587] documented incorrect GSI query pagination when multiple items shared the same index sort key, producing loop behavior because `LastEvaluatedKey` omitted base-table keys; [GitHub issue floci-io/floci#571] documented non-serialized concurrent `UpdateItem` atomic counter operations that produced duplicate values under concurrency. These are not superficial compatibility gaps—they are behavioral differences that can corrupt application logic. MiniStack's DynamoDB test suite was observed to be materially deeper in the reviewed evidence, validating `ConsumedCapacity` precision, Streams integration, and PITR defaults, with no corresponding open DynamoDB defects identified at that time.

**Athena** is one of MiniStack's clearest specialized advantages. MiniStack provides real Athena-like SQL query execution backed by DuckDB, returning actual result sets. Floci's Athena implementation mocks the query lifecycle but returns effectively empty results. For teams whose local development includes Athena queries over S3 datasets, MiniStack is the only general-purpose emulator in this comparison with meaningful Athena support.

**Advanced platform services**—Cognito, KMS, MSK/Kafka, EKS, Firehose, OpenSearch, ECR—remain better evidenced on Floci. MiniStack's later documentation contradicted some earlier research by claiming Cognito and KMS coverage, but Floci's breadth and consistency of evidence was stronger for these services at the time of writing.

### 4.4 Infrastructure-as-Code Compatibility

CloudFormation compatibility is the highest-risk dimension for teams whose workflows involve CDK, SAM, or Terraform-managed stacks. The asymmetry between Floci and MiniStack here is architecturally significant.

**Floci CloudFormation** was analyzed directly through `CloudFormationResourceProvisioner.java`. The provisioner handles a broad set of resource types correctly: S3, SQS, DynamoDB, Lambda, IAM roles and policies, SSM Parameter Store, KMS keys, Secrets Manager secrets, nested stacks, ECR repositories, Route53 records, EventBridge rules, and API Gateway v1 and v2 resources. However, unsupported resource types fall through to a default stub path. The critical defect is the semantics of that stub: resources including at minimum `AWS::Lambda::EventSourceMapping`, `AWS::Lambda::Permission`, `AWS::SNS::Subscription`, and `AWS::StepFunctions::StateMachine` were observed to be marked `CREATE_COMPLETE` without any real resource being provisioned. A CloudFormation stack can report overall success while event trigger wiring is absent. For CDK and SAM users who depend on CloudFormation to wire SQS → Lambda event source mappings or API Gateway → Lambda integrations, this constitutes silent failure semantics—a trap that is unlikely to surface until deployment to a real environment.

**MiniStack CloudFormation** was assessed primarily through documentation and the published resource matrix, a weaker evidence source than direct source analysis. Nonetheless, MiniStack documented materially broader CloudFormation behavior, including `AWS::Lambda::Permission`, `AWS::Lambda::EventSourceMapping`, a wider set of intrinsic functions (`Fn::If`, `Fn::Equals`, `Fn::And`, `Fn::Or`, `Fn::Not`, `Fn::ImportValue`, `Fn::Split`, `Fn::Select`, `Fn::GetAZs`, `Fn::Cidr`), pseudo-parameter support including `AWS::NoValue`, and crucially, explicit `CREATE_FAILED` semantics for unsupported resource types rather than silent success. The fail-loud behavior is architecturally safer for IaC-heavy teams: a visible failure is diagnosable; a silently successful but incomplete stack is not.

**Terraform** compatibility favors Floci. Because Terraform interacts directly with AWS service APIs rather than going through CloudFormation, the stub-resource problem that afflicts CDK and SAM stacks does not apply in the same way. Floci maintains a committed `compat-terraform` compatibility suite covering S3, SQS with dead-letter queues and redrive policies, SNS with SQS subscriptions, DynamoDB, IAM, SSM, Secrets Manager, RDS, Cognito User Pool, and CloudWatch metric alarms. The correct Terraform provider configuration requires an explicit `endpoints {}` block (provider version `~> 6.0`), `s3_use_path_style` (or `s3_force_path_style` for older providers), and the standard skip flags: `skip_credentials_validation = true`, `skip_requesting_account_id = true`, and typically `skip_metadata_api_check = true`. MiniStack documents Terraform compatibility and likely supports the same endpoint configuration pattern, but no equivalent committed CI compatibility suite was observed in the reviewed evidence.

**CDK** presents a more nuanced picture. Floci maintains an official CDK compatibility harness using `cdklocal` with `LOCALSTACK_HOSTNAME` and `EDGE_PORT` environment variables, and its test suite validates DockerImageFunction/ECR/Lambda image deployments. MiniStack documents a native CDK path using plain `cdk` with `AWS_ENDPOINT_URL`, which reduces toolchain dependency. However, Floci's CloudFormation stub semantics create meaningful risk for CDK stacks that rely on CloudFormation to wire event sources. MiniStack's stronger documented support for `Lambda::EventSourceMapping`, `Lambda::Permission`, `Fn::ImportValue`, and conditional constructs makes it the safer apparent choice for CDK stacks using those patterns—though this conclusion rests more on documented support than independently reproduced runtime evidence.

**SAM** remains the least-verified dimension. Floci is likely workable for simple SAM deployments but carries the CloudFormation stub risk for event-wired functions. MiniStack is more promising for SAM-deployed serverless stacks given its documented support for the resource types that SAM uses to wire Lambda triggers. Neither conclusion should be treated as a strong guarantee without direct validation.

### 4.5 Migration Effort

At the network and SDK layer, both Floci and MiniStack are close to drop-in LocalStack replacements: same port 4566, same `--endpoint-url http://localhost:4566` pattern for AWS CLI and SDK calls, same Docker-based deployment model. The mechanical migration is achievable, but "no changes required" overstates the practical experience.

**Changes common to both migrations** include: replacing the LocalStack Docker image with the chosen alternative; removing `LOCALSTACK_AUTH_TOKEN` from environment configuration; optionally removing the `SERVICES` environment variable (which was optional in LocalStack and is not a required construct in either alternative); and retaining Docker socket mounting for Docker-backed services.

**Health checks** differ and represent a concrete migration touch point. MiniStack documents `/_ministack/health` and maintains a `/_localstack/health` compatibility alias, which is a direct migration convenience for teams whose health check configuration references LocalStack paths. Floci's health and readiness endpoint documentation was less consistent in the reviewed period; teams should verify the current endpoint before automating readiness probes.

**Container hostname configuration** for multi-container Docker Compose networks requires environment variable changes: `FLOCI_HOSTNAME` for Floci and `MINISTACK_HOST` for MiniStack, both analogous to LocalStack's `LOCALSTACK_HOSTNAME`.

**Persistence** handling requires attention in both cases. Floci documents richer persistence modes (memory, persistent, hybrid, and WAL-based) but documentation was inconsistent about defaults. MiniStack supports broader persistence via `PERSIST_STATE=1` across multiple service categories—a broader claim than earlier research credited. Teams relying on LocalStack's persistence features should verify the current default behavior and configure it explicitly rather than relying on assumed defaults.

**Testcontainers** users will find that both tools now publish official Testcontainers modules, substantially reducing migration friction for Java-based integration test suites. The practical experience varied in some reviewed reports, and version-specific documentation should be consulted for current module coordinates.

**Migration effort estimates** by team profile are necessarily approximate:

- *Serverless teams using S3, SQS, SNS, Lambda, and DynamoDB via SDK calls only, without IaC automation:* Estimated 1–2 days for either migration target. Most changes are confined to Docker Compose configuration and environment variable substitution.

- *CDK or SAM teams with event-source-wired functions:* Estimated 3–5 days for either migration, with additional time required for validating CloudFormation-mediated event wiring. Floci carries higher retest risk due to silent stub semantics.

- *Terraform teams:* Estimated 1–3 days for Floci (aided by the committed compatibility suite as a reference); estimated 2–4 days for MiniStack (no equivalent reference suite available in the reviewed evidence).

- *Polyglot Lambda teams (Go, Java, .NET):* Estimated additional 1–2 days for runtime-specific Lambda validation regardless of chosen emulator.

- *Teams with Athena-dependent workflows:* MiniStack is the viable path; migration effort for Athena-specific code is concentrated on query execution semantics rather than endpoint configuration.

### 4.6 CI/CD Integration

Both tools operate acceptably in standard CI/CD topologies for in-process emulated services and do not fundamentally require privileged container execution for normal API emulation. Docker-backed services—Lambda, RDS, ElastiCache, ECS, MSK, EKS, OpenSearch—introduce the standard Docker-out-of-Docker dependency: the emulator container requires access to the host Docker daemon, typically via `/var/run/docker.sock` mounting. This is not full nested Docker-in-Docker, but it does depend on runner configuration.

In GitHub Actions, the correct emulator hostname depends on whether the job step runs directly on the runner host (use `localhost:4566`) or inside a container (use the service container's alias name and the service-level port). Floci's CI documentation contained at least one observed inconsistency: CI configuration examples in the reviewed period still referenced the older `hectorvent/floci` image name after the project announced migration to `floci/floci`. Teams configuring CI from Floci's documentation should verify the current canonical image name.

**CI footprint** is one of Floci's clearer advantages. Its [unverified self-reported] figures of approximately 24 ms startup, approximately 13 MiB idle RAM, and approximately 90 MB image are substantially smaller than MiniStack's [unverified] approximately 270 MB image and under-2-second startup. In practice, the most material CI cost difference is usually image pull time and size on fresh runners rather than startup latency after pull. An approximately 180 MB image size difference is meaningful in pull-heavy CI environments.

MiniStack exhibited an open issue around Docker-mode Lambda execution when MiniStack itself ran inside a container and attempted to spawn sibling Lambda containers using host bind mounts. This implies additional fragility in containerized CI topologies where Lambda uses Docker execution rather than warm in-process workers.

### 4.7 Community Maturity and Sustainability

Both tools were in early-stage development as of the research period. This is the single largest shared risk in any adoption decision.

**Floci** community metrics as of approximately April 23, 2026: [unverified] approximately 4,140 GitHub stars, approximately 280 forks, approximately 60 contributors, approximately 380 commits over approximately 65 days of existence, roughly 2–3 releases per week, and approximately 50,000+ Docker pulls on the older image. The commit distribution showed the top contributor accounting for approximately 29% of commits across an organization-owned repository with broader contributor spread, suggesting medium rather than high bus-factor risk.

**MiniStack** community metrics as of approximately April 23, 2026: [unverified] approximately 2,186 GitHub stars, approximately 36 contributors, approximately 260 commits over approximately 30 days of existence, roughly one or more releases per day, and approximately 19,500 combined Docker pulls. The primary author accounted for approximately 54% of commits, indicating higher maintainer concentration and therefore higher bus-factor risk than Floci at this snapshot.

These metrics carry their own caveats. Sampling methodology varied across the research iterations, repository naming changed during the period (particularly for Floci's image name transition), and GitHub stars are susceptible to single-event spikes around launch announcements. The directional conclusion is robust even if the precise figures are approximate: Floci is larger, more distributed, and slightly more mature by elapsed time; MiniStack is growing faster on an absolute commit basis but with greater centralization. Neither project has a track record beyond the lifecycle of a single AWS service API change cycle, which makes long-term sustainability judgment premature.

---

## Discussion

The evidence assembled across these eight evaluation dimensions supports a picture that is more nuanced than a simple ranking.

Floci's core technical proposition is architectural coherence. Its JVM/GraalVM-native image is optimized for minimal footprint while delegating computationally intensive workloads to real Docker-backed processes, an approach that is transparent and consistent. Its IAM policy enforcement capability is unique among the alternatives examined and represents a genuine security fidelity advantage. Its Terraform compatibility suite provides an unusual degree of confidence for Terraform-heavy teams. Its broader support for non-Python, non-Node Lambda runtimes makes it more appropriate for polyglot organizations.

The CloudFormation stub semantics, however, are a serious structural concern for CDK and SAM teams. Silent CREATE_COMPLETE responses for unprovisioned event-source mapping and trigger resources mean that local stack deployments can succeed while the application is silently broken. This is not a minor omission—it is an architectural choice with real workflow consequences. Teams that have heavily invested in CDK or SAM as their local deployment mechanism must treat this as the primary migration risk for Floci.

MiniStack's core proposition is different: it prioritizes LocalStack-compatible migration ergonomics, stronger CloudFormation safety semantics for serverless event wiring, and Python/Node ecosystem coherence. Its fail-loud CloudFormation behavior, its LocalStack health endpoint alias, and its path-based API Gateway data plane (introduced in v1.3.6) reflect an explicit design intent to lower migration friction and surface errors visibly. Its Athena-via-DuckDB implementation fills a niche that no other emulator in this comparison addresses.

The documentation velocity of MiniStack is simultaneously a signal of active development and a source of research reliability risk. Multiple service coverage assessments were invalidated within days by documentation updates during the April 2026 research period. Teams should calibrate their decisions against current documentation and their own verification tests, not against any static matrix produced at a specific point in time.

A dimension that warrants particular attention is the IAM enforcement asymmetry. The ability to validate authorization failures locally—not merely that API calls reach the correct endpoints, but that they succeed or fail based on the correct policy evaluation—is a meaningful quality gate for teams building multi-account, multi-role, or fine-grained permission architectures. Floci is currently the only tool in this comparison with documented enforcement semantics. Whether its policy evaluation behavior accurately matches AWS's IAM policy evaluation algorithm is a deeper question that the available evidence does not resolve.

---

## Limitations

**Evidence quality is heterogeneous across candidates.** Floci's CloudFormation behavior was assessed through direct source-code analysis of `CloudFormationResourceProvisioner.java`, which provides strong signal. MiniStack's CloudFormation behavior was assessed primarily through documentation and the published resource matrix, which is a weaker evidence source. Conclusions drawn comparatively across these two evidence types should be treated with appropriate asymmetry.

**Documentation drift is a specific limitation for MiniStack.** Multiple claims in earlier research iterations were invalidated within the same research period by documentation updates. The conclusion about API Gateway coverage and Cognito/KMS support changed materially between research iterations in April 2026. Any matrix or comparison document produced from this research, including the present one, may be partially outdated by the time it is read.

**Community metrics are directional, not precise.** GitHub star counts, fork counts, and Docker pull counts are subject to single-event inflation and sampling timing effects. The observed figures were collected across a narrow window and from inconsistent sampling snapshots. They establish directional rather than definitive relative standing.

**The pass-rate claim from Floci is self-reported.** The statement that Floci achieves 100% pass rate across 1,800+ AWS SDK compatibility tests originates from Floci's own documentation. Independent reproduction of this claim was not part of the research methodology and its accuracy cannot be assessed here.

**Both tools are extremely young.** The research was conducted when Floci was approximately 65 days old and MiniStack approximately 30 days old. Neither has undergone a full AWS API change cycle, a major version deprecation event, a community dispute, or any of the long-term maintenance challenges that reveal project health over time. Sustainability assessments are necessarily speculative.

**CI/CD behavior was not validated through independent pipeline execution.** CI configuration was assessed through documentation and official examples, not through execution on real runners. The MiniStack Docker-mode Lambda fragility finding came from an open issue report, not independent reproduction.

**Lambda runtime fidelity claims are mixed in evidence quality.** Open GitHub issues provide strong evidence for specific defects in Floci's Lambda implementation. The absence of corresponding open issues for MiniStack is negative evidence, not proof of correctness.

**LocalStack's current free-tier terms were not independently verified** beyond the reported March 23, 2026 change summary. The exact scope of the Student plan, the open-source license path, and any subsequent modifications were not analyzed in depth.

---

## Decision

The evidence does not support a categorical recommendation of one tool over the other for all teams. The appropriate selection depends on the specific service profile, IaC toolchain, Lambda runtime mix, and risk tolerance of the adopting team.

Teams whose local development workflow consists primarily of SDK-level calls against S3, SQS, SNS, DynamoDB, and Lambda—without relying on CloudFormation, CDK, or SAM to wire event sources—will find either tool viable. For these teams, the operative differentiation factors are Lambda runtime mix (favoring Floci for non-Python/Node runtimes), DynamoDB concurrency correctness (currently favoring MiniStack based on the reviewed defect record), CI image size (favoring Floci), and Athena dependency (requiring MiniStack).

Teams whose infrastructure is delivered via CDK or SAM, or who rely on CloudFormation event source mapping resources to wire Lambda triggers, should treat Floci's silent-stub CloudFormation semantics as a critical risk. The evidence that `CREATE_COMPLETE` can be returned for unprovisioned event-wiring resources—observed directly in the provisioner source—is the most consequential architectural finding in this report. For these teams, MiniStack's documented fail-loud semantics and its explicit support for `AWS::Lambda::EventSourceMapping` and `AWS::Lambda::Permission` make it the safer starting point, with the caveat that "documented support" remains a weaker claim than independently verified runtime behavior.

Teams whose IaC is managed through Terraform and who require cross-service integration testing with IAM enforcement are best served by Floci. The committed compatibility suite provides real confidence that foundational Terraform workflows function correctly, and the IAM policy enforcement capability is without equivalent in any other open-source alternative reviewed here.

Teams for whom long-term maintenance risk is the primary concern should note that neither tool is a safe long-term bet based solely on current evidence—both are too young. The risk-management response in this scenario is to preserve optionality: implement endpoint configuration at an abstraction layer that allows switching emulators without application code changes, and monitor project health at 90-day intervals over the following year.

For all teams, the operationally correct approach before any migration commitment is direct validation of the three to five workflows that matter most: the IaC deployment path (not just API calls), the specific Lambda runtimes in use, the CI topology including whether Lambda uses Docker execution, any event-source mapping chains, and any IAM enforcement requirements. Service count matrices, including any produced in this report, should be treated as initial orientation rather than migration guarantees.

Continuing to pay for LocalStack Pro is rationally defensible for teams that require broad advanced-service coverage (Cognito, MSK, EKS, OpenSearch at production fidelity), established Testcontainers integration, long-term vendor accountability, and a mature CI/CD track record. The open-source alternatives are real competitors, not toy projects, but they have not yet demonstrated multi-year reliability, and the cost of an emulator failure late in a CI pipeline is not zero.

---

## References

The following sources were consulted during research. Where a source was observed directly, it is cited as such. Where a source is referenced from the knowledge base summary rather than independently accessed, it is noted accordingly.

1. **Floci repository** — `https://github.com/floci-io/floci` — Primary repository for the Floci AWS emulator; source of documentation, release notes, and compatibility suites.
2. **Floci GitHub issue #432** — `https://github.com/floci-io/floci/issues/432` — Lambda container inability to reach S3 via virtual-hosted-style hostnames.
3. **Floci GitHub issue #485** — `https://github.com/floci-io/floci/issues/485` — Timeout-induced Lambda container handle leaks and warm-pool exhaustion.
4. **Floci GitHub issue #547** — `https://github.com/floci-io/floci/issues/547` — Rejection of nested module handler paths at Lambda function creation.
5. **Floci GitHub issue #571** — `https://github.com/floci-io/floci/issues/571` — Non-serialized concurrent `UpdateItem` atomic counter operations producing duplicate values.
6. **Floci GitHub issue #587** — `https://github.com/floci-io/floci/issues/587` — Incorrect GSI query pagination when items share the same index sort key.
7. **MiniStack repository** — `https://github.com/ministackorg/ministack` — Primary repository for the MiniStack AWS emulator; source of documentation, resource matrices, and release notes.
8. **MiniStack release v1.3.6** — `https://github.com/ministackorg/ministack/releases/tag/v1.3.6` — Release introducing path-based API Gateway data plane through `localhost:4566`; published April 20, 2026.
9. **LocalStack licensing change announcement** — `https://discuss.localstack.cloud` — [Referenced from knowledge base; not independently verified at the primary URL] — Official communication regarding the March 23, 2026 transition to unified image requiring `LOCALSTACK_AUTH_TOKEN`.
10. **Moto documentation** — `https://docs.getmoto.org` — Official documentation for the Moto Python AWS mocking library.
11. **ElasticMQ repository** — `https://github.com/softwaremill/elasticmq` — SQS-compatible message queue emulator.
12. **MinIO documentation** — `https://min.io/docs` — S3-compatible object storage documentation.
13. **AWS Testcontainers modules** — `https://testcontainers.com/modules/` — Source for Testcontainers module availability for Floci and MiniStack.
14. **CloudFormationResourceProvisioner.java** — Observed directly within the `floci-io/floci` repository source tree; primary evidence source for CloudFormation stub-resource semantics.