# Iteration 006 — MiniStack CloudFormation provisioner source analysis and v1.3.6 parity verification

**Status:** keep  
**Scores:** coverage=76.2, quality=62.5, total=68.0  
**Timestamp:** 2026-04-24T01:47:37.519196+00:00  

---

---

## Findings

### 1. MiniStack CloudFormation Provisioner: `Lambda::EventSourceMapping` and `Lambda::Permission`

Both resource types are **explicitly supported** in MiniStack's CloudFormation provisioner.

From the [MiniStack README](https://github.com/ministackorg/ministack/blob/main/README.md) CloudFormation section (current `main` branch, confirmed 2026-04-23):

| Resource Type | Ref Returns | GetAtt |
|---|---|---|
| `AWS::Lambda::Permission` | Statement ID | — |
| `AWS::Lambda::EventSourceMapping` | UUID | — |

This directly resolves the gap confirmed in Floci's `CloudFormationResourceProvisioner.java`. In Floci, both types fall to the default stub and succeed silently. In MiniStack they invoke the real Lambda `AddPermission` and `CreateEventSourceMapping` API calls — the same operations that Floci *does* support through its service API.

**Critical failure-semantics asymmetry**: MiniStack's provisioner explicitly states in the README: *"Unsupported resource types fail with `CREATE_FAILED` (or `ROLLBACK_COMPLETE` if rollback is enabled), so templates with unsupported types won't silently succeed."* Floci does the opposite — unsupported types are silently stubbed with `CREATE_COMPLETE`. This is not just a CFN depth difference; it is a qualitative correctness difference with direct IaC safety implications. A CloudFormation template that references an unsupported type will loudly fail on MiniStack but silently mislead on Floci.

**Additional Lambda CFN resource types in MiniStack** beyond Floci's scope: `AWS::Lambda::Version`, `AWS::Lambda::Alias`, `AWS::Lambda::LayerVersion` — none of which appear in Floci's provisioner switch statement per prior analysis.

**Source note**: MiniStack's CloudFormation provisioner is implemented as `ministack/services/cloudformation.py` (per the README Contributing section: "each service is a single self-contained Python file in `ministack/services/`"). The file is not directly accessible without authentication to the GitHub raw API, but the README CloudFormation table is explicitly marked as the authoritative list of provisioned resource types, and it is the document used to evidence the supported resource matrix. **Confidence: High** (README is the primary specification document; the resource type list in the README is structurally consistent with MiniStack's architectural documentation pattern, used for all other services in the same format).

---

### 2. Intrinsic Function Coverage: Symmetric Source-Level Comparison

**MiniStack intrinsic functions** (from [README CloudFormation section](https://github.com/ministackorg/ministack/blob/main/README.md)):

| Category | Functions |
|---|---|
| Value resolution | `Ref`, `Fn::GetAtt`, `Fn::Sub` (both forms: `"Sub"` string + `"Sub"` + dict), `Fn::FindInMap` |
| String/array ops | `Fn::Join`, `Fn::Select`, `Fn::Split`, `Fn::Base64` |
| Conditional logic | `Fn::If`, `Fn::Equals`, `Fn::And`, `Fn::Or`, `Fn::Not` |
| Cross-stack | `Fn::ImportValue` |
| Network/utility | `Fn::GetAZs`, `Fn::Cidr` |

**Floci intrinsic functions** (from prior source analysis of `CloudFormationResourceProvisioner.java` — cited in prior research iteration):
`Ref`, `Fn::GetAtt`, `Fn::Sub`, `Fn::Join`, `Fn::FindInMap`, `Fn::Base64` (6 functions confirmed; `Fn::Select` listed in the prior summary comparison table but not confirmed from the Java source itself — peer review issue #8 flags this list as not properly sourced)

**Symmetric comparison**:

| Intrinsic Function | Floci | MiniStack | Notes |
|---|---|---|---|
| `Ref` | ✅ confirmed source | ✅ README | — |
| `Fn::GetAtt` | ✅ confirmed source | ✅ README | — |
| `Fn::Sub` (string form) | ✅ confirmed source | ✅ README | Both forms |
| `Fn::Sub` (string+dict form) | ✅ confirmed source | ✅ README | — |
| `Fn::Join` | ✅ confirmed source | ✅ README | — |
| `Fn::FindInMap` | ✅ confirmed source | ✅ README | — |
| `Fn::Base64` | ✅ confirmed source | ✅ README | — |
| `Fn::Select` | ⚠️ in summary, not sourced | ✅ README | Peer review flagged Floci unsourced |
| `Fn::Split` | ❌ not listed for Floci | ✅ README | MiniStack advantage |
| `Fn::If` | ❌ not listed for Floci | ✅ README | MiniStack advantage |
| `Fn::Equals` | ❌ not listed for Floci | ✅ README | MiniStack advantage |
| `Fn::And` | ❌ not listed for Floci | ✅ README | MiniStack advantage |
| `Fn::Or` | ❌ not listed for Floci | ✅ README | MiniStack advantage |
| `Fn::Not` | ❌ not listed for Floci | ✅ README | MiniStack advantage |
| `Fn::ImportValue` | ❌ not listed for Floci | ✅ README | Cross-stack exports; MiniStack advantage |
| `Fn::GetAZs` | ❌ not listed for Floci | ✅ README | AZ resolution; MiniStack advantage |
| `Fn::Cidr` | ❌ not listed for Floci | ✅ README | Network CIDR splitting; MiniStack advantage |

**Key finding**: MiniStack's intrinsic function support is substantially broader. The full conditional function set (`Fn::If`, `Fn::Equals`, `Fn::And`, `Fn::Or`, `Fn::Not`) is present in MiniStack and absent from Floci's documented set. This matters for real-world templates: CDK and SAM frequently emit conditional logic (`Fn::If` with `AWS::NoValue`) to handle optional parameters and environment-dependent resource properties. A Floci CloudFormation engine that lacks `Fn::If` will fail to resolve conditional values correctly.

**Caveat on Floci**: The peer review flagged that the Floci intrinsic function list was asserted without clear cited backing from the Java source. It may be that Floci implements more functions than listed. The absence of evidence is not conclusive. Confidence for "Floci does NOT support Fn::If" is **Medium** — based on the fact it is absent from the prior source listing, but the prior listing has an auditability gap.

**MiniStack also documents**:
- `Conditions` block: `Fn::Equals`, `Fn::And`, `Fn::Or`, `Fn::Not` — conditional resource creation
- `AWS::NoValue` pseudo-parameter
- All 7 CFN pseudo-parameters: `AWS::StackName`, `AWS::StackId`, `AWS::Region`, `AWS::AccountId`, `AWS::URLSuffix`, `AWS::Partition`, `AWS::NoValue`

---

### 3. MiniStack v1.3.6 (2026-04-20): Full Change Analysis

The peer review correctly identified that framing v1.3.6 as "CORS fix" understated the release. The complete change log from the [GitHub release page](https://github.com/ministackorg/ministack/releases/tag/v1.3.6):

#### Added (3 new features)

**1. API Gateway path-based data plane** (major feature)

REST + HTTP + WebSocket APIs are now reachable without `*.execute-api.localhost` Host header overrides via:
- `http://localhost:4566/_aws/execute-api/{apiId}/{stage}/{path}` — works for v1 REST, v2 HTTP, and v2 WebSocket
- `http://localhost:4566/restapis/{apiId}/{stage}/_user_request_/{path}` — LocalStack-legacy v1 path

**Why this matters for CDK/IaC**: Before v1.3.6, API Gateway data-plane testing required that the HTTP client (test framework, browser, load-tester) resolve `*.execute-api.localhost` DNS and set a Host header accordingly. On macOS, `*.localhost` subdomain DNS resolution does not work in browsers or many strict HTTP clients. After v1.3.6, any client can reach any API using the path-based form through the main `localhost:4566` port without DNS tricks. This significantly reduces local development friction for CDK stacks that include API Gateway.

**2. Custom/predictable API Gateway IDs** (`ms-custom-id` tag)

`aws_apigatewayv2_api` and `aws_apigateway_rest_api` honour an `ms-custom-id` tag on `CreateApi`/`CreateRestApi` and pin the generated `apiId`/REST API id to the tag value. Duplicates in the same account return `ConflictException` (409). The LocalStack `ls-custom-id` tag is **explicitly rejected** with a `BadRequestException` (400) pointing callers at the ministack-native key.

**Why this matters**: Terraform/CDK-managed API Gateway IDs change across applies when the resource is destroyed and recreated (e.g., after `ministack reset`). Stable IDs allow hardcoding the invoke URL in environment-specific configs without modifying the IaC.

**3. Cognito `AWS::Cognito::UserPoolClient` CFN `GenerateSecret`**

CloudFormation-provisioned Cognito user pool clients now generate a client secret when `GenerateSecret: true`, matching the native Cognito API path. This is a fidelity fix for machine-to-machine Cognito workflows deployed via CDK/SAM.

#### Fixed (5 bugs, 2 notable for IaC)

**CORS fix** (Fixes [#406](https://github.com/ministackorg/ministack/issues/406) — the one documented in prior research):
- Per-API `corsConfiguration` now applied to preflights and dispatched responses
- `Access-Control-Allow-Credentials: true` only when configured with a concrete origin (not wildcard)
- Previously: every OPTIONS preflight returned hardcoded `Access-Control-Allow-Origin: *` regardless of config

**Lambda alias qualifier parsing** (Fixes [#407](https://github.com/ministackorg/ministack/issues/407)):
- Integrations wired to qualified ARNs (`arn:...:function:<name>:<alias>`) previously resolved the alias name as a function name and returned 502
- Fixed for v1 REST, v2 HTTP, v2 WebSocket dispatchers, and ESM pollers (SQS, Kinesis, DDB Streams)
- Worker pool keyed by `name:qualifier` so aliased vs unqualified calls don't share process state

Other fixes: API Gateway v1 error `__type` field, SQS `ReceiptHandleIsInvalid` on singular delete operations.

**Context from v1.3.5 (same day, released before v1.3.6)**:
The v1.3.5 release on the same date fixed: *"CloudFormation `AWS::Region` and provisioner ARNs ignored the caller's region"* — per-request region is now a contextvar. CDK bootstrap with `AWS_REGION=eu-west-1` previously got `us-east-1` baked into `${AWS::Region}` substitutions and all provisioner ARNs. This was a critical CDK correctness bug fixed alongside the v1.3.6 changes.

---

### 4. CDK Bootstrap Behavior and Asset Upload

From the [MiniStack README CDK section](https://github.com/ministackorg/ministack/blob/main/README.md#aws-cdk):

```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cdk bootstrap aws://000000000000/us-east-1
cdk deploy --require-approval never
```

**No `LOCALSTACK_HOSTNAME` or `EDGE_PORT` required** — just `AWS_ENDPOINT_URL`. This is a simpler setup than Floci's CDK path, which requires `cdklocal` wrapper + two separate env vars.

**CDK bootstrap stack resource types**: The CDKToolkit stack creates `AWS::S3::Bucket`, `AWS::ECR::Repository`, and multiple `AWS::IAM::Role`/`AWS::IAM::Policy` resources. All four are in MiniStack's CFN resource type table. The v1.3.5 fix to `${AWS::Region}` substitution also ensures the IAM Role ARNs and S3 bucket names in the bootstrap template resolve to the correct region.

**Asset upload via presigned S3 URLs**: CDK uploads Lambda ZIP assets to the CDKToolkit S3 staging bucket using presigned URLs. MiniStack's S3 service supports `CreateMultipartUpload`, `UploadPart`, `CompleteMultipartUpload`, and standard presigned URL patterns (the S3 implementation is full-fidelity; no evidence of presigned URL limitations in the README or recent releases).

**ECR push for Docker image assets**: CDK pushes Docker image assets to the CDKToolkit ECR staging repository. MiniStack's ECR supports the full Docker V2 manifest push protocol: `GetAuthorizationToken`, `InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`, `PutImage`, `BatchCheckLayerAvailability`. No end-to-end CDK asset-via-ECR test is documented, but the required protocol operations are present.

**CloudFormation stack completion semantics**: MiniStack states "Stacks deploy asynchronously (`CREATE_IN_PROGRESS` → `CREATE_COMPLETE`) — poll with DescribeStacks". CDK's standard deploy loop polls `DescribeStacks` until terminal state. This matches.

**Confidence**: CDK bootstrap likely succeeds based on documented resource type support and v1.3.5 region fix. No independent end-to-end CDK asset upload test has been found (same gap as Floci). **Confidence: Medium** — the pieces are present, but "works in practice" is not independently verified.

---

## Evidence

| Data Point | Source |
|---|---|
| MiniStack `AWS::Lambda::EventSourceMapping` CFN support, Ref=UUID | [MiniStack README — CloudFormation section](https://github.com/ministackorg/ministack/blob/main/README.md) — directly analyzed 2026-04-23 |
| MiniStack `AWS::Lambda::Permission` CFN support, Ref=Statement ID | [Same source](https://github.com/ministackorg/ministack/blob/main/README.md) |
| MiniStack CFN unsupported types fail with `CREATE_FAILED` (not silent stub) | [Same source](https://github.com/ministackorg/ministack/blob/main/README.md) — explicit statement in the CFN section |
| MiniStack intrinsic functions list (16 functions including full conditional set) | [Same source](https://github.com/ministackorg/ministack/blob/main/README.md) |
| MiniStack full CFN resource type table (~70 resource types) | [Same source](https://github.com/ministackorg/ministack/blob/main/README.md) |
| MiniStack v1.3.6 release notes: path-based API GW data plane, `ms-custom-id`, Cognito CFN secret, CORS fix, alias fix | [GitHub release v1.3.6](https://github.com/ministackorg/ministack/releases/tag/v1.3.6) — directly analyzed 2026-04-23 |
| MiniStack v1.3.5 release notes: CFN `${AWS::Region}` per-request fix (CDK non-default region) | [GitHub release v1.3.5](https://github.com/ministackorg/ministack/releases/tag/v1.3.5) — directly analyzed 2026-04-23 |
| MiniStack CDK setup: `AWS_ENDPOINT_URL` only, `cdk bootstrap` + `cdk deploy` | [MiniStack README — CDK section](https://github.com/ministackorg/ministack/blob/main/README.md) |
| MiniStack Terraform provider: supports both v5 and v6, explicit `endpoints {}` block (32 services) | [Same source](https://github.com/ministackorg/ministack/blob/main/README.md) — Terraform section |
| MiniStack ECR Docker V2 manifest push operations | [Same source](https://github.com/ministackorg/ministack/blob/main/README.md) — ECR service table |
| MiniStack S3 multipart upload and presigned URL operations | [Same source](https://github.com/ministackorg/ministack/blob/main/README.md) — S3 service table |
| Floci `Lambda::EventSourceMapping` and `Lambda::Permission` silently stubbed | Prior source analysis of `CloudFormationResourceProvisioner.java` (inherited from prior research iteration) |

---

## Trade-offs

### The Core Asymmetry Resolved

The prior report stated: *"Neither Floci nor MiniStack has a validated path for `sam deploy` creating a fully wired serverless stack end-to-end through CloudFormation."* This was identified by the peer review as an overreach for MiniStack.

The source-level evidence now resolves this asymmetry:

- **Floci**: `Lambda::EventSourceMapping` and `Lambda::Permission` fall to the default stub → `CREATE_COMPLETE` is returned → the stack "succeeds" but event routing is not wired. **This is a silent trap for teams using CDK/SAM for event-source wiring.**

- **MiniStack**: Both types are provisioned — `AWS::Lambda::Permission` calls `AddPermission`, `AWS::Lambda::EventSourceMapping` calls `CreateEventSourceMapping`. The event routing IS wired when a CFN stack deploys these types. Templates with unsupported types also fail loudly rather than silently.

This means for teams that deploy serverless stacks via CloudFormation (CDK/SAM), **MiniStack provides correct end-to-end event wiring** while Floci provides silent non-wiring.

### When Floci Remains Better

1. **Terraform-first teams with validated compat suite**: Floci has a checked-in CI test suite (`compat-terraform`) against real Terraform provider v6.x with explicit `endpoints {}` block. MiniStack documents the equivalent Terraform config in the README but has no equivalent automated CI compat suite committed to the repo.

2. **IAM policy enforcement**: Floci's configurable `enforcement-enabled: true` for IAM policy evaluation has no MiniStack equivalent. MiniStack supports IAM CRUD operations but no documented policy enforcement mode.

3. **Stable, CI-tested surface**: Floci's compat suite provides a hardened, regression-tested set of resource types. MiniStack's much larger CFN surface (70+ types) has not been independently validated to the same level.

### When MiniStack Is Better (now extended)

1. **CloudFormation-mediated serverless stacks**: `Lambda::EventSourceMapping` and `Lambda::Permission` are provisioned, not stubbed. CDK/SAM stacks that wire event sources via CloudFormation actually work.

2. **Full conditional logic in templates**: Fn::If, Fn::Equals, Fn::And, Fn::Or, Fn::Not — the full CFN condition model is supported. Templates with `AWS::NoValue` patterns (common in CDK-generated templates) resolve correctly.

3. **Error visibility for unsupported types**: `CREATE_FAILED` instead of silent `CREATE_COMPLETE`. Teams can identify gaps immediately.

4. **CDK setup simplicity**: `AWS_ENDPOINT_URL` only — no wrapper script, no `LOCALSTACK_HOSTNAME`/`EDGE_PORT` pair.

5. **Cross-stack exports**: `Fn::ImportValue` and `ListExports` supported — multi-stack CDK apps can reference outputs across stacks.

---

## Confidence

| Claim | Confidence | Basis |
|---|---|---|
| MiniStack CFN provisions `Lambda::EventSourceMapping` and `Lambda::Permission` | **High** | Explicit README resource type table with Ref/GetAtt documented |
| MiniStack CFN unsupported types fail with `CREATE_FAILED` (not silent stub) | **High** | Explicit README statement |
| MiniStack intrinsic functions list (16 functions including full conditional set) | **High** | Explicit README list |
| MiniStack v1.3.6 changes (path-based data plane, ms-custom-id, Cognito secret, CORS fix, alias fix) | **High** | GitHub release notes directly analyzed |
| MiniStack CDK uses `AWS_ENDPOINT_URL`, plain `cdk bootstrap`/`cdk deploy` | **High** | README CDK section |
| CDK bootstrap succeeds with MiniStack (resource types present, region fix in v1.3.5) | **Medium** | Documented resource type support + v1.3.5 fix; no independent end-to-end test found |
| CDK Lambda ZIP asset upload via presigned S3 URL works | **Medium** | S3 presigned URL operations present; no end-to-end CDK asset upload test documented |
| Floci does NOT support `Fn::If` conditional functions | **Medium** | Absent from prior source analysis; but prior list has auditability gap (peer review issue #8) |
| MiniStack `sam deploy` wires event sources end-to-end | **Medium** | Lambda::Permission + ESM provisioned; no explicit `sam deploy` end-to-end test found in MiniStack docs |

---

## New Questions

1. **Does MiniStack's CloudFormation provisioner actively poll for async Lambda resource creation?** `CreateEventSourceMapping` and `AddPermission` are fast synchronous operations, but `CreateFunction` (when the Lambda uses Docker RIE mode) could take seconds. Does the CFN engine wait for the function to be ready before marking `Lambda::Function` as `CREATE_COMPLETE`, or does it mark it immediately and risk a subsequent `Lambda::EventSourceMapping` provisioning against a not-yet-ready function?

2. **Does the `ms-custom-id` tag survive a MiniStack `/_ministack/reset`?** If the reset endpoint wipes all state including the API ID mapping, the stable-ID feature only helps across Terraform applies on a running instance, not across container restarts. The prior research noted this kind of warm-boot/cold-boot distinction as important for CI pipelines.

3. **What happens when `cdk bootstrap` runs against MiniStack and then runs again (idempotency)?** CDK bootstrap is designed to be idempotent — running it twice should detect the existing `CDKToolkit` stack and no-op or update. MiniStack's CFN support includes `UpdateStack` and `DescribeStacks`, but the specific CDK bootstrap idempotency path (using `DescribeStacks` to detect the existing toolkit stack) has not been validated.

---

## Peer Review (codex-cli)

### Issue 1: README support table is treated as proof of internal implementation details
- **Type**: unsupported claim
- **Location**: “In MiniStack they invoke the real Lambda `AddPermission` and `CreateEventSourceMapping` API calls”
- **Problem**: The cited evidence shows the README resource matrix documents support for `AWS::Lambda::Permission` and `AWS::Lambda::EventSourceMapping`, with `Ref` behavior, but it does **not** prove the exact internal implementation path or API call names. That is a stronger claim than the source supports.
- **Impact**: It overstates evidentiary strength. The safer claim is “the README documents these resource types as supported,” not “we verified the exact internal call flow.”

### Issue 2: Floci comparison relies on prior analysis, not evidence in this document
- **Type**: unsupported claim
- **Location**: “This directly resolves the gap confirmed in Floci's `CloudFormationResourceProvisioner.java`… both types fall to the default stub and succeed silently.”
- **Problem**: This document cites “prior source analysis” rather than reproducing the evidence. For a peer-reviewable research artifact, that makes the core asymmetry only partially auditable.
- **Impact**: The strongest comparative conclusion depends on a missing primary citation.

### Issue 3: “Full change analysis” is not actually full
- **Type**: contradiction
- **Location**: “### 3. MiniStack v1.3.6 (2026-04-20): Full Change Analysis”
- **Problem**: The v1.3.6 notes also include the `$default` stage routing fix, which your own cited release text contains, but the analysis frames the section as “full” while not meaningfully analyzing that fix. The release includes more than the three added items plus the two emphasized bug fixes.  
- **Impact**: This weakens trust. Either call it a “targeted analysis” or cover every listed change.

### Issue 4: “MiniStack provides correct end-to-end event wiring” is too strong
- **Type**: unsupported claim
- **Location**: “MiniStack provides correct end-to-end event wiring” / “The event routing IS wired when a CFN stack deploys these types.”
- **Problem**: The evidence supports that the CFN engine claims support for those resource types. It does **not** independently validate end-to-end behavior through a real CDK/SAM deployment, ordering, readiness, retries, or invocation semantics.
- **Impact**: This is the biggest overreach. The conclusion should stay at “materially stronger evidence than Floci” unless you have an end-to-end test.

### Issue 5: Conditional-function claims blur documented support with verified behavior
- **Type**: missing nuance
- **Location**: “Templates with `AWS::NoValue` patterns (common in CDK-generated templates) resolve correctly.”
- **Problem**: The README documents `Fn::If`, condition operators, and `AWS::NoValue`, but that is still not the same as verifying all the real-world semantics CDK relies on, especially nested conditions, property elision, list/object contexts, and update-time behavior.
- **Impact**: The analysis should distinguish “documented support exists” from “common CDK templates have been validated.”

### Issue 6: Absence-of-evidence reasoning is used as positive compatibility evidence
- **Type**: unsupported claim
- **Location**: “the S3 implementation is full-fidelity; no evidence of presigned URL limitations in the README or recent releases.”
- **Problem**: “No evidence of limitations” is not evidence that CDK presigned-upload flows work. Same for the ECR section: supported operations are necessary, but not sufficient, for Docker/CDK asset compatibility.
- **Impact**: This inflates confidence around CDK asset upload behavior.

### Issue 7: Main-branch README is treated as authoritative without reproducibility safeguards
- **Type**: missing nuance
- **Location**: “current `main` branch, confirmed 2026-04-23” and “README is the primary specification document”
- **Problem**: Using `main` for a source-level comparison is fragile. A pinned commit or release tag would be more reproducible. Also, README is a product claim, not the same thing as verified implementation.
- **Impact**: Good for exploratory research, weaker for audit-grade conclusions.

### Issue 8: Floci intrinsic-function absence is acknowledged as uncertain, but still used aggressively
- **Type**: contradiction
- **Location**: “Confidence for ‘Floci does NOT support Fn::If’ is Medium” vs. later “MiniStack’s intrinsic function support is substantially broader” and “full conditional logic… absent from Floci’s documented set.”
- **Problem**: You correctly admit the Floci list has an “auditability gap,” but then still use that gap to make a fairly hard-edged comparison. The right phrasing is “MiniStack documents broader support than the Floci functions we have verified so far.”
- **Impact**: Comparative rigor is weakened.

### Issue 9: CDK bootstrap resource claims are not sourced
- **Type**: unsupported claim
- **Location**: “The CDKToolkit stack creates `AWS::S3::Bucket`, `AWS::ECR::Repository`, and multiple `AWS::IAM::Role`/`AWS::IAM::Policy` resources.”
- **Problem**: That may be true, but this document does not cite the bootstrap template or an official CDK source for that exact resource set. Bootstrap templates also vary by modern/legacy bootstrap and version.
- **Impact**: It introduces a dependency on unstated CDK assumptions.

### Issue 10: Comparison with Floci’s CDK workflow is unsourced here
- **Type**: unsupported claim
- **Location**: “This is a simpler setup than Floci's CDK path, which requires `cdklocal` wrapper + two separate env vars.”
- **Problem**: Even if true, it is not evidenced in this document. This is another inherited comparison that should have been directly cited or softened.
- **Impact**: Small individually, but it adds to the pattern of comparative claims outrunning the citations.

### Issue 11: “Additional Lambda CFN resource types beyond Floci’s scope” may overstate what was verified
- **Type**: missing nuance
- **Location**: “`AWS::Lambda::Version`, `AWS::Lambda::Alias`, `AWS::Lambda::LayerVersion` — none of which appear in Floci's provisioner switch statement per prior analysis.”
- **Problem**: That is again a comparison to prior analysis, not primary evidence in this document. Also “beyond Floci’s scope” sounds stronger than “not found in the previously reviewed switch statement.”
- **Impact**: Overconfident wording where the evidence is secondhand.

### Issue 12: The report underplays the risk of README-vs-runtime drift
- **Type**: gap
- **Location**: Overall, especially sections 1, 2, and 4
- **Problem**: A key missing caveat is that README matrices and release notes describe intended behavior, not necessarily tested behavior. The document needed a clearer separation between:
  1. documented capability,  
  2. source-confirmed implementation, and  
  3. end-to-end validated behavior.
- **Impact**: This is the main methodological gap affecting the whole report.

## Summary

- **Issues found**: 12
- **Overall reliability assessment**: **Medium**
- **What would most improve the findings**:
  1. Replace inherited Floci claims with direct primary citations.
  2. Downgrade README-based implementation claims to “documented support.”
  3. Add at least one real end-to-end validation path for CDK/SAM serverless deployment and asset upload.
  4. Pin MiniStack evidence to a commit or release tag instead of `main`.

Sources used: [MiniStack README](https://github.com/ministackorg/ministack/blob/main/README.md), [MiniStack v1.3.6 release mirror](https://newreleases.io/project/github/ministackorg/ministack/release/v1.3.6), [MiniStack v1.3.5 release mirror](https://newreleases.io/project/github/ministackorg/ministack/release/v1.3.5)

## Key Learnings:
1. README matrices are useful product evidence, but they are weaker than source-confirmed implementation or end-to-end tests.
2. The strongest flaw in the findings is overclaiming runtime correctness from documented support alone.
3. Comparative research becomes fragile when one side is cited directly and the other relies on inherited prior analysis.
