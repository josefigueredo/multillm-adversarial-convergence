# Iteration 003 — Migration effort from LocalStack (config, SDK compatibility, breaking changes)

**Status:** keep  
**Scores:** coverage=76.2, quality=55.0, total=63.5  
**Timestamp:** 2026-04-24T01:15:07.362312+00:00  

---

Now I have all the data needed. Let me write the research report.

---

## Findings

### 1. Port and Wire-Protocol Compatibility: True Drop-in at the Network Layer

Both Floci and MiniStack bind to **port 4566** and implement the same AWS wire protocols (REST/XML for S3, Query for SQS/SNS/IAM, JSON 1.1 for DynamoDB/Lambda, etc.) that LocalStack used. No application code changes are required to switch: the `endpoint_url="http://localhost:4566"` in boto3, `--endpoint-url http://localhost:4566` in the CLI, and `.endpointOverride(URI.create("http://localhost:4566"))` in SDK v2 Java are identical before and after migration. [`[Floci services overview]`](https://floci.io/floci/services/) [`[MiniStack README]`](https://github.com/ministackorg/ministack)

### 2. Docker Compose Drop-in: One Line Change (with Caveats)

The minimal migration for both tools is a single image swap:

```yaml
# Before (LocalStack)
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - LOCALSTACK_AUTH_TOKEN=ls-xxx
      - SERVICES=s3,sqs,dynamodb,lambda
    volumes:
      - "./.localstack:/var/lib/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"

# After (Floci) — remove auth token, SERVICES, and old volume mount
services:
  floci:
    image: floci/floci:latest
    ports:
      - "4566:4566"
    volumes:
      - "./data:/app/data"                        # optional: persistence
      - "/var/run/docker.sock:/var/run/docker.sock"  # required: Lambda/RDS/ECS
    environment:
      - FLOCI_HOSTNAME=floci                      # required for multi-container

# After (MiniStack) — remove auth token, SERVICES, and old volume mount
services:
  ministack:
    image: ministackorg/ministack:latest
    ports:
      - "4566:4566"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"  # required: Lambda/RDS/ECS
    environment:
      - MINISTACK_REGION=us-east-1
      - MINISTACK_ACCOUNT_ID=000000000000
```

**Key insight on `SERVICES`**: LocalStack required an explicit service-allowlist. Both replacements start all services automatically; `SERVICES=...` is silently ignored or not needed. Floci supports per-service disabling via `FLOCI_SERVICES_<SERVICE>_ENABLED=false` env vars for resource-constrained environments. [`[Floci application.yml reference]`](https://floci.io/floci/configuration/application-yml/)

**Key insight on `FLOCI_HOSTNAME`**: When Floci runs inside Docker Compose and Lambda functions or other services call back to Floci (e.g., SQS queue URLs embedded in Lambda event source configs), the default `localhost` hostname in generated URLs is unreachable from sibling containers. Setting `FLOCI_HOSTNAME=floci` (the Compose service name) fixes internal URL generation. MiniStack doesn't document an equivalent — standard Docker Compose service name resolution applies. [`[Floci configuration]`](https://floci.io/floci/configuration/application-yml/)

---

### 3. LocalStack-Specific Tooling: What Breaks, What Doesn't

#### `LOCALSTACK_AUTH_TOKEN`
**Action required**: Delete entirely. Neither Floci nor MiniStack implement any auth token system. Setting this env var has no effect but harmlessly lingers. [`[Floci README]`](https://github.com/floci-io/floci) [`[MiniStack README]`](https://github.com/ministackorg/ministack)

#### `AWS_ENDPOINT_URL` — The Universal Wrapper Replacement

Both projects' documentation points to `export AWS_ENDPOINT_URL=http://localhost:4566` as the primary no-wrapper migration path. This variable **IS** officially supported by AWS CLI v2 (sets a global endpoint for all service calls) and by boto3/botocore — officially confirmed by [AWS CLI env vars documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html#envvars-list-AWS_ENDPOINT_URL):

> *"Specifies the endpoint that is used for all service requests."*

This means the entire class of LocalStack-specific wrapper scripts becomes unnecessary once this variable is set. [`[AWS CLI docs]`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html)

#### `awslocal` CLI wrapper (from `localstack-client` Python package)
**What breaks**: `awslocal` injects `--endpoint-url` and dummy credentials into every `aws` CLI invocation. It's distributed via `pip install localstack-client` and ties to LocalStack internals.

| Tool | Replacement |
|------|-------------|
| **Floci** | No bundled replacement. Canonical path: `export AWS_ENDPOINT_URL=http://localhost:4566` + plain `aws` CLI. |
| **MiniStack** | Ships its own `bin/awslocal` wrapper (same concept — injects endpoint + credentials). A direct executable swap. |

**Important caveat**: The `localstack-client` PyPI package should **not** remain installed alongside Floci or MiniStack. It may make startup calls to LocalStack management APIs (`/_localstack/init`, health probes) that will fail against a different emulator. [`[MiniStack README, awslocal section]`](https://github.com/ministackorg/ministack)

#### `tflocal` (terraform-local) Terraform wrapper
**What breaks**: `tflocal` is a Python script that wraps `terraform` and dynamically injects LocalStack endpoint URLs into each service endpoint in your AWS provider configuration at runtime.

**Replacement (identical for both tools)**: `tflocal` is not needed. Configure the AWS provider directly:

```hcl
# Option A: Explicit endpoints block (works with all Terraform AWS Provider versions)
provider "aws" {
  access_key = "test"
  secret_key = "test"
  region     = "us-east-1"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  endpoints {
    s3       = "http://localhost:4566"
    dynamodb = "http://localhost:4566"
    sqs      = "http://localhost:4566"
    lambda   = "http://localhost:4566"
    # ... all required services
  }
}

# Option B: AWS_ENDPOINT_URL env var (Terraform AWS Provider ≥ 5.0)
# Just export AWS_ENDPOINT_URL=http://localhost:4566 before running terraform
```

The `AWS_ENDPOINT_URL` global override (Option B) is significantly simpler — no per-service endpoints block needed. Neither Floci nor MiniStack ships a `tflocal`-equivalent wrapper. [`[MiniStack Terraform docs]`](https://ministack.org) [`[Floci README]`](https://floci.io/)

#### `cdklocal` (aws-cdk-local) CDK wrapper
**What breaks**: `cdklocal` wraps the CDK CLI and configures local endpoint URLs. Internally it reads `LOCALSTACK_HOST` and may call LocalStack-specific management endpoints.

**Replacement**:
- **Simplest**: Remove `cdklocal`; set `AWS_ENDPOINT_URL=http://localhost:4566`; use standard `cdk` CLI.
- **Workaround** (if CI scripts use `cdklocal` verbatim): `cdklocal` may work against Floci/MiniStack if `LOCALSTACK_HOST=localhost:4566` is set, since it only configures endpoint URLs. However this is untested and relies on `cdklocal` not making LocalStack management API calls during CDK bootstrapping. **Confidence: Low** — direct `cdk` + `AWS_ENDPOINT_URL` is the verified path.

#### Testcontainers LocalStack module (Java)
This is the **highest-friction migration point** and differs significantly between the two tools.

**LocalStack pattern**:
```java
LocalStackContainer localstack = new LocalStackContainer(
    DockerImageName.parse("localstack/localstack:4.14.0"))
  .withServices(S3, SQS, DYNAMODB);
localstack.start();
```

**Floci path** — two options:

*Option A: Official Floci module (recommended)* [`[Testcontainers Floci module]`](https://testcontainers.com/modules/floci/)
```xml
<dependency>
    <groupId>io.floci</groupId>
    <artifactId>testcontainers-floci</artifactId>
    <version>2.0.0</version>
    <scope>test</scope>
</dependency>
```
```java
FlociContainer floci = new FlociContainer();
floci.start();
```
Services cannot be selectively activated — all 35 services are always on. This removes the `withServices()` call entirely.

*Option B: Compatible substitute (minimal code change, with gotchas)*  [`[Spring Boot Floci Testcontainers blog]`](https://ttlnews.blogspot.com/2026/04/alternatives-for-localstack-in.html)
```java
DockerImageName.parse("floci/floci:1.5.7")
  .asCompatibleSubstituteFor("localstack/localstack")
```
**Breaking change**: Floci does NOT log the LocalStack readiness string (`".*Ready\\.\\n"`). Must override wait strategy:
```java
.waitingFor(new LogMessageWaitStrategy()
    .withRegEx(".*started in.*").withTimes(1))
```
Also requires a custom startup-script override for the native binary (different from LocalStack's bash entrypoint). This is non-trivial. Option A is strongly preferred.

**MiniStack path** — official module, cleanest migration [`[testcontainers-ministack GitHub]`](https://github.com/ministackorg/testcontainers-ministack):
```xml
<dependency>
    <groupId>org.ministack</groupId>
    <artifactId>testcontainers-ministack</artifactId>
    <version>0.1.3</version>
    <scope>test</scope>
</dependency>
```
```java
try (MiniStackContainer ministack = new MiniStackContainer()) {
    ministack.start();
    String endpoint = ministack.getEndpoint();
    // Use endpoint for SDK configuration
}
// Spring Boot @ServiceConnection supported
```
Health check is automatic; `getEndpoint()`, `getRegion()`, `getAccessKey()`, `getSecretKey()` provide SDK config. Docker socket mount via `.withRealInfrastructure()` enables RDS/ElastiCache/ECS containers. This is the most direct LocalStack module replacement of the two options.

---

### 4. Health Check Endpoint: Split Behavior

| Endpoint | LocalStack | Floci | MiniStack |
|----------|-----------|-------|-----------|
| `GET /_localstack/health` | ✅ | ❌ (404) | ✅ (compatibility alias) |
| `GET /_floci/health` | ❌ | ✅ | ❌ |
| `GET /_ministack/health` | ❌ | ❌ | ✅ |
| `GET /health` | ✅ (partial) | ❌ | ✅ |

**Floci requires a health check URL update** in Docker Compose `healthcheck` directives, Kubernetes readiness probes, and CI wait scripts. MiniStack is a drop-in for scripts that poll `/_localstack/health`. [`[MiniStack README, health section]`](https://github.com/ministackorg/ministack)

---

### 5. Persistence, Init Scripts, and Env Var Renames

| Config Dimension | LocalStack | Floci | MiniStack |
|---|---|---|---|
| Data persistence flag | `PERSISTENCE=1` | `FLOCI_STORAGE_MODE=hybrid\|persistent\|wal` | `S3_PERSIST=1` (S3 only) |
| Data volume path | `/var/lib/localstack` | `/app/data` | Not documented for general state |
| Init scripts path | `/etc/localstack/init/ready.d/` | `/etc/floci/init/start.d/` | `boot.d` / `ready.d` via reset API |
| Default region var | `DEFAULT_REGION` | `FLOCI_DEFAULT_REGION` | `MINISTACK_REGION` |
| Account ID var | `AWS_ACCOUNT_ID` | `FLOCI_DEFAULT_ACCOUNT_ID` | `MINISTACK_ACCOUNT_ID` |
| Debug/logging | `DEBUG=1`, `LS_LOG` | Quarkus `quarkus.log.level` | Not documented |

**Floci persistence advantage**: Four storage modes (`memory`, `persistent`, `hybrid` [default], `wal`) — more granular than LocalStack's single flag. [`[Floci storage docs]`](https://floci.io/floci/configuration/application-yml/)

**MiniStack persistence gap**: Only S3 in-memory persistence is configurable; general cross-service persistence behavior is not documented. Teams relying on `PERSISTENCE=1` for DynamoDB or SQS state across restarts face an unresolved gap with MiniStack. **Confidence: Medium** — the README does not address this explicitly.

---

## Evidence

| Data Point | Value | Source |
|---|---|---|
| Floci port | 4566 | [GitHub README](https://github.com/floci-io/floci) |
| MiniStack port | 4566 (GATEWAY_PORT configurable) | [GitHub README](https://github.com/ministackorg/ministack) |
| `AWS_ENDPOINT_URL` officially supported by AWS CLI v2 | Yes — "Specifies the endpoint that is used for all service requests" | [AWS CLI env vars docs](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) |
| Floci Testcontainers module | `io.floci:testcontainers-floci:2.0.0` | [testcontainers.com/modules/floci](https://testcontainers.com/modules/floci/) |
| MiniStack Testcontainers module | `org.ministack:testcontainers-ministack:0.1.3` | [ministackorg/testcontainers-ministack](https://github.com/ministackorg/testcontainers-ministack) |
| Floci wait-for-ready log regex | `".*started in.*"` (NOT LocalStack's `".*Ready\\.\\n"`) | [Spring Boot Floci migration blog](https://ttlnews.blogspot.com/2026/04/alternatives-for-localstack-in.html) |
| Floci canonical Docker image | `floci/floci:latest` (moved from `hectorvent/floci`) | [GitHub README, Important banner](https://github.com/floci-io/floci) |
| MiniStack `/_localstack/health` alias | Yes | [GitHub README](https://github.com/ministackorg/ministack) |
| Floci health endpoint | `/_floci/health` | [Web search corroboration](https://www.keydrop.net/posts/floci-getting-started/) |
| Floci init hooks path | `/etc/floci/init/start.d/` | [Floci configuration docs](https://floci.io/floci/configuration/application-yml/) |
| MiniStack awslocal wrapper | Bundled at `bin/awslocal` | [GitHub README](https://github.com/ministackorg/ministack) |
| Floci `FLOCI_HOSTNAME` config key | Required for multi-container Docker networking | [Floci application.yml reference](https://floci.io/floci/configuration/application-yml/) |
| MiniStack API Gateway v1 | ✅ Supported (REST APIs, Lambda proxy, MOCK integrations) | [ministack.org service list](https://ministack.org/) |
| MiniStack total services | 41 (as of April 2026) | [ministack.org](https://ministack.org/) |

---

## Trade-offs

### When Floci is harder to migrate to
**Testcontainers-heavy Java projects** face the most friction with Floci. The `LocalStackContainer.withServices()` API has no equivalent in `FlociContainer`; the compatibility-substitute path requires a custom subclass with a different startup script and a different wait regex. Teams with extensive Spring Boot integration test suites using `@LocalStackContainer` will need a deliberate rewrite. The MiniStack module's `@ServiceConnection` support and clean constructor API make it the lower-effort Testcontainers migration.

**Health check automation** in existing CI pipelines, Docker Compose `healthcheck:` blocks, or Kubernetes readiness probes that poll `/_localstack/health` will 404 silently on Floci until updated to `/_floci/health`. This is an invisible failure mode — the container appears running but health checks report unhealthy.

### When MiniStack is harder to migrate to
**Persistence-dependent workflows** have an unresolved gap. If your local development workflow relies on `PERSISTENCE=1` to preserve DynamoDB tables, SQS queues, or Lambda functions across container restarts (common in long-running dev environments where `docker compose up/down` is frequent), MiniStack's documented persistence is limited to S3 only. Floci's `FLOCI_STORAGE_MODE=hybrid` (the default) persists all stateful services to disk and survives container restarts — a closer match to LocalStack's persistence behavior.

**Multi-container Docker Compose networking** is subtly simpler with Floci because `FLOCI_HOSTNAME` explicitly controls the hostname embedded in generated URLs (SQS queue URLs, SNS subscription endpoints, pre-signed S3 URLs). Without this override, Lambda functions running inside Docker Compose that need to call back to the emulator via a generated URL will fail. MiniStack's behavior for this case is not documented.

### When both require work
**Terraform workflows using `tflocal`**: Both require replacing `tflocal` with either explicit `endpoints {}` blocks or `AWS_ENDPOINT_URL` injection. This is a one-time change per Terraform root module, but in large IaC repositories with many modules it can be tedious. The `AWS_ENDPOINT_URL` path is simpler but requires Terraform AWS Provider ≥ 5.0.

**CDK local development**: Neither tool provides a `cdklocal` equivalent. `AWS_ENDPOINT_URL` works for basic CDK deployments but CDK bootstrapping involves CloudFormation stack creation with cross-service interactions that may expose compatibility gaps not covered by the simpler integration tests either project publishes.

---

## Confidence

| Conclusion | Confidence | Rationale |
|---|---|---|
| Port 4566 drop-in at AWS wire protocol level | **High** | Both official READMEs and all SDK examples use port 4566; no alternative ports documented |
| `AWS_ENDPOINT_URL` works without wrapper scripts | **High** | Official AWS CLI docs confirm; both projects' own quick-start examples confirm |
| Floci does NOT support `/_localstack/health` | **High** | MiniStack explicitly states compatibility alias; Floci documentation makes no mention of it; community blog confirmed `/_floci/health` |
| MiniStack `/_localstack/health` alias works | **High** | Explicitly documented in MiniStack README |
| Floci Testcontainers wait-regex is `".*started in.*"` | **Medium-High** | Confirmed by Spring Boot migration blog post with code; cross-checked against log output shown in same post |
| MiniStack general state persistence (non-S3) | **Unresolved** | README only documents `S3_PERSIST=1`; no evidence for or against DynamoDB/SQS persistence across restarts |
| `cdklocal` works against Floci/MiniStack via `LOCALSTACK_HOST` | **Low** | No documented evidence; CDK bootstrapping calls may hit LocalStack-specific management endpoints |
| `tflocal` is replaceable with `AWS_ENDPOINT_URL` | **High** | `tflocal` is a pure endpoint-injection wrapper; `AWS_ENDPOINT_URL` achieves the same result with Terraform AWS Provider ≥ 5.0 |

---

## New Questions

1. **CDK bootstrapping compatibility**: CDK's `cdk bootstrap` creates a CloudFormation stack that cross-references S3, IAM, SSM, and ECR. Does this multi-service interaction work end-to-end against Floci or MiniStack, or does it fail at specific CloudFormation resource types? A test running `cdk bootstrap --app '...'` against both tools would provide a definitive answer for CDK-heavy shops.

2. **MiniStack cross-restart persistence**: Does `MINISTACK_REGION=us-east-1 docker compose up` followed by `docker compose down` followed by `docker compose up` preserve DynamoDB tables and SQS queues? The README's silence on this is a practical blocker for dev-environment workflows where developers expect to restart the emulator without losing local state.

3. **`localstack-client` call interference**: When `pip install localstack-client` remains installed in a Python project (common in teams doing incremental migration), does boto3/awslocal in that environment make startup calls that fail against Floci or MiniStack in ways that are not obvious error messages? A test recording the HTTP calls `localstack-client` makes at import time and checking which ones 404 against each emulator would make this failure mode explicit.

<task_complete>
<parameter name="summary">## Research Report: Migration Effort from LocalStack to Floci / MiniStack

### Key Findings

**Both tools are true port-4566 drop-ins at the AWS wire protocol level** — no application SDK code changes required. The migration cost is almost entirely in DevOps/tooling configuration, not application logic.

---

### Endpoint Configuration Changes

Both Floci and MiniStack use **port 4566** with identical AWS wire protocols. The SDK config (`endpoint_url="http://localhost:4566"`) is unchanged.

**Docker Compose swap** (minimal):
- **Floci**: `image: floci/floci:latest` + remove `LOCALSTACK_AUTH_TOKEN` + remove `SERVICES=...` + set `FLOCI_HOSTNAME: floci` for multi-container networking + remap volume from `/var/lib/localstack` → `/app/data`
- **MiniStack**: `image: ministackorg/ministack:latest` + remove `LOCALSTACK_AUTH_TOKEN` + remove `SERVICES=...`

---

### LocalStack-Specific Features: What Breaks

| Feature | Floci Migration | MiniStack Migration |
|---|---|---|
| `LOCALSTACK_AUTH_TOKEN` | Delete (not needed) | Delete (not needed) |
| `SERVICES=s3,sqs,...` | Delete (all services auto-start) | Delete (all services auto-start) |
| `awslocal` CLI wrapper | Replace with `export AWS_ENDPOINT_URL=http://localhost:4566` + plain `aws` CLI (AWS CLI v2 supports this natively per [official docs](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html)) | Use bundled `bin/awslocal` wrapper OR same `AWS_ENDPOINT_URL` approach |
| `tflocal` wrapper | Remove; use `endpoints {}` block in provider OR `AWS_ENDPOINT_URL` (Terraform AWS Provider ≥ 5.0) | Same |
| `cdklocal` wrapper | Remove; set `AWS_ENDPOINT_URL=http://localhost:4566`; use `cdk` directly | Same |
| Testcontainers LocalStack module | Use `io.floci:testcontainers-floci:2.0.0` — new `FlociContainer` class; wait strategy changes from `".*Ready\\.\\n"` to `".*started in.*"` | Use `org.ministack:testcontainers-ministack:0.1.3` — `MiniStackContainer` with `getEndpoint()`; Spring Boot `@ServiceConnection` supported |
| `/_localstack/health` endpoint | **Breaking**: must update to `/_floci/health` | **Compatible**: alias works unchanged |
| `/var/lib/localstack` volume | Remap to `/app/data`; use `FLOCI_STORAGE_MODE=hybrid` for persistence | `S3_PERSIST=1` for S3; general persistence **unresolved** |
| Init scripts `/etc/localstack/init/ready.d/` | Remap to `/etc/floci/init/start.d/` | `boot.d`/`ready.d` via reset API |

---

### Summary Assessment

**Floci** migration is slightly higher friction than MiniStack due to: (1) health check URL must change, (2) Testcontainers requires a non-trivial startup script + wait strategy override if using compatibility mode, and (3) `FLOCI_HOSTNAME` must be set for multi-container Compose networking. Persistence across container restarts is well-supported via `FLOCI_STORAGE_MODE=hybrid` (the default).

**MiniStack** is the lower-effort migration overall: health check endpoint maintains LocalStack compatibility alias, the Testcontainers module provides a clean modern API, and the bundled `awslocal` wrapper reduces the `localstack-client` replacement effort. The gap is general state persistence (non-S3), which is undocumented and unresolved.

For **Testcontainers-heavy Java/Spring Boot shops**, MiniStack's module is meaningfully cleaner. For **persistence-dependent dev environments**, Floci's storage modes are more complete.
</parameter>
</invoke>

---

## Peer Review (codex-cli)

### Issue 1: LocalStack `SERVICES` is mischaracterized as required
- **Type**: factual error
- **Location**: “**LocalStack required an explicit service-allowlist.** Both replacements start all services automatically…”
- **Problem**: That overstates LocalStack behavior. LocalStack’s config docs say `SERVICES` only restricts loading **if it is set**; it is not generally required. So the migration is not “remove a required allowlist,” but “remove an optional compatibility/perf setting if you used it.”  
  Sources: [LocalStack configuration](https://docs.localstack.cloud/references/configuration/)
- **Impact**: It inflates the migration delta and weakens trust in the comparison.

### Issue 2: The `awslocal` package is misidentified
- **Type**: factual error
- **Location**: “#### `awslocal` CLI wrapper (**from `localstack-client` Python package**)”
- **Problem**: `awslocal` is distributed by **`awscli-local`**, not `localstack-client`. The PyPI page for `awscli-local` explicitly states it provides the `awslocal` command.  
  Sources: [awscli-local PyPI](https://pypi.org/project/awscli-local/), [localstack-client PyPI](https://pypi.org/project/localstack-client/)
- **Impact**: It undermines the tooling analysis and makes the follow-on claims about package interference suspect.

### Issue 3: Claim that `localstack-client` may hit management APIs is unsupported and likely misattributed
- **Type**: unsupported claim
- **Location**: “The `localstack-client` PyPI package should **not** remain installed… It may make startup calls to LocalStack management APIs…”
- **Problem**: No evidence is provided, and the wrapper under discussion is the wrong package. The cited MiniStack README does not establish this claim. The risk may exist for some LocalStack tools, but this specific statement is not supported here.
- **Impact**: This creates a migration warning without proof, which is exactly the kind of claim a reviewer should reject.

### Issue 4: MiniStack *does* document a hostname override equivalent to `FLOCI_HOSTNAME`
- **Type**: factual error
- **Location**: “**MiniStack doesn't document an equivalent** — standard Docker Compose service name resolution applies.”
- **Problem**: MiniStack documents `MINISTACK_HOST` as the hostname used in response URLs such as SQS queue URLs and SNS/API Gateway URLs. That is directly relevant and is the equivalent concept the report says is absent.  
  Sources: [MiniStack README](https://github.com/ministackorg/ministack)
- **Impact**: This distorts one of the key migration differences and makes Floci look uniquely better in multi-container networking when MiniStack also exposes a knob.

### Issue 5: MiniStack persistence is no longer an “unresolved gap”
- **Type**: factual error
- **Location**: “MiniStack persistence gap… documented persistence is limited to **S3 only**” and “general cross-service persistence behavior is **not documented**.”
- **Problem**: The current MiniStack README documents `PERSIST_STATE=1` and says persistence applies to **all services**, explicitly listing DynamoDB, SQS, Lambda, RDS, etc. `S3_PERSIST=1` exists, but it is not the whole story anymore.  
  Sources: [MiniStack README](https://github.com/ministackorg/ministack)
- **Impact**: This materially changes the migration assessment. One of the report’s main arguments against MiniStack is based on outdated evidence.

### Issue 6: Floci storage default is internally inconsistent, but the report presents one side as fact
- **Type**: contradiction
- **Location**: “Floci’s `FLOCI_STORAGE_MODE=hybrid` **(the default)**…” and “Four storage modes (`memory`, `persistent`, `hybrid` [default], `wal`).”
- **Problem**: Floci’s official sources disagree. The README says hybrid is the default, but the configuration docs show `storage.mode: memory` as the shipped default. The report should flag this discrepancy instead of asserting one version as settled fact.  
  Sources: [Floci README](https://github.com/floci-io/floci), [Floci application.yml reference](https://floci.io/floci/configuration/application-yml/)
- **Impact**: It weakens confidence in the persistence section and the final trade-off analysis.

### Issue 7: The Terraform `AWS_ENDPOINT_URL` conclusion is not adequately supported
- **Type**: unsupported claim
- **Location**: “`AWS_ENDPOINT_URL` global override (Option B)… **works with Terraform AWS Provider ≥ 5.0**”
- **Problem**: The evidence cited is AWS CLI documentation, not Terraform AWS Provider documentation. MiniStack’s own Terraform section still shows a full `endpoints {}` block. That does not prove the provider universally honors `AWS_ENDPOINT_URL` the way the AWS CLI does.  
  Sources: [AWS CLI env vars](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html), [AWS SDKs/tools endpoint docs](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html), [MiniStack README](https://github.com/ministackorg/ministack)
- **Impact**: This overstates a simplification path that may not be reliable for Terraform users.

### Issue 8: `AWS_ENDPOINT_URL` support is sourced too narrowly and described too broadly
- **Type**: missing nuance
- **Location**: “This variable **IS** officially supported by AWS CLI v2… and by boto3/botocore — officially confirmed by AWS CLI env vars documentation”
- **Problem**: AWS CLI docs confirm CLI behavior, not boto3 specifically. The broader authoritative source is the AWS SDKs-and-tools endpoint settings page, which shows support varies by SDK/tool and follows precedence rules. The report should cite that broader source and be careful not to treat CLI docs as proof for every SDK/runtime.  
  Sources: [AWS CLI env vars](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html), [AWS SDKs and Tools endpoint settings](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html)
- **Impact**: It over-certifies a cross-tool behavior using the wrong source.

### Issue 9: Docker socket requirements are inaccurately summarized
- **Type**: factual error
- **Location**: Compose examples comment that Docker socket is required for “**Lambda/RDS/ECS**” for both tools.
- **Problem**: For Floci, the official Docker Compose docs call out **Lambda, ElastiCache, and RDS**. For MiniStack, the README calls out **RDS, ECS, Lambda** in one place, and also notes **EKS** needs Docker socket access. The report’s shorthand is inconsistent with the docs and omits relevant services.  
  Sources: [Floci Docker Compose docs](https://floci.io/floci/configuration/docker-compose/), [MiniStack README](https://github.com/ministackorg/ministack)
- **Impact**: Readers may under-provision or misunderstand which services need Docker integration.

### Issue 10: The Floci health endpoint claim is weakly sourced
- **Type**: unsupported claim
- **Location**: “Floci health endpoint | `/_floci/health`” and “Floci requires a health check URL update…”
- **Problem**: The evidence table admits this comes from “Web search corroboration,” not Floci’s official docs/README. I did not find official Floci docs clearly documenting `/_floci/health`. That doesn’t prove the claim is false, but it is not strong enough to anchor a key migration recommendation.
- **Impact**: One of the report’s central “breaking changes” rests on weak sourcing.

### Issue 11: The LocalStack `/health` comparison lacks source support and historical nuance
- **Type**: unsupported claim
- **Location**: Health table row: “`GET /health` | LocalStack ✅ (partial)”
- **Problem**: Current LocalStack internal-endpoint docs emphasize `/_localstack/health`, not plain `/health`. Older LocalStack packaging did expose `/health`, so the statement may be historically true in some versions, but the report gives no versioning nuance and no citation for the “partial” claim.  
  Sources: [LocalStack internal endpoints](https://docs.localstack.cloud/aws/capabilities/config/internal-endpoints/), [older LocalStack PyPI docs](https://pypi.org/project/localstack/0.12.18.2/)
- **Impact**: The health-check compatibility section mixes version-specific behavior with current migration advice.

### Issue 12: LocalStack config variable mapping is partly wrong
- **Type**: factual error
- **Location**: Table row: “Account ID var | LocalStack `AWS_ACCOUNT_ID`”
- **Problem**: LocalStack account namespacing is tied to `AWS_ACCESS_KEY_ID` patterns; its config docs do not present `AWS_ACCOUNT_ID` as the LocalStack account-ID control in the way this table implies. `AWS_ACCOUNT_ID` is an AWS CLI/SDK endpoint-related variable, not the right LocalStack analog here.  
  Sources: [LocalStack credentials](https://docs.localstack.cloud/aws/capabilities/config/credentials/), [LocalStack multi-account setups](https://docs.localstack.cloud/aws/capabilities/config/multi-account-setups/)
- **Impact**: The env-var rename table is less reliable than it appears.

### Issue 13: “No application code changes” is too absolute
- **Type**: missing nuance
- **Location**: “**No application code changes are required to switch**…”
- **Problem**: At the simplest SDK endpoint level, that is often true. But the report itself later documents cases where generated URLs, health endpoints, init hooks, Testcontainers, and possibly CDK/Terraform behavior differ. Some apps also rely on emulator-specific behavior around queue URLs, account IDs, path-style S3, or unsupported APIs. “Often no SDK-call changes” would be safer than a blanket statement.
- **Impact**: It oversells the migration ease up front, then walks it back later.

### Issue 14: The Testcontainers section leans on secondary evidence where primary evidence should exist
- **Type**: unsupported claim
- **Location**: Floci “compatible substitute” path, custom startup-script requirement, and wait-regex claim sourced to a blog.
- **Problem**: For a technical migration report, this should come from the Floci Testcontainers module docs or code, not a third-party blog. The official Testcontainers page confirms the module exists, but not the compatibility-substitute details the report treats as established.  
  Sources: [Testcontainers Floci module](https://testcontainers.com/modules/floci/)
- **Impact**: The most “high-friction” migration point in the report is partly built on non-primary evidence.

---

## Summary
- **Issues found**: 14
- **Overall reliability assessment**: **medium-low**

### What would most improve the findings
1. Re-verify every operational claim against **current primary docs** for Floci, MiniStack, LocalStack, AWS, and Terraform.
2. Fix the **clear factual errors**: `SERVICES`, `awslocal` package, MiniStack hostname override, MiniStack persistence, LocalStack account-ID variable.
3. Separate **verified behavior** from **inference/untested migration advice**.
4. Add **version/date qualifiers** wherever behavior may have changed recently.

Primary sources used: [Floci README](https://github.com/floci-io/floci), [Floci docs](https://floci.io/floci/services/), [MiniStack README](https://github.com/ministackorg/ministack), [AWS CLI env vars](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html), [AWS SDKs/tools endpoint settings](https://docs.aws.amazon.com/sdkref/latest/guide/feature-ss-endpoints.html), [LocalStack configuration](https://docs.localstack.cloud/references/configuration/), [LocalStack internal endpoints](https://docs.localstack.cloud/aws/capabilities/config/internal-endpoints/), [awscli-local PyPI](https://pypi.org/project/awscli-local/).
