# Iteration 005 — CloudFormation and IaC toolchain compatibility (Terraform, CDK, SAM)

**Status:** keep  
**Scores:** coverage=76.2, quality=65.0, total=69.5  
**Timestamp:** 2026-04-24T01:40:02.407133+00:00  

---

I now have comprehensive primary source data. Let me compile the final research report.

---

## Findings

### 1. Floci: CloudFormation Resource Type Coverage (From Source Code)

The most valuable finding of this research iteration is a direct analysis of Floci's `CloudFormationResourceProvisioner.java` source code, which maps every `AWS::*` resource type to an action. This is the ground truth, not marketing copy.

**Fully provisioned (wired to actual Floci service implementations):**

| Resource Type | Notes |
|---|---|
| `AWS::S3::Bucket`, `AWS::S3::BucketPolicy` | Full S3 integration |
| `AWS::SQS::Queue`, `AWS::SQS::QueuePolicy` | Standard + FIFO |
| `AWS::SNS::Topic` | Topic creation only |
| `AWS::DynamoDB::Table`, `AWS::DynamoDB::GlobalTable` | GSI/LSI supported |
| `AWS::Lambda::Function` | S3 or inline ZIP code |
| `AWS::IAM::Role`, `::User`, `::AccessKey`, `::Policy`, `::ManagedPolicy`, `::InstanceProfile` | Full IAM hierarchy |
| `AWS::SSM::Parameter` | SecureString included |
| `AWS::KMS::Key`, `::Alias` | Signing/verify supported |
| `AWS::SecretsManager::Secret` | Password generation supported |
| `AWS::CloudFormation::Stack` | Nested stacks supported |
| **`AWS::CDK::Metadata`** | **Critical CDK shim — prevents bootstrap failures** |
| `AWS::ECR::Repository` | |
| `AWS::Route53::HostedZone`, `::RecordSet` | |
| `AWS::Events::Rule` | EventBridge |
| `AWS::ApiGateway::RestApi/Resource/Method/Deployment/Stage` | Full v1 REST management plane |
| `AWS::ApiGatewayV2::Api/Route/Integration/Stage/Deployment` | Full v2 HTTP management plane |

**Silently stubbed (default case — stack shows CREATE_COMPLETE but resource is never created):**

| Resource Type | Impact |
|---|---|
| **`AWS::Lambda::EventSourceMapping`** | **CDK/SAM SQS→Lambda, Kinesis→Lambda, DDB→Lambda wiring never created** |
| **`AWS::Lambda::Permission`** | **API Gateway→Lambda invocation permission never granted** |
| `AWS::SNS::Subscription` | SNS→Lambda/SQS wiring not created via CFN |
| `AWS::SQS::QueueRedrivePolicy` | Redrive must be set via direct API |
| `AWS::StepFunctions::StateMachine` | |
| `AWS::Cognito::UserPool`, `::UserPoolClient` | Cognito exists in Floci's API but not CFN |
| `AWS::Logs::LogGroup`, `AWS::CloudWatch::Alarm` | |
| `AWS::ECS::TaskDefinition/Service/Cluster` | Docker-backed ECS exists but not via CFN provisioner |

The `default` branch logs at `DEBUG` level and stubs the resource with a fake physical ID and `arn:aws:stub:::LogicalId`. **Stacks will show `CREATE_COMPLETE` even when critical wiring resources are absent.** This is the single most significant operational trap for IaC-heavy teams.

---

### 2. Floci: Terraform Compatibility

**Provider config**: Terraform AWS Provider 5.x (via AWS SDK for Go v2) [honors `AWS_ENDPOINT_URL`](https://registry.terraform.io/providers/hashicorp/aws/5.90.0/docs/guides/custom-service-endpoints) as a global endpoint override, plus service-specific `AWS_ENDPOINT_URL_<SERVICE>` variants. Floci's official `compat-terraform/run.sh` sets only `AWS_ENDPOINT_URL=$FLOCI_ENDPOINT` — no explicit `endpoints {}` block required for modern provider versions.

For older Terraform provider versions or explicit control, the standard block is:
```hcl
provider "aws" {
  region     = "us-east-1"
  access_key = "test"
  secret_key = "test"
  s3_force_path_style         = true
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  endpoints {
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
    # ... one entry per service
  }
}
```

**Tested resources in Floci's official compat-terraform suite** (from `main.tf` source code):
- S3 bucket + versioning ✅
- SQS queue + DLQ + redrive policy ✅
- SNS topic + SQS subscription ✅
- DynamoDB table with TTL ✅
- IAM role + trust policy ✅
- SSM parameters (String + SecureString) ✅
- Secrets Manager ✅
- RDS PostgreSQL instance ✅ (real Docker)
- Cognito User Pool ✅
- CloudWatch metric alarm ✅

**Missing from Terraform compat test**: Lambda function, API Gateway resources. These work via the API but are not part of Floci's official automated Terraform validation.

**Known issue**: GitHub issue [#412](https://github.com/floci-io/floci/issues/412) — Lambda functions deployed via Terraform `aws_lambda_function` with `filename = "deployment.zip"` fail when the ZIP exceeds ~15 MB (base64 overhead hits a Jackson JSON parser 20 MB string limit). Workaround: use S3 code source (`s3_bucket`/`s3_key`).

---

### 3. Floci: AWS CDK Compatibility

Floci maintains a `compatibility-tests/compat-cdk/` suite. The CDK `run.sh` sets:
```bash
export LOCALSTACK_HOSTNAME="${FLOCI_ENDPOINT#http://}"  # strips http://
export EDGE_PORT="${FLOCI_ENDPOINT##*:}"                # extracts port
```
This means Floci uses **`cdklocal`** (LocalStack's CDK wrapper from `aws-cdk-local` package), not plain `cdk`. The `LOCALSTACK_HOSTNAME`/`EDGE_PORT` variables are the interface contract.

**CDK test stack covers** (from `floci-stack.js` source code):
- `s3.Bucket` → `AWS::S3::Bucket` ✅
- `sqs.Queue` → `AWS::SQS::Queue` ✅
- `dynamodb.TableV2` with GSI + LSI → `AWS::DynamoDB::Table` ✅
- `secretsmanager.CfnSecret` with `generateSecretString` → `AWS::SecretsManager::Secret` ✅
- `AWS::CDK::Metadata` stub → handled explicitly ✅

**Not tested in CDK compat suite**: Lambda, API Gateway, event source mappings. Any CDK stack using `lambda.Function.addEventSource(new SqsEventSource(queue))` will generate `AWS::Lambda::EventSourceMapping` → silently stubbed.

**CDK bootstrap**: Bootstrap creates a `CDKToolkit` CloudFormation stack containing an S3 bucket, ECR repository, and IAM roles — all of which are provisioned types in Floci. Bootstrap should succeed with `cdklocal bootstrap`.

---

### 4. SAM CLI Compatibility

SAM CLI's `sam deploy` command transforms `AWS::Serverless::*` resources into CloudFormation and deploys via the CloudFormation API. For Floci, this means:

| SAM Transform Output | CFN Resource | Floci Outcome |
|---|---|---|
| Function | `AWS::Lambda::Function` | ✅ provisioned |
| API event | `AWS::ApiGateway::RestApi/...` | ✅ provisioned |
| SQS event | `AWS::Lambda::EventSourceMapping` | ❌ silently stubbed |
| HTTP API event | `AWS::ApiGatewayV2::Api/...` | ✅ provisioned |
| Lambda permission | `AWS::Lambda::Permission` | ❌ silently stubbed |

**`sam deploy` to Floci will succeed without errors, but event routing will not be wired.** The recommended hybrid pattern (confirmed by AWS re:Post article) is: **SAM CLI for Lambda runtime + API Gateway** (`sam local invoke`, `sam local start-api`) + **Floci/MiniStack for backend services** (DynamoDB, SQS, S3). This combination works correctly and sidesteps the CloudFormation gap.

---

### 5. MiniStack: CloudFormation and IaC Compatibility

MiniStack's CloudFormation internals are less transparent than Floci's (no source code analysis available at this depth). Key findings from release notes and community reports:

**What works in MiniStack**:
- API Gateway v2 (HTTP API) full control plane + data plane dispatch since v1.0.2 [(MiniStack v1.0.4 blog)](https://dev.to/nahuel990/ministack-v104-api-gateway-v2-lambda-warm-workers-sns-sqs-fanout-state-persistence-50ac). Host-header routing (`{apiId}.execute-api.localhost`). This is **the data plane**, meaning actual HTTP requests get routed to Lambda — not just management operations.
- SQS → Lambda event source mapping with background poller ✅ (v1.0.2+)
- SNS → SQS fanout and SNS → Lambda dispatch ✅ (v1.0.2+)
- DynamoDB TTL enforcement ✅ (v1.0.2+)
- Lambda warm/cold start worker pool for Python/Node.js ✅

**Known open issues in MiniStack**:
- [Issue #406](https://github.com/ministackorg/ministack/issues/406): API Gateway v2 `cors_configuration` ignored in v1.3.5 — every preflight returns wildcard `Access-Control-Allow-Origin: *` regardless of config. Blocks cookie-based auth and credentialed browser requests.
- MiniStack does **not bundle boto3** in Lambda runtime — must package in ZIP. Only affects Python Lambda deployed directly to MiniStack (not an issue when using SAM CLI runtime).
- CFN key format bugs for ECS provisioner (PascalCase vs. camelCase) were recently fixed.
- The AWS re:Post article (dated April 3, 2026) noted API Gateway dispatch to Lambda "not working in MiniStack v3.0.0." This appears to be from a very early development build (`3.0.0.dev` shown in health endpoint), not the v1.x release series. The v1.0.2 release notes confirm dispatch was added.

**MiniStack Terraform / CDK**: MiniStack uses the same port 4566 and the same `AWS_ENDPOINT_URL` pattern. No official compat test suite equivalent to Floci's. Indirect CDK support exists because CDK synthesizes CloudFormation, which MiniStack handles, but the depth of CloudFormation resource coverage is not formally documented.

---

### 6. IaC-Specific Comparison Summary

| Dimension | Floci | MiniStack |
|---|---|---|
| **Terraform** `AWS_ENDPOINT_URL` | ✅ official compat test | ✅ same pattern, no official test |
| **Terraform** Lambda + API GW | ✅ works via API (not tested) | ✅ works via API (not tested) |
| **CDK** bootstrap | ✅ via `cdklocal` + `LOCALSTACK_HOSTNAME`/`EDGE_PORT` | ⚠️ no official test, indirect |
| **CDK** simple stacks (S3/SQS/DDB) | ✅ tested in compat suite | ✅ documented |
| **CDK** serverless + event sources (via CFN) | ❌ Lambda::Permission, Lambda::ESM silently stubbed | ⚠️ unverified depth |
| **SAM `sam deploy`** | ❌ event wiring silently broken | ⚠️ partial — API GW v2 dispatch works, CloudFormation coverage unclear |
| **SAM `sam local` hybrid** | ✅ recommended pattern | ✅ officially documented (AWS re:Post) |
| **CFN intrinsic functions** | ✅ Ref, Fn::Sub, Fn::GetAtt, Fn::Join, Fn::FindInMap, Fn::Base64 | ⚠️ no source analysis |
| **CFN ChangeSets** | ✅ implemented | ⚠️ unverified |
| **Nested stacks** (`AWS::CloudFormation::Stack`) | ✅ supported | ⚠️ unverified |

---

## Evidence

| Data Point | Source |
|---|---|
| Floci CloudFormationResourceProvisioner switch statement (full resource type list) | [Source code](https://raw.githubusercontent.com/floci-io/floci/main/src/main/java/io/github/hectorvent/floci/services/cloudformation/CloudFormationResourceProvisioner.java) — directly analyzed |
| Floci CDK test stack covers S3/SQS/DDB/SecretsManager, not Lambda/ApiGW | [floci-stack.js](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-cdk/lib/floci-stack.js) — directly analyzed |
| Floci CDK run.sh uses `LOCALSTACK_HOSTNAME` + `EDGE_PORT` | [compat-cdk/run.sh](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-cdk/run.sh) — directly analyzed |
| Floci Terraform compat test covers S3/SQS/SNS/DDB/IAM/SSM/SecretsManager/RDS/Cognito/CloudWatch | [compat-terraform/main.tf](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-terraform/main.tf) — directly analyzed |
| Floci Terraform compat uses `AWS_ENDPOINT_URL` env var only | [compat-terraform/run.sh](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-terraform/run.sh) — directly analyzed |
| Terraform AWS Provider 5.x supports `AWS_ENDPOINT_URL` global override | [Terraform Registry docs v5.90.0](https://registry.terraform.io/providers/hashicorp/aws/5.90.0/docs/guides/custom-service-endpoints) |
| Floci Lambda service supports CreateEventSourceMapping/AddPermission via API (not CFN) | [floci.io/services/lambda](https://floci.io/floci/services/lambda/) — directly confirmed |
| Floci Lambda ZIP >15 MB inline fails with Jackson 20 MB limit (issue #412) | [GitHub issue #412](https://github.com/floci-io/floci/issues/412) |
| MiniStack API Gateway v2 full data plane dispatch (host-header routing) since v1.0.2 | [MiniStack v1.0.4 blog post](https://dev.to/nahuel990/ministack-v104-api-gateway-v2-lambda-warm-workers-sns-sqs-fanout-state-persistence-50ac) |
| MiniStack SQS→Lambda ESM with background poller, SNS→SQS/Lambda dispatch (v1.0.2) | [Same source](https://dev.to/nahuel990/ministack-v104-api-gateway-v2-lambda-warm-workers-sns-sqs-fanout-state-persistence-50ac) |
| MiniStack CORS bug (issue #406): wildcard response ignores config in v1.3.5 | [GitHub issue #406](https://github.com/ministackorg/ministack/issues/406) |
| MiniStack API GW dispatch "not working in v3.0.0.dev" — AWS re:Post article | [repost.aws article](https://repost.aws/articles/AR-WRCanAJScabqnY2OQ5H7A/local-lambda-testing-with-ministack-sam-cli-and-finch) |
| MiniStack does not bundle boto3 in Lambda runtime | [Same repost.aws article](https://repost.aws/articles/AR-WRCanAJScabqnY2OQ5H7A/local-lambda-testing-with-ministack-sam-cli-and-finch) |
| `nahuelnucera/ministack` and `ministackorg/ministack` are the same project | [newreleases.io](https://newreleases.io/project/github/ministackorg/ministack/release/v1.2.1) |
| Floci API Gateway v1 "not implemented" list (Deployment detail, Authorizer update, VPC Links, etc.) | [floci.io/services/api-gateway](https://floci.io/floci/services/api-gateway/) |
| Floci CloudFormation supported actions (21 actions) | [floci.io/services/cloudformation](https://floci.io/floci/services/cloudformation/) |
| Floci default account ID: `000000000000`, configurable via `FLOCI_DEFAULT_ACCOUNT_ID` | [floci.io/getting-started/aws-setup](https://floci.io/floci/getting-started/aws-setup/) |

---

## Trade-offs

### When Floci is better for IaC

1. **Terraform-first teams**: Floci's official Terraform compat suite tests 10+ resource types including RDS and Cognito. Terraform uses the AWS API directly — the CloudFormation provisioner gap doesn't affect it. Floci is the safer bet for validated Terraform workflows.

2. **CDK simple stacks** (S3 + SQS + DDB + Secrets Manager): Fully tested in Floci's compat suite. Add `cdklocal` to your workflow, export `LOCALSTACK_HOSTNAME`/`EDGE_PORT`.

3. **Explicit API-based wiring**: Teams that create event source mappings imperatively (Terraform `aws_lambda_event_source_mapping`, SDK `create_event_source_mapping`) rather than via CloudFormation templates are unaffected by the CFN stub gap.

4. **IAM enforcement**: Floci's configurable IAM enforcement is a differentiator for catching authorization bugs. No CloudFormation gap here.

### When MiniStack is better for IaC

1. **API Gateway v2 data plane testing**: MiniStack routes actual HTTP requests to Lambda containers from v1.0.2+. This is the real use case for most local serverless testing — you want actual HTTP requests to your API to reach your Lambda code, not just management-plane wiring.

2. **End-to-end SAM/serverless hybrid**: The official AWS re:Post article patterns MiniStack + SAM CLI. This is the most authoritative real-world guidance found.

3. **Python Lambda with SQS/DDB warm workers**: MiniStack's warm-worker model for Python/Node is suited for testing module-level state bugs. The boto3 packaging requirement is a one-time friction.

### The critical gap both tools share

**Neither Floci nor MiniStack has a validated path for `sam deploy` creating a fully wired serverless stack end-to-end through CloudFormation.** The practical solution is the hybrid pattern: SAM CLI handles Lambda runtime + API Gateway dispatch; Floci/MiniStack handles stateful backend services (DynamoDB, SQS, S3, SNS, SSM).

For CDK users: **stacks with `Lambda::EventSourceMapping` and `Lambda::Permission` resources will silently succeed in Floci but won't be wired.** This is a trap with no error message. Teams must either:
- Use Terraform instead of CDK for event source wiring (works correctly)
- Manually create ESMs and permissions via CLI/SDK after CDK deploy
- Wait for these resource types to be added to Floci's CFN provisioner

### Terraform provider configuration note

Terraform AWS Provider v5.x with `AWS_ENDPOINT_URL` set globally works for most resources. However, some resources (particularly older ones) may still make service-specific calls that need to be enumerated in the `endpoints {}` block. The explicit block is the most reliable approach for production-grade CI pipelines. S3 additionally requires `s3_force_path_style = true` and `skip_credentials_validation = skip_requesting_account_id = true`.

---

## Confidence

| Claim | Confidence | Basis |
|---|---|---|
| Floci's supported CloudFormation resource types | **High** | Direct source code analysis of `CloudFormationResourceProvisioner.java` |
| Lambda::EventSourceMapping and Lambda::Permission silently stubbed in Floci CFN | **High** | Direct source code analysis — not in switch statement, falls to default stub |
| Terraform AWS Provider 5.x honors `AWS_ENDPOINT_URL` globally | **High** | Official Terraform Registry docs v5.90.0 |
| Floci CDK uses `cdklocal` / `LOCALSTACK_HOSTNAME`+`EDGE_PORT` | **High** | Direct `run.sh` source code analysis |
| MiniStack API Gateway v2 data plane dispatch works (v1.0.2+) | **High** | Dev blog by primary maintainer with working code examples |
| MiniStack CORS config bug ignored in v1.3.5 | **High** | Direct GitHub issue #406 |
| MiniStack Lambda ESM (SQS poller) works via direct API | **High** | Dev blog v1.0.4 with code examples |
| MiniStack CloudFormation resource type depth | **Low** | No source code analysis available; only documentation claims verified |
| MiniStack CDK bootstrap behavior | **Unresolved** | No primary source found |
| Floci API Gateway v1 execute plane (actual HTTP routing) fidelity | **Medium** | Documentation lists it, no end-to-end test found in compat suite |
| Floci Lambda >15MB ZIP issue resolved vs. still open | **Medium** | Issue #412 identified, fix status not confirmed |

---

## New Questions

1. **Does `sam deploy --guided` to Floci fail silently or loudly for missing resource types?** The current finding is that unsupported CloudFormation resources are stubbed with `CREATE_COMPLETE` (silent failure). It's worth determining whether there's a Floci configuration option to turn stubbing into errors, which would make IaC mismatches visible rather than invisible.

2. **What does MiniStack's CloudFormation provisioner actually implement at the source-code level?** This iteration confirmed Floci's CFN gaps via source analysis. The same analysis has not been done for MiniStack — it's possible MiniStack handles `Lambda::EventSourceMapping` and `Lambda::Permission` via CFN, which would make it strictly better for CloudFormation-mediated deployments.

3. **How does CDK asset uploading (Lambda ZIP, Docker image) behave when the CDK bootstrap S3 bucket and ECR repo are in Floci?** Bootstrap itself likely succeeds (all required resource types are provisioned), but asset uploads depend on S3 presigned URL behavior and ECR `docker push` — both of which Floci supports in principle, but no end-to-end CDK asset upload test was found in the compat suite.

---

## Peer Review (codex-cli)

### Issue 1: Terraform guidance contradicts Floci’s checked-in config
- **Type**: factual error
- **Location**: “**Provider config**: Terraform AWS Provider 5.x … Floci's official `compat-terraform/run.sh` sets only `AWS_ENDPOINT_URL=$FLOCI_ENDPOINT` — no explicit `endpoints {}` block required for modern provider versions.”
- **Problem**: Floci’s checked-in [`compat-terraform/provider.tf`](https://github.com/floci-io/floci/blob/main/compatibility-tests/compat-terraform/provider.tf) pins `hashicorp/aws` to `~> 6.0` and includes an explicit `endpoints {}` block for multiple services. So the report gets both the tested provider line and the official config shape wrong.
- **Impact**: This weakens one of the central compatibility conclusions and could mislead readers into using a provider setup that Floci’s own suite does not actually model.

### Issue 2: “Full IAM hierarchy” is overstated
- **Type**: missing nuance
- **Location**: “`AWS::IAM::Role`, `::User`, `::AccessKey`, `::Policy`, `::ManagedPolicy`, `::InstanceProfile` | **Full IAM hierarchy**”
- **Problem**: The provisioner switch includes those types, but not `AWS::IAM::Group`. Calling that “full IAM hierarchy” is broader than the evidence supports. The source file shows cases for Role/User/AccessKey/Policy/ManagedPolicy/InstanceProfile, not Group.
- **Impact**: Overstates CloudFormation coverage and makes the support matrix sound more complete than it is.

### Issue 3: “Full v1/v2 management plane” for API Gateway is too broad
- **Type**: unsupported claim
- **Location**: “`AWS::ApiGateway::RestApi/Resource/Method/Deployment/Stage` | **Full v1 REST management plane**” and “`AWS::ApiGatewayV2::Api/Route/Integration/Stage/Deployment` | **Full v2 HTTP management plane**”
- **Problem**: The CloudFormation provisioner only wires those specific CFN resource types. Floci’s API Gateway docs explicitly list multiple v1 operations as not implemented, including deployment lifecycle detail, authorizer lifecycle, API key detail, usage-plan detail, and more ([Floci API Gateway docs](https://floci.io/floci/services/api-gateway/)). For v2, the CFN switch shown in the source covers Api/Route/Integration/Stage/Deployment, not authorizers.
- **Impact**: Readers may wrongly infer broader API Gateway IaC parity than the evidence shows.

### Issue 4: MiniStack CORS bug is presented as open/current even though it was fixed
- **Type**: factual error
- **Location**: “**Known open issues in MiniStack**: [Issue #406] … `cors_configuration` ignored in v1.3.5”
- **Problem**: MiniStack release [`v1.3.6`](https://newreleases.io/project/github/ministackorg/ministack/release/v1.3.6) on **2026-04-20** says `corsConfiguration` was fixed and explicitly references “Fixes #406.”
- **Impact**: This materially skews the MiniStack assessment by treating a fixed bug as a current limitation.

### Issue 5: MiniStack CDK and CloudFormation support is understated
- **Type**: factual error
- **Location**: “MiniStack Terraform / CDK … **No official compat test suite equivalent to Floci's. Indirect CDK support exists because CDK synthesizes CloudFormation, which MiniStack handles, but the depth of CloudFormation resource coverage is not formally documented.**”
- **Problem**: MiniStack’s README does formally document both:
  - **CDK usage** with plain `cdk bootstrap` / `cdk deploy` plus `AWS_ENDPOINT_URL` ([README](https://github.com/ministackorg/ministack), CDK section).
  - **CloudFormation support** including stack ops, change sets, exports, template formats, intrinsic functions, pseudo-parameters, and parameters ([README](https://github.com/ministackorg/ministack), CloudFormation section).
- **Impact**: The comparison under-credits MiniStack and makes the cross-tool picture less reliable.

### Issue 6: The “critical gap both tools share” overreaches
- **Type**: unsupported claim
- **Location**: “**Neither Floci nor MiniStack has a validated path for `sam deploy` creating a fully wired serverless stack end-to-end through CloudFormation.**”
- **Problem**: For Floci, the warning is well-supported by the missing/stubbed CFN resource types. For MiniStack, the report did not establish the same thing. MiniStack’s own docs claim CloudFormation support plus Lambda `AddPermission` / `CreateEventSourceMapping` and API Gateway data planes in the service matrix ([README](https://github.com/ministackorg/ministack)). That does not prove `sam deploy` works, but it also does not justify claiming the same gap exists.
- **Impact**: This is the biggest comparative overreach; it collapses “not verified” into “does not have.”

### Issue 7: Floci CloudFormation evidence is internally inconsistent
- **Type**: contradiction
- **Location**: Evidence row: “**Floci CloudFormation supported actions (21 actions)**”
- **Problem**: Floci’s current CloudFormation service page lists **17** actions ([CloudFormation docs](https://floci.io/floci/services/cloudformation/)), while Floci’s services overview lists CloudFormation with **18** supported operations ([services overview](https://floci.io/floci/services/)). The report gives **21** without reconciling the discrepancy.
- **Impact**: This suggests source reconciliation was incomplete, which is exactly the kind of thing a final research report should resolve before making confident claims.

### Issue 8: Floci intrinsic-function support is asserted without clear cited backing
- **Type**: unsupported claim
- **Location**: Comparison table: “**CFN intrinsic functions** | ✅ Ref, Fn::Sub, Fn::GetAtt, Fn::Join, Fn::FindInMap, Fn::Base64”
- **Problem**: The evidence table does not cite a Floci source for that list. The Floci CloudFormation docs page cited in the report does not enumerate intrinsics. This may be true from code analysis elsewhere, but the claim is not properly sourced in the report as written.
- **Impact**: Reduces auditability. A reader cannot distinguish “verified from source” from “inferred/remembered.”

### Issue 9: The SAM hybrid recommendation is over-attributed to the AWS re:Post article
- **Type**: unsupported claim
- **Location**: “The recommended hybrid pattern (**confirmed by AWS re:Post article**) is: **SAM CLI for Lambda runtime + API Gateway + Floci/MiniStack for backend services**”
- **Problem**: The cited AWS re:Post article is about **MiniStack + SAM CLI + Finch**, not Floci. Extending that pattern to Floci may be reasonable, but it is an inference, not something that source “confirmed.”
- **Impact**: Blurs the line between sourced fact and analyst extrapolation.

## Summary
- **Issues found**: 9
- **Overall reliability**: **Medium**
- **What would most improve the findings**:  
  1. Reconcile conflicting source counts and versions before finalizing.  
  2. Separate **verified fact** from **inference** explicitly.  
  3. Rework the MiniStack sections using its current README/release notes, especially after **v1.3.6 (2026-04-20)** fixed issue #406.  
  4. Correct the Terraform section to match Floci’s actual checked-in `provider.tf`.

Sources used: [Floci provisioner source](https://github.com/floci-io/floci/blob/main/src/main/java/io/github/hectorvent/floci/services/cloudformation/CloudFormationResourceProvisioner.java), [Floci API Gateway docs](https://floci.io/floci/services/api-gateway/), [Floci CloudFormation docs](https://floci.io/floci/services/cloudformation/), [Floci services overview](https://floci.io/floci/services/), [Floci compat-terraform provider.tf](https://github.com/floci-io/floci/blob/main/compatibility-tests/compat-terraform/provider.tf), [MiniStack README](https://github.com/ministackorg/ministack), [MiniStack v1.3.6 release notes](https://newreleases.io/project/github/ministackorg/ministack/release/v1.3.6), [AWS re:Post article](https://repost.aws/articles/AR-WRCanAJScabqnY2OQ5H7A/local-lambda-testing-with-ministack-sam-cli-and-finch)

## Key Learnings:
1. Floci’s strongest evidence is the CloudFormation provisioner source, but some summary labels overstate what those switch cases prove.
2. The Terraform section is materially wrong because Floci’s own compat suite uses provider `~> 6.0` and explicit `endpoints {}`.
3. MiniStack’s current documentation is much stronger than the report suggests, and issue #406 was fixed in v1.3.6 on 2026-04-20.
