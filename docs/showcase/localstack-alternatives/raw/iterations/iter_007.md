# Iteration 007 — Migration effort estimation by team profile and IaC toolchain

**Status:** keep  
**Scores:** coverage=76.2, quality=55.0, total=63.5  
**Timestamp:** 2026-04-24T12:37:05.097413+00:00  

---

---

## Findings

### 1. The Core Migration Invariant: Port 4566, Dummy Credentials, One Endpoint

Both Floci and MiniStack listen on **port 4566** and accept any dummy credentials. Every AWS SDK endpoint override (`endpoint_url`, `endpointOverride`, `BaseEndpoint`, `--endpoint-url`) that previously pointed at LocalStack points at the new emulator unchanged. **Zero application code changes are required** for pure SDK call sites — this is the genuine drop-in layer.

The three layers that *do* require changes are:
1. The Docker Compose / container configuration
2. The CI pipeline secrets and service blocks  
3. The IaC toolchain wrapper (CDK specifically)

---

### 2. Terraform-First Teams

#### Before/After: Docker Compose

**Before (LocalStack):**
```yaml
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      LOCALSTACK_AUTH_TOKEN: ${LOCALSTACK_AUTH_TOKEN}
      SERVICES: s3,sqs,dynamodb,lambda
    volumes:
      - ./init:/etc/localstack/init/ready.d
      - /var/run/docker.sock:/var/run/docker.sock
```

**After (Floci):**
```yaml
services:
  floci:
    image: floci/floci:latest       # ← changed (was hectorvent/floci; now floci/floci)
    ports:
      - "4566:4566"                 # ← no change
    environment:
      FLOCI_HOSTNAME: floci         # ← add only for multi-container Compose setups
      # SERVICES and LOCALSTACK_AUTH_TOKEN → deleted
    volumes:
      - ./init/start.d:/etc/floci/init/start.d:ro   # ← path changed
      - /var/run/docker.sock:/var/run/docker.sock    # ← only if Lambda/RDS/ElastiCache
```

**After (MiniStack):**
```yaml
services:
  ministack:
    image: ministackorg/ministack   # ← changed
    ports:
      - "4566:4566"                 # ← no change
    environment:
      MINISTACK_HOST: ministack     # ← add only for multi-container Compose setups
      # SERVICES and LOCALSTACK_AUTH_TOKEN → deleted
    volumes:
      - ./boot.d:/app/boot.d:ro    # ← path changed
      - /var/run/docker.sock:/var/run/docker.sock    # ← only if Lambda Docker/RDS/ECS
```

**Touch points:** 1 Compose file, 1 CI secret deletion (`LOCALSTACK_AUTH_TOKEN`).

#### Before/After: Terraform Provider Block

**Both Floci and MiniStack require zero changes to the Terraform provider block.** All services remain on `http://localhost:4566`. The full provider block from the MiniStack README and verified against Floci's `compat-terraform` test suite:

```hcl
provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true    # renamed from s3_force_path_style in provider v4+
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    s3             = "http://localhost:4566"
    sqs            = "http://localhost:4566"
    dynamodb       = "http://localhost:4566"
    lambda         = "http://localhost:4566"
    iam            = "http://localhost:4566"
    sts            = "http://localhost:4566"
    cloudformation = "http://localhost:4566"
    # ... every service at the same URL
  }
}
```

#### Floci's Validated Terraform Surface

Floci's [`compat-terraform`](https://github.com/floci-io/floci/tree/main/compatibility-tests/compat-terraform) test suite (14 bats-based CI tests against Terraform v1.10+) provisions and validates: **S3 bucket with versioning, SQS queue with DLQ + redrive policy, SNS topic with SQS subscription, DynamoDB table with TTL + tags, IAM role for Lambda, SSM parameters (String + SecureString), Secrets Manager secret + version, RDS DB instance, Cognito User Pool, CloudWatch metric alarm.** These pass in Floci's CI. An equivalent `compat-opentofu` suite covers OpenTofu v1.9+.

**MiniStack's Terraform coverage** is wider by count (the README lists 38+ service endpoints in the example block including ECS, ELBv2, EMR, EFS, WAF) but has **no equivalent committed CI compat test suite** — coverage is documented via the README and the 1,300+ unit tests, not an IaC integration test.

#### Predictable API Gateway IDs

If the existing LocalStack config uses `ls-custom-id` tags to pin API Gateway IDs across `terraform apply` runs, this **must be updated** to `ms-custom-id` for both tools. The `ls-custom-id` tag is explicitly rejected with `BadRequestException (400)` by MiniStack; Floci similarly documents only `ms-custom-id`. This is **the one Terraform file change** that may be required beyond the Compose config.

---

### 3. CDK/SAM Teams

This is where the migration paths **diverge most significantly**.

#### Floci CDK Path — Requires `cdklocal` Wrapper

From direct source analysis of [`compat-cdk/run.sh`](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-cdk/run.sh):

```bash
export AWS_ENDPOINT_URL="$FLOCI_ENDPOINT"
export AWS_ENDPOINT_URL_S3="$FLOCI_ENDPOINT"
# CDK-specific: derive hostname and port from endpoint
export LOCALSTACK_HOSTNAME="${FLOCI_ENDPOINT#http://}"
export LOCALSTACK_HOSTNAME="${LOCALSTACK_HOSTNAME%:*}"   # → "localhost"
export EDGE_PORT="${FLOCI_ENDPOINT##*:}"                  # → "4566"
```

And the test executes `cdklocal bootstrap --force` / `cdklocal deploy --require-approval never`.

**Translation:** Floci's CDK compatibility still depends on the `cdklocal` CLI wrapper (`aws-cdk-local` npm package), which reads `LOCALSTACK_HOSTNAME` and `EDGE_PORT`. Teams migrating from LocalStack to Floci **retain the same `cdklocal` dependency** and the same LocalStack-derived env vars, but remove `LOCALSTACK_AUTH_TOKEN`. This is the lowest-friction CDK migration if the team already has `cdklocal` installed.

**What the CDK compat suite validates (17 tests):** S3 bucket creation, SQS queue creation, DynamoDB table with GSI + LSI, CloudFormation stack `CREATE_COMPLETE`, Secrets Manager `GeneratedSecret` CRUD, **`DockerImageFunction` (ECR + Lambda image) push and invocation end-to-end**. This last test confirms that CDK asset upload via presigned S3 URL → ECR → Lambda invocation works in Floci's CI.

**Bootstrap procedure for Floci:**
```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export LOCALSTACK_HOSTNAME=localhost
export EDGE_PORT=4566
cdklocal bootstrap --force
cdklocal deploy --require-approval never
```

**Risk — CloudFormation event source wiring:** Per the prior analysis, Floci's CloudFormation provisioner stubs `AWS::Lambda::EventSourceMapping` and `AWS::Lambda::Permission` — these resource types return `CREATE_COMPLETE` silently without actual API calls. CDK stacks that wire SQS → Lambda or SNS → Lambda **through CloudFormation** will deploy without errors but the event routing will not be established. Lambda functions invocable directly will work; trigger-based invocations via event source mappings in CloudFormation **will not fire**.

**Risk — `cdklocal` wrapper dependency:** `cdklocal` is maintained by LocalStack, Inc. If it evolves to enforce LocalStack-specific validation (e.g., reject non-LocalStack backends), Floci's CDK path breaks. As of April 2026 this has not occurred, but it is a structural dependency.

#### MiniStack CDK Path — Plain `cdk` + `AWS_ENDPOINT_URL`

From the MiniStack README:
```bash
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cdk bootstrap aws://000000000000/us-east-1
cdk deploy --require-approval never
```

**No `cdklocal` wrapper.** No `LOCALSTACK_HOSTNAME`. No `EDGE_PORT`. CDK v2 uses AWS SDK v3 internally, which honors `AWS_ENDPOINT_URL` natively.

**Migration delta vs LocalStack CDK (using `cdklocal`):**
- Remove `cdklocal` package (or keep it, run plain `cdk` instead)
- Replace `cdklocal bootstrap` → `cdk bootstrap aws://000000000000/us-east-1`
- Replace `cdklocal deploy` → `cdk deploy --require-approval never`
- Remove `LOCALSTACK_HOSTNAME`, `EDGE_PORT`, `LOCALSTACK_AUTH_TOKEN`
- Add `AWS_ENDPOINT_URL=http://localhost:4566`

**CloudFormation event source wiring:** MiniStack's CFN provisioner creates `AWS::Lambda::Permission` (calls `AddPermission`) and `AWS::Lambda::EventSourceMapping` (calls `CreateEventSourceMapping`) as documented resource types in the README resource matrix. Unsupported types fail with `CREATE_FAILED` rather than silently succeeding. CDK stacks with SQS → Lambda triggers deployed via CloudFormation **will wire correctly**, making MiniStack materially lower-risk for CDK/SAM teams that use CloudFormation to configure event sources.

**Cross-stack exports:** MiniStack supports `Fn::ImportValue` and `ListExports`, enabling multi-stack CDK apps to reference outputs across stacks. No equivalent confirmation was found in Floci's documentation.

**Bootstrap idempotency risk (unverified):** Whether `cdk bootstrap` running twice against MiniStack correctly detects the existing `CDKToolkit` stack and no-ops (the real-world CDK bootstrap idempotency path) has not been independently validated. MiniStack documents `UpdateStack` and `DescribeStacks`, which are the operations CDK uses for detection, but end-to-end idempotency has not been source-confirmed.

#### SAM Teams

**LocalStack pattern:**
```bash
export LOCALSTACK_AUTH_TOKEN=token
samlocal deploy --stack-name my-stack --capabilities CAPABILITY_IAM
```

**Floci path:** The `samlocal` wrapper (from the `aws-sam-cli-local` package, LocalStack-maintained) sets `LOCALSTACK_HOSTNAME` and `EDGE_PORT` similarly to `cdklocal`. Floci's API compatibility on port 4566 should allow `samlocal` to work, but **no official Floci SAM test suite exists**. The event source wiring silent-stub risk applies to SAM deployments as well — `sam deploy` creates CloudFormation stacks, and Floci will stub `Lambda::EventSourceMapping` silently.

**MiniStack path:**
```bash
export AWS_ENDPOINT_URL=http://localhost:4566
sam deploy --stack-name my-stack --capabilities CAPABILITY_IAM
```

SAM CLI honors `AWS_ENDPOINT_URL` for CloudFormation and S3 uploads. Since MiniStack provisions `Lambda::EventSourceMapping` and `Lambda::Permission` properly, SAM-deployed stacks with SQS→Lambda or SNS→Lambda triggers should wire correctly. This is the most favorable path for SAM teams that test trigger-based event flow locally.

---

### 4. Minimum Viable Migration Checklist (SDK-Direct + Shared Base)

#### ✅ Shared steps for both tools

| Step | Change | Both Tools |
|---|---|---|
| Docker Compose | Change image, rename service | Yes (both on 4566) |
| Remove `LOCALSTACK_AUTH_TOKEN` from CI secrets | Delete secret | Yes |
| Remove `SERVICES` env var | Delete line | Yes (both auto-enable all services) |
| SDK endpoint | `endpoint_url=http://localhost:4566` | No change |
| Credentials | `access_key=test` / `secret_key=test` | No change |
| `skip_credentials_validation = true` | No change | No change |
| Health check for CI readiness | Change URL | Diverges (see below) |
| Init scripts | Rename mount path | Diverges (see below) |

#### ↔ Where paths diverge

| Concern | Floci | MiniStack |
|---|---|---|
| **Docker image** | `floci/floci:latest` | `ministackorg/ministack` |
| **Health check URL** | No documented HTTP health endpoint; rely on container start | `GET /_ministack/health` (JSON) or `/_localstack/health` (backward compat) |
| **Init scripts** | `./init/start.d:/etc/floci/init/start.d:ro` | `./boot.d:/app/boot.d:ro` and `./ready.d:/app/ready.d:ro` |
| **Reset for test isolation** | Not documented | `POST /_ministack/reset` (or `?init=1`) |
| **Multi-container hostname** | `FLOCI_HOSTNAME=floci` | `MINISTACK_HOST=ministack` |
| **CDK** | `cdklocal` + `LOCALSTACK_HOSTNAME` + `EDGE_PORT` | Plain `cdk` + `AWS_ENDPOINT_URL` only |
| **SAM** | `samlocal` (unvalidated) or `AWS_ENDPOINT_URL` | `AWS_ENDPOINT_URL` |
| **Custom API GW IDs** | `ms-custom-id` tag | `ms-custom-id` tag |
| **Testcontainers (Java)** | `io.floci:testcontainers-floci` / `FlociContainer` | `org.ministack:testcontainers-ministack:0.1.3` / `MiniStackContainer` |
| **CFN event source wiring** | Silent stub (risk) | Provisioned correctly (documented) |
| **IAM enforcement** | Optional, `FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED=true` | Not documented |
| **Storage persistence** | `FLOCI_STORAGE_MODE=hybrid\|persistent\|wal` | `PERSIST_STATE=1` + `STATE_DIR` |
| **STS operations** | All 7 operations | 4 operations (GetCallerIdentity, AssumeRole, GetSessionToken, AssumeRoleWithWebIdentity) |

#### CI Pipeline Example (GitHub Actions)

**Floci:**
```yaml
services:
  floci:
    image: floci/floci:latest
    ports:
      - "4566:4566"
    options: --health-cmd "curl -sf http://localhost:4566/ || exit 1" --health-interval 2s
steps:
  - name: Run tests
    env:
      AWS_ENDPOINT_URL: http://localhost:4566
      AWS_DEFAULT_REGION: us-east-1
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
    run: ./run-tests.sh
```
*Note: Floci's ~24ms startup makes explicit health checks mostly unnecessary in practice, but a liveness probe is good hygiene.*

**MiniStack:**
```yaml
services:
  ministack:
    image: ministackorg/ministack
    ports:
      - "4566:4566"
    options: >-
      --health-cmd "curl -sf http://localhost:4566/_ministack/health || exit 1"
      --health-interval 3s
      --health-retries 5
steps:
  - name: Run tests
    env:
      AWS_ENDPOINT_URL: http://localhost:4566
      AWS_DEFAULT_REGION: us-east-1
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
    run: ./run-tests.sh
```

#### Testcontainers Migration (Java)

```xml
<!-- Before (LocalStack) -->
<dependency>
  <groupId>org.testcontainers</groupId>
  <artifactId>localstack</artifactId>
</dependency>

<!-- After (Floci) -->
<dependency>
  <groupId>io.floci</groupId>
  <artifactId>testcontainers-floci</artifactId>
  <version>2.x</version>  <!-- Spring Boot 4.x / TC 2.x -->
</dependency>

<!-- After (MiniStack) -->
<dependency>
  <groupId>org.ministack</groupId>
  <artifactId>testcontainers-ministack</artifactId>
  <version>0.1.3</version>
</dependency>
```

```java
// Before
@Container static LocalStackContainer ls = new LocalStackContainer(DockerImageName.parse("localstack/localstack"))
    .withServices(LocalStackContainer.Service.S3, LocalStackContainer.Service.SQS);

// After (Floci) — no service selection needed
@Container static FlociContainer floci = new FlociContainer();

// After (MiniStack) — no service selection needed
@Container static MiniStackContainer ms = new MiniStackContainer();
```

Both provide `.getEndpoint()`, `.getRegion()`, `.getAccessKey()`, `.getSecretKey()` and Spring Boot `@ServiceConnection` auto-configuration.

---

## Evidence

| Claim | Value | Source |
|---|---|---|
| Floci port | 4566 | [floci/floci README](https://github.com/hectorvent/floci) |
| MiniStack port | 4566 | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| Floci image | `floci/floci:latest` (moved from `hectorvent/floci`) | [README Important notice](https://github.com/hectorvent/floci) |
| Floci startup time | ~24 ms | [floci README](https://github.com/hectorvent/floci) |
| MiniStack startup time | <2 seconds | [ministack.org](https://ministack.org) |
| Floci Terraform compat tests | 14 tests, Terraform v1.10+ | [compat-terraform/run.sh](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-terraform/run.sh) |
| Floci CDK compat tests | 17 tests, CDK v2+ | [compat-cdk/test/cdk.bats](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-cdk/test/cdk.bats) |
| Floci CDK requires `cdklocal` + `LOCALSTACK_HOSTNAME` + `EDGE_PORT` | Confirmed in source | [compat-cdk/run.sh](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-cdk/run.sh) |
| MiniStack CDK uses plain `cdk` + `AWS_ENDPOINT_URL` | From README | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| Floci CDK DockerImageFunction (ECR + Lambda) e2e passes | In CI | [compat-cdk/test/cdk.bats](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-cdk/test/cdk.bats) |
| MiniStack CFN supports `Lambda::EventSourceMapping` | README resource matrix | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| MiniStack CFN supports `Lambda::Permission` | README resource matrix | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| MiniStack health endpoint | `/_ministack/health` (also `/_localstack/health`) | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| MiniStack reset endpoint | `POST /_ministack/reset` | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| Floci storage modes | memory / persistent / hybrid / wal | [floci.io configuration](https://floci.io/floci/configuration/application-yml/) |
| Floci IAM enforcement | `FLOCI_SERVICES_IAM_ENFORCEMENT_ENABLED=true` | [floci.io configuration](https://floci.io/floci/configuration/application-yml/) |
| MiniStack Testcontainers | `org.ministack:testcontainers-ministack:0.1.3` | [testcontainers-ministack](https://github.com/ministackorg/testcontainers-ministack) |
| Floci Testcontainers | `io.floci:testcontainers-floci` 2.x (Spring Boot 4.x) | [testcontainers-floci](https://github.com/floci-io/testcontainers-floci) |
| MiniStack multi-tenant via 12-digit access key | Documented | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| MiniStack `ms-custom-id` tag; rejects `ls-custom-id` with 400 | From prior analysis | Prior iteration findings |
| Floci STS: all 7 operations | [Floci README](https://github.com/hectorvent/floci) | README |
| MiniStack STS: 4 operations | MiniStack README operations table | [ministackorg/ministack README](https://github.com/ministackorg/ministack) |
| Floci init hooks: `start.d` / `stop.d` | [Docker Compose docs](https://floci.io/floci/configuration/docker-compose/) | Floci docs |
| MiniStack init hooks: `boot.d` / `ready.d` | From README | MiniStack README |

---

## Trade-offs

### Terraform-First Teams

**Both tools are essentially equivalent for Terraform.** Zero provider.tf changes. The only meaningful Terraform-level difference is:

- **Floci has a committed, CI-run IaC compat suite** (`compat-terraform`, `compat-opentofu`) that runs in the GitHub Actions release pipeline, giving higher confidence that provider v6.x resource types work correctly after each Floci release.
- **MiniStack has broader CFN resource type coverage** (70+ CFN types vs Floci's more focused set), which matters less for Terraform-managed infrastructure but becomes important when Terraform calls CloudFormation internally (e.g., CDK-generated stacks).
- **MiniStack is better for teams that use `terraform-aws-modules/vpc`**: The EC2/VPC implementation is validated at v6.6.0 per the README, while Floci's EC2 coverage is documented but not explicitly tested via the VPC module.
- **Floci is better for teams that need IAM policy enforcement** (`enforcement-enabled: true`) to catch authorization bugs locally. MiniStack has no equivalent.

The `ls-custom-id` → `ms-custom-id` tag change affects both tools equally and is the only guaranteed Terraform file change if custom API GW IDs are in use.

### CDK/SAM Teams

This is the highest-differentiation dimension:

**Floci CDK** (better for):
- Teams already running `cdklocal` and wanting minimal CDK workflow changes — the migration preserves the same wrapper
- `DockerImageFunction` teams — Floci has an end-to-end CI-validated test (ECR push + Lambda image invocation)
- Teams who want to stage the migration incrementally without rewriting their CDK scripts

**Floci CDK** (worse for):
- Teams using CloudFormation-mediated event sources (SQS→Lambda, SNS→Lambda triggers in CDK stacks) — the silent stub risk means event-driven tests will pass deployment but fail at runtime
- Teams wanting to eliminate `cdklocal` as a dependency
- Multi-stack CDK apps using `Fn::ImportValue` (no confirmed support in Floci)

**MiniStack CDK** (better for):
- Teams wanting clean CDK v2 native path without `cdklocal`
- Teams testing CloudFormation-mediated event source wiring — `Lambda::EventSourceMapping` and `Lambda::Permission` are provisioned, not stubbed
- Multi-stack CDK apps using cross-stack exports (`Fn::ImportValue`)
- SAM teams testing trigger-based invocations locally
- Teams using `Fn::If` / conditional resource creation in templates (documented full condition support)

**MiniStack CDK** (worse for):
- Teams with Java/.NET/Go Lambda functions — MiniStack uses warm workers for Python/Node only; other runtimes use Docker RIE which requires Docker socket, same as Floci
- Teams who need validated end-to-end CDK `DockerImageFunction` support (no equivalent CI test found for MiniStack)

### SDK-Direct Teams

Both tools are equivalent. The difference is:

- **MiniStack has a documented test-isolation primitive** (`POST /_ministack/reset`) that Floci lacks — relevant for test suites that share a single running emulator instance and need clean state per test class
- **Floci has richer persistence options** (hybrid/WAL modes) for scenarios where local dev state survives container restarts
- **MiniStack has built-in multi-tenancy** via 12-digit access keys with no extra configuration — relevant for shared CI environments

### Testcontainers

Both provide official Maven Central modules with equivalent APIs. Key distinction:

- **Floci** has `withDedicatedNetwork()` for Docker socket scenarios (Lambda, RDS, ElastiCache in tests)
- **MiniStack** has `withRealInfrastructure()` to explicitly request Docker socket access
- MiniStack lists Go and Python Testcontainers as "planned"; Floci's README does not mention non-Java Testcontainers modules

---

## Confidence

| Conclusion | Confidence | Basis |
|---|---|---|
| Zero Terraform provider.tf changes for both tools | **High** | Both tools on port 4566; confirmed via compat suites and README |
| Floci CDK requires `cdklocal` + `LOCALSTACK_HOSTNAME` + `EDGE_PORT` | **High** | Direct source analysis of `compat-cdk/run.sh` |
| MiniStack CDK uses plain `cdk` + `AWS_ENDPOINT_URL` only | **High** | From README with explicit `cdk bootstrap` / `cdk deploy` commands |
| MiniStack CFN provisions `Lambda::EventSourceMapping` + `Lambda::Permission` | **Medium** | README resource matrix documents support; internal implementation not source-confirmed |
| Floci CFN stubs `Lambda::EventSourceMapping` + `Lambda::Permission` silently | **Medium** | From prior iteration's source analysis; not independently reproduced here |
| CDK `DockerImageFunction` (ECR + Lambda image) works end-to-end in Floci | **High** | Direct test in `compat-cdk/test/cdk.bats` with explicit assertion |
| CDK bootstrap (`cdk bootstrap aws://000000000000/us-east-1`) succeeds against MiniStack | **Medium** | Documented pattern + required resource types present; no end-to-end test confirmed |
| SAM `sam deploy` with `AWS_ENDPOINT_URL` correctly wires event sources in MiniStack | **Medium** | Follows from CFN support; no explicit `sam deploy` test found |
| MiniStack `/_ministack/reset` correctly clears all state for test isolation | **High** | Documented with explicit curl examples; CI tests rely on it |
| Floci has no documented HTTP health endpoint | **Medium** | Absent from all reviewed docs; inferred from 24ms startup model |

---

## New Questions

1. **Does Floci expose a machine-readable readiness endpoint?** The absence of a documented health/readiness probe URL (analogous to MiniStack's `/_ministack/health`) creates a gap for CI health checks and Testcontainers. Floci's 24ms startup mitigates this in practice, but strict CI environments that use `healthcheck:` directives in Docker Compose need a reliable target. Does Floci's JAX-RS/Vert.x router respond on any path (e.g., `GET /`) with an identifiable status code when ready?

2. **What does `samlocal` version compatibility with Floci look like in practice?** `samlocal` is LocalStack-maintained and internally calls `cdklocal` for CloudFormation operations. Since Floci's CDK compat sets `LOCALSTACK_HOSTNAME` and `EDGE_PORT`, `samlocal` should function — but SAM's asset packaging (ZIP uploads via `boto3` presigned URLs) follows a different path than CDK's. Does SAM's Lambda packaging upload succeed end-to-end against Floci, or does the presigned URL generation in Floci's S3 implementation diverge from what `samlocal` expects?

3. **Is MiniStack's CDK bootstrap path idempotent on the second run?** CDK bootstrap is designed to detect the existing `CDKToolkit` stack via `DescribeStacks` and `UpdateStack` rather than `CreateStack`. If run twice, the correct behavior is a no-op or diff-based update. MiniStack documents both operations, but CDK's bootstrap template also manages IAM roles, ECR repositories, and S3 buckets with specific naming and tagging conventions. A failed second bootstrap is a common CDK pain point and would block CI pipelines that call `cdk bootstrap` unconditionally.

---

## Peer Review (codex-cli)

I found **9 issues**.

### Issue 1: Floci image name is presented as settled, but current official docs conflict
- **Type**: factual error / missing nuance
- **Location**: `image: floci/floci:latest       # ← changed (was hectorvent/floci; now floci/floci)`
- **Problem**: Current Floci sources are inconsistent. The homepage shows `floci/floci:latest`, but the Quick Start and other docs still show `hectorvent/floci:latest`. So the finding treats a migration as definitive when the official docs are not yet internally consistent.
- **Impact**: Readers may “fix” working configs unnecessarily or conclude older docs are wrong when the upstream documentation itself is split.  
Sources: [Floci homepage](https://floci.io/), [Floci Quick Start](https://floci.io/floci/getting-started/quick-start/)

### Issue 2: MiniStack CDK guidance is overstated as “plain cdk only”
- **Type**: contradiction / missing nuance
- **Location**: `MiniStack CDK Path — Plain cdk + AWS_ENDPOINT_URL` and `No cdklocal wrapper.`
- **Problem**: MiniStack’s official docs currently say **“Use the `cdklocal` wrapper”**, while another official-ish channel (PyPI) shows plain `cdk` with `AWS_ENDPOINT_URL`. That means the evidence base is internally conflicting; the finding presents one path as definitive and high-confidence when upstream guidance is mixed.
- **Impact**: This is exactly the kind of migration detail that can break teams. The correct conclusion should be “official guidance is inconsistent; plain `cdk` appears supported in some docs, but MiniStack docs still recommend `cdklocal`.”  
Sources: [MiniStack docs](https://ministack.org/docs), [MiniStack PyPI](https://pypi.org/project/ministack/)

### Issue 3: “Floci CDK requires `cdklocal` + `LOCALSTACK_HOSTNAME` + `EDGE_PORT`” is too strong
- **Type**: unsupported claim / missing nuance
- **Location**: `Floci CDK Path — Requires cdklocal Wrapper`
- **Problem**: The evidence cited is a compatibility test harness, not a normative product requirement. Also, `aws-cdk-local` documents `LOCALSTACK_HOSTNAME` and `EDGE_PORT` as deprecated and says it can use `AWS_ENDPOINT_URL` directly.
- **Impact**: This overstates a likely implementation detail of Floci’s CI tests into a hard migration requirement.  
Sources: [aws-cdk-local docs](https://github.com/localstack/aws-cdk-local), [Floci compat harness cited in findings](https://raw.githubusercontent.com/floci-io/floci/main/compatibility-tests/compat-cdk/run.sh)

### Issue 4: The Floci CloudFormation “silent stub” claim conflicts with current Floci docs
- **Type**: contradiction / unsupported claim
- **Location**: `Floci's CloudFormation provisioner stubs AWS::Lambda::EventSourceMapping and AWS::Lambda::Permission`
- **Problem**: Current Floci docs explicitly advertise Lambda **event source mappings** and SQS/Kinesis/DynamoDB Streams triggers. That does not prove the CFN path is correct, but it does mean the finding’s claim is contradicted by current official product messaging and cannot be stated this strongly without fresh source proof.
- **Impact**: This is one of the most consequential claims in the document, and it is not robustly supported in the current version.  
Sources: [Floci homepage](https://floci.io/)

### Issue 5: MiniStack init-script migration paths are wrong
- **Type**: factual error
- **Location**: 
  - `- ./boot.d:/app/boot.d:ro`
  - `./boot.d:/app/boot.d:ro and ./ready.d:/app/ready.d:ro`
- **Problem**: MiniStack’s current docs describe native init-script paths under `/docker-entrypoint-initaws.d` and also say LocalStack-compatible paths under `/etc/localstack/init` are supported. The findings’ `/app/boot.d` and `/app/ready.d` paths are not what current docs show.
- **Impact**: This would cause needless migration churn and likely broken startup hooks.  
Sources: [MiniStack PyPI startup scripts section](https://pypi.org/project/ministack/)

### Issue 6: The Floci health-check guidance contradicts itself
- **Type**: contradiction / unsupported claim
- **Location**: 
  - `No documented HTTP health endpoint; rely on container start`
  - CI example: `--health-cmd "curl -sf http://localhost:4566/ || exit 1"`
- **Problem**: The research says no documented health endpoint exists, then recommends a health check against `/` without evidence that `/` is a stable readiness signal. That is an inference, not a verified migration recipe.
- **Impact**: CI examples are supposed to be copy-paste safe. This one is not sufficiently supported.  
Sources: [Floci docs search/no health endpoint found](https://floci.io/), [Floci Quick Start](https://floci.io/floci/getting-started/quick-start/)

### Issue 7: MiniStack Testcontainers version appears outdated/wrong
- **Type**: factual error
- **Location**: `org.ministack:testcontainers-ministack:0.1.3`
- **Problem**: Current MiniStack homepage and Maven Central show `0.1.0`, not `0.1.3`.
- **Impact**: Version mistakes are operationally expensive: copy-paste failures, dependency resolution confusion, and reduced trust in the rest of the matrix.  
Sources: [MiniStack homepage](https://ministack.org/), [Maven Central](https://central.sonatype.com/artifact/org.ministack/testcontainers-ministack)

### Issue 8: MiniStack CloudFormation coverage is inflated
- **Type**: factual error / unsupported claim
- **Location**: `MiniStack has broader CFN resource type coverage (70+ CFN types...)`
- **Problem**: Current MiniStack docs say **66 resource types** are supported, not 70+.
- **Impact**: The trade-off analysis is biased by an inflated number.  
Sources: [MiniStack docs](https://ministack.org/docs)

### Issue 9: The SAM conclusions are speculative beyond the evidence shown
- **Type**: unsupported claim
- **Location**: 
  - `SAM CLI honors AWS_ENDPOINT_URL for CloudFormation and S3 uploads`
  - `sam deploy ... should wire correctly`
- **Problem**: The finding presents this as an operational path, but no official SAM documentation was cited showing end-to-end support for `AWS_ENDPOINT_URL` across deploy/package/S3/ECR/CloudFormation. AWS SAM docs describe deployment to AWS and artifact upload behavior, but do not confirm this local-emulator path.
- **Impact**: This section reads more confidently than the evidence justifies; it should be labeled as hypothesis unless reproduced.  
Sources: [SAM deploy docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html), [SAM package docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-package.html)

## Summary
- **Issues found**: 9
- **Overall reliability**: **medium-low**
- **What would most improve the findings**: separate claims into **verified**, **inferred**, and **speculative**; resolve conflicts between official docs before drawing conclusions; and avoid promoting CI/test-harness details into product requirements without direct documentation or reproduction.
