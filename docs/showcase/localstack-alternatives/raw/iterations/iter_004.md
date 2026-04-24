# Iteration 004 — CI/CD integration: GitHub Actions, GitLab CI, and Docker-in-Docker constraints

**Status:** keep  
**Scores:** coverage=76.2, quality=55.0, total=63.5  
**Timestamp:** 2026-04-24T01:25:12.765701+00:00  

---

Now I have all the material needed for a thorough, accurate report.

---

## Findings

### 1. Official CI/CD Example Workflows

**Floci** has one official CI pipeline snippet, embedded in the [Docker Compose configuration docs](https://floci.io/floci/configuration/docker-compose/). It covers only the GitHub Actions `services:` block and the `steps:` environment — no complete workflow file, no matrix strategy, and no GitLab CI equivalent:

```yaml
# .github/workflows/test.yml (from official Floci docs)
services:
  floci:
    image: hectorvent/floci:latest   # ⚠ OUTDATED — see note
    ports:
      - "4566:4566"
steps:
  - name: Run tests
    env:
      AWS_ENDPOINT_URL: http://localhost:4566
      AWS_DEFAULT_REGION: us-east-1
      AWS_ACCESS_KEY_ID: test
      AWS_SECRET_ACCESS_KEY: test
    run: mvn test
```

**Critical documentation inconsistency**: The CI example still references `hectorvent/floci:latest`, which the [Floci README explicitly marks as abandoned](https://github.com/floci-io/floci):

> The old `hectorvent/floci` repository will no longer receive updates.

The correct image is `floci/floci:latest`. A CI pipeline copying this example verbatim will pull a stale image.

**MiniStack** has no official GitHub Actions or GitLab CI YAML examples in its [README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) or documentation site. Community-maintained examples exist (including from the MiniStack team's own benchmark article), but there is no canonical workflow file for either CI platform.

**Neither tool provides official GitLab CI documentation.** The same patterns apply: declare the emulator as a `services:` entry, expose port 4566, and point your AWS SDK at the service hostname.

---

### 2. Privileged Mode and Docker-in-Docker Constraints

Neither Floci nor MiniStack requires privileged mode or Docker-in-Docker for any of their core services. The breakdown is:

| Service tier | Docker requirement | Privileged needed? |
|---|---|---|
| S3, SQS, SNS, DynamoDB, IAM, STS, KMS, Cognito, SSM, Secrets Manager, Step Functions, EventBridge, CloudWatch, API Gateway v1+v2, Kinesis, ACM, SES, CloudFormation, EC2, Glue, Firehose (all in-process) | None | No |
| Lambda, ElastiCache, RDS, MSK, ECS, EKS, ECR, OpenSearch (real Docker containers) | `/var/run/docker.sock` bind mount | No |

Both tools use **Docker-out-of-Docker (DooD)**: the emulator process talks to the host's Docker daemon via the socket, spawning sibling containers. Privileged mode would only be needed if you ran a Docker daemon *inside* the emulator container — neither tool does this.

**GitHub Actions hosted runners (`ubuntu-latest`)**: Docker Engine is pre-installed. When test code runs directly on the runner host (the default pattern — no `container:` at the job level), the Docker socket at `/var/run/docker.sock` is accessible with no extra configuration. [Testcontainers official guidance](https://github.com/filipsnastins/testcontainers-github-actions) confirms this is sufficient.

**GitHub Actions service containers** do not support `options: --privileged` on hosted runners. For Lambda (or RDS/ElastiCache) to work from within a service container, the socket mount must be added as a `volumes:` entry:

```yaml
services:
  floci:
    image: floci/floci:latest
    ports:
      - "4566:4566"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

[GitHub's service-container docs](https://docs.github.com/en/actions/using-containerized-services/about-service-containers) make no mention of privileged mode being available; socket-mount is the recommended pattern for Docker access from within services.

**GitLab CI (Docker executor, shared runners)**: GitLab shared runners typically run jobs inside Docker containers. The service is reachable via its service label hostname (e.g., `http://floci:4566`). For Testcontainers or Lambda execution in the *job container* to reach Docker, teams must configure `DOCKER_HOST` to point at the host socket or a DinD sidecar. GitLab's official guidance recommends the socket-bind pattern over DinD where privileged mode is unavailable. No official GitLab CI example exists from either project.

---

### 3. Cold-Start Time and Steady-State Memory Footprint

**Floci** (native binary, `floci/floci:latest`):

| Metric | Value | Source |
|---|---|---|
| Cold-start time | **~24 ms** | [floci.io homepage](https://floci.io/) |
| Idle memory | **~13 MiB** | [floci.io homepage](https://floci.io/) |
| Docker image size (native) | **~90 MB** | [floci.io homepage](https://floci.io/) |
| Docker image size (JVM tag) | ~276 MB | [dev.to benchmark](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p) |

An April 2026 benchmark (authored by the MiniStack team) reported Floci startup as "~3s" and image size 276 MB — but their methodology used `hectorvent/floci:latest`, which at the time of testing corresponded to the JVM image. The JVM variant starts in ~85ms and uses a 276MB image; the native `floci/floci:latest` starts in ~24ms and uses ~90MB. Teams evaluating CI overhead should be careful to pull the native image.

**MiniStack** (`ministackorg/ministack:latest`):

| Metric | Value | Source |
|---|---|---|
| Cold-start time | **<2s** | [MiniStack README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) |
| Idle memory | ~21 MB (README) / ~30 MB (website) | [README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md), [ministack.org](https://ministack.org/) |
| Docker image size | ~270 MB | [MiniStack README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) |
| Lambda throughput | 233 ops/s (SQS benchmark proxy) | [dev.to benchmark](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p) |

**Pipeline cost impact**: On GitHub Actions, `ubuntu-latest` runners are billed per minute (minimum 1 min per job). Both tools' cold-start times are negligible relative to pipeline billing granularity. The meaningful CI cost difference lies in Docker image pull time: Floci's ~90MB native image pulls in seconds on a fresh runner; MiniStack's ~270MB image takes longer. For frequently run jobs where layer caching is unavailable (ephemeral runners, matrix jobs without caching), Floci's smaller image size reduces pipeline minutes more meaningfully than the sub-2s startup difference.

---

### 4. Testcontainers Module Compatibility in GitHub Actions

**Floci Testcontainers module** (`io.floci:testcontainers-floci:2.0.0`):

```java
var floci = new FlociContainer();
floci.start();
// endpoint: http://localhost:<mapped-port>
```

The native module is minimal and correct. It works on `ubuntu-latest` runners without privileged mode — tests run directly on the host and the Docker socket is available.

The complexity arises when teams use the **LocalStack compatibility substitute path** (required to reuse `LocalStackContainer.withServices()` infrastructure without rewriting test code):

```kotlin
// Must override startup script AND wait strategy
class FlociContainer(dockerImageName: DockerImageName) : LocalStackContainer(dockerImageName) {
    override fun containerIsStarting(containerInfo: InspectContainerResponse) {
        val command = if (dockerImageName.contains("jvm")) {
            "/bin/sh\njava -jar quarkus-app/quarkus-run.jar\n"
        } else {
            "/bin/bash\n./application\n"
        }
        copyFileToContainer(Transferable.of(command, 511), STARTER_SCRIPT)
    }
}
// Wait strategy must be changed from ".*Ready\\.\\n" to ".*started in.*"
.waitingFor(LogMessageWaitStrategy().withRegEx(".*started in.*").withTimes(1))
```

This is confirmed by a [Spring Boot Floci migration blog post](https://ttlnews.blogspot.com/2026/04/alternatives-for-localstack-in.html) — a primary engineering report. The native `FlociContainer` API avoids this friction entirely; it's only the LocalStack-compatibility substitute path that requires it.

**MiniStack Testcontainers module** (`org.ministack:testcontainers-ministack:0.1.3`):

```java
try(MiniStackContainer ministack = new MiniStackContainer()) {
    ministack.start();
    String endpoint = ministack.getEndpoint(); // auto-mapped
    // Works with any SDK
}
// Spring Boot ServiceConnection
@Bean @ServiceConnection
public MiniStackContainer miniStackContainer() { return new MiniStackContainer("latest"); }
// Real infrastructure (Docker socket must be accessible):
ministack.withRealInfrastructure();
```

On `ubuntu-latest`, the module works out of the box. The `withRealInfrastructure()` method mounts the Docker socket into the MiniStack container at test start — this works on hosted runners when the test code itself is running on the host.

**Known issue (MiniStack, April 2026)**: [GitHub issue #367](https://github.com/ministackorg/ministack/issues/367) documents a Lambda Docker executor failure:

> `"invalid mount config for type "bind": bind source path does not exist: /tmp/ministack-lambda-docker-xxx/code"`

This occurs when MiniStack itself runs inside a Docker container (e.g., as a Testcontainers container or a service container) and attempts to spawn Lambda sibling containers. The path MiniStack writes Lambda code to on its own filesystem (`/tmp/ministack-lambda-docker-*/code`) is not accessible as a bind mount from the host's Docker daemon perspective. This is a fundamental DooD limitation: the bind-mount source must exist on the *host*, not inside the intermediate container. **Lambda execution in local mode (`LAMBDA_EXECUTOR=local`) is not affected.** This issue is open as of April 2026.

Floci does not have a documented equivalent issue; its Lambda container lifecycle is managed differently.

**Service container networking**: When Floci runs as a GitHub Actions service container, `FLOCI_HOSTNAME: floci` must be set or generated SQS queue URLs and pre-signed S3 URLs will embed `localhost` — unreachable from any sibling containers that call back to the emulator via those URLs. MiniStack has an equivalent `MINISTACK_HOST` variable. Neither tool's official CI examples include these variables.

---

## Evidence

| Data point | Value | Source |
|---|---|---|
| Floci startup time | 24 ms | [floci.io homepage](https://floci.io/) |
| Floci idle memory | 13 MiB | [floci.io homepage](https://floci.io/) |
| Floci native Docker image | ~90 MB | [floci.io homepage](https://floci.io/) |
| Floci JVM Docker image | ~276 MB | [dev.to benchmark (MiniStack team)](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p) |
| MiniStack startup time | <2 s | [MiniStack README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) |
| MiniStack idle memory | ~21–30 MB | [README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) / [ministack.org](https://ministack.org/) |
| MiniStack Docker image | ~270 MB | [MiniStack README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) |
| Floci official CI snippet | GitHub Actions `services:` block only | [Floci Docker Compose docs](https://floci.io/floci/configuration/docker-compose/) |
| Floci CI snippet uses wrong image | `hectorvent/floci:latest` (deprecated) | [Floci README image migration notice](https://github.com/floci-io/floci) |
| Floci default storage mode | `memory` | [Floci application.yml reference](https://floci.io/floci/configuration/application-yml/) |
| MiniStack no official CI YAML | Confirmed absence | [MiniStack README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) |
| GitHub Actions: no privileged for service containers | Documented constraint | [GitHub Actions service container docs](https://docs.github.com/en/actions/using-containerized-services/about-service-containers) |
| Testcontainers on ubuntu-latest: no privileged mode needed | Confirmed | [Testcontainers GitHub Actions examples](https://github.com/filipsnastins/testcontainers-github-actions) |
| Floci LocalStack compat path: requires custom startup script + wait regex | Confirmed in production | [Spring Boot migration blog](https://ttlnews.blogspot.com/2026/04/alternatives-for-localstack-in.html) |
| Floci wait-for-ready log string | `".*started in.*"` | [Spring Boot migration blog](https://ttlnews.blogspot.com/2026/04/alternatives-for-localstack-in.html) |
| MiniStack Lambda Docker bind-mount failure | Open bug, issue #367 | [GitHub issue #367](https://github.com/ministackorg/ministack/issues/367) |
| Floci mock modes for CI (ECS, OpenSearch) | `FLOCI_SERVICES_ECS_MOCK=true`, `FLOCI_SERVICES_OPENSEARCH_MOCK=true` | [Floci application.yml reference](https://floci.io/floci/configuration/application-yml/) |
| FLOCI_HOSTNAME required for service container URL generation | Documented | [Floci Docker Compose docs](https://floci.io/floci/configuration/docker-compose/) |
| Floci Testcontainers module | `io.floci:testcontainers-floci:2.0.0` | [testcontainers.com/modules/floci](https://testcontainers.com/modules/floci/) |
| MiniStack Testcontainers module | `org.ministack:testcontainers-ministack:0.1.3` | [ministackorg/testcontainers-ministack](https://github.com/ministackorg/testcontainers-ministack) |
| MiniStack `/_localstack/health` alias | Confirmed | [MiniStack README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) |
| MiniStack `/_ministack/reset` for test isolation | Documented | [MiniStack README](https://raw.githubusercontent.com/ministackorg/ministack/main/README.md) |

---

## Trade-offs

### Floci in CI

**Advantages:**
- **24ms startup** on the native image means the emulator adds essentially zero overhead to CI wall time. On a GitHub Actions runner with the image already cached, "floci start" is invisible.
- **~90MB image** pulls much faster than MiniStack's ~270MB on ephemeral runners — relevant for high-volume matrix pipelines or projects without Docker layer caching.
- **`FLOCI_SERVICES_ECS_MOCK=true` / `FLOCI_SERVICES_OPENSEARCH_MOCK=true`**: explicit mock modes for Docker-backed services allow those service APIs to be tested (control-plane stubs return success) without a Docker socket, making the CI config simpler for teams that don't test ECS or OpenSearch internals.
- Lambda execution is not affected by the bind-mount path bug that hits MiniStack.

**Disadvantages:**
- **Official CI documentation uses deprecated `hectorvent/floci:latest` image.** A team copying the example verbatim gets the stale image. This is a silent failure mode — the image still works but receives no updates.
- **No official GitLab CI example.** Teams on GitLab must figure out the service networking themselves. Specifically, `FLOCI_HOSTNAME: floci` must be added to service-container configurations, and this variable is not mentioned in the CI example snippet.
- **LocalStack compatibility Testcontainers path is non-trivial.** Projects that want to migrate incrementally by keeping `LocalStackContainer.withServices()` call sites must write a custom container subclass + wait strategy override. The native `FlociContainer` API avoids this, but requires rewriting call sites.
- **ECS, OpenSearch, MSK, EKS** are real-Docker services with no mock mode documented for them (ECS has `mock: false` as default with `mock: true` available; OpenSearch has `mock: true` available). For CI without Docker socket, teams must explicitly set these to mock mode or accept that those services are unavailable.

### MiniStack in CI

**Advantages:**
- **`/_localstack/health` alias** means existing CI health check scripts, Docker Compose `healthcheck:` blocks, and Kubernetes readiness probes copy-paste without modification.
- **`/_ministack/reset`** endpoint allows test isolation *without restarting the container* — a meaningful CI pattern for `beforeEach`/`@BeforeEach` style test suites. Combined with `?init=1` it re-runs init scripts to restore seed data.
- **Testcontainers module is cleaner**: Spring Boot `@ServiceConnection` annotation support and `withRealInfrastructure()` API require fewer lines of test code than the Floci compatibility path.
- Startup of <2s is still fast enough that CI overhead is negligible for billing purposes.

**Disadvantages:**
- **Lambda Docker executor bind-mount bug (issue #367)**: When MiniStack runs inside a Docker container (as a Testcontainers-managed container or a GitHub Actions service container) and `LAMBDA_EXECUTOR=docker` is configured, Lambda invocations fail with a bind-mount error. Workaround: use `LAMBDA_EXECUTOR=local` (Python/Node.js warm worker pool) for CI, or run tests directly on the host runner (not inside a container job) where the mount path is accessible.
- **~270MB image** is 3× larger than Floci's native image — meaningful on ephemeral runners without caching.
- **No official CI YAML examples** from the project.
- **`MINISTACK_HOST` (the hostname override) is not mentioned in any CI context documentation**, even though it is the equivalent of Floci's `FLOCI_HOSTNAME` and has the same silent failure mode in multi-container setups.

### For GitLab CI specifically

Neither tool ships official `.gitlab-ci.yml` examples. The key concern is that GitLab's Docker executor runs the job inside a container, so Testcontainers requires Docker socket access via `DOCKER_HOST` or a DinD sidecar — the same Lambda bind-mount limitation applies to MiniStack when running inside GitLab CI job containers. Floci's Lambda implementation is unaffected.

---

## Confidence

| Conclusion | Confidence | Rationale |
|---|---|---|
| Neither tool requires privileged mode for core services | **High** | Direct inspection of Docker socket requirements in both official READMEs; confirmed by GitHub Actions docs confirming socket-mount works without privileged mode |
| Floci native image starts in ~24ms, uses ~13 MiB idle | **High** | Primary source: floci.io homepage and README; consistent with GraalVM native binary expectations |
| MiniStack starts in <2s, uses ~21–30 MiB idle | **High** | Primary: README and ministack.org; range reflects minor discrepancy between sources (both within same order of magnitude) |
| Testcontainers modules work on ubuntu-latest without privileged mode | **High** | Docker is pre-installed on ubuntu-latest; confirmed by testcontainers community examples and GitHub Actions architecture |
| Floci CI snippet uses deprecated `hectorvent/floci:latest` | **High** | Directly observable in current floci.io docs vs README migration notice |
| Floci storage default is `memory`, NOT `hybrid` | **High** | Confirmed by `application.yml` reference: `mode: memory` is the shipped default |
| MiniStack Lambda Docker executor bind-mount bug exists | **High** | Open GitHub issue #367 with reproduction steps and error message |
| April 2026 dev.to benchmark used Floci's JVM image (explaining ~3s startup) | **Medium** | Inferred from benchmark's reported 276 MB image size (matching JVM tag) and old image names; not directly confirmed by benchmark author |
| `FLOCI_HOSTNAME` / `MINISTACK_HOST` required for correct service-container URL generation | **High** | Documented in Floci Docker Compose docs; MiniStack README explicitly documents `MINISTACK_HOST` |
| GitLab CI: MiniStack Lambda Docker bind-mount bug also affects GitLab job containers | **Medium** | Logical extension of issue #367 (same DooD path problem); not independently tested against GitLab |
| Neither tool provides official GitLab CI examples | **High** | Confirmed absence after checking both READMEs and documentation sites |

---

## New Questions

1. **Lambda bind-mount workaround in GitHub Actions service containers**: MiniStack issue #367 confirms the failure when MiniStack runs inside Docker. Does Floci's Lambda implementation encounter the same bind-mount limitation if Floci is run as a service container (inside Docker)? The Floci docs describe Lambda code storage in `./data/lambda-code` — if that path is inside the Floci container and gets passed to the host Docker daemon as a bind mount, the same path-not-found error should occur. Reproducing a `FlociContainer` test that invokes Lambda in a service-container configuration would determine whether this is a Floci risk or a MiniStack-only issue.

2. **Docker layer caching strategy for CI**: At ~90MB (Floci native) and ~270MB (MiniStack), repeated pulls on ephemeral CI runners (especially across GitHub Actions matrix jobs) have meaningfully different costs. What is the actual pull time delta on a GitHub-hosted runner (`ubuntu-latest`) without cache, and does the difference translate to a real pipeline-minute cost difference at scale (e.g., 100 parallel matrix jobs × 5 pushes/day)?

3. **`/_ministack/reset` isolation semantics vs Lambda warm workers**: MiniStack's reset API (`POST /_ministack/reset`) promises to wipe all service state. Does it also terminate running Lambda warm-worker processes and Lambda Docker containers? If warm workers survive a reset, tests run after reset may get stale function code or environment. This would affect the common CI pattern of sharing a single MiniStack instance across test classes with per-class resets.

---

## Peer Review (codex-cli)

As of **April 23, 2026**, I found **10 issues**.

### Issue 1: “No privileged mode” is overstated
- **Type**: missing nuance
- **Location**: “Neither Floci nor MiniStack requires privileged mode or Docker-in-Docker for any of their core services.”
- **Problem**: MiniStack’s README includes a caveat that `privileged: true` may be needed if `/var/run/docker.sock` is root-owned. So “neither requires privileged mode” is too absolute.
- **Impact**: Overstates portability and may mislead teams on locked-down runners.

### Issue 2: GitHub Actions `--privileged` claim is not supported by the cited docs
- **Type**: unsupported claim
- **Location**: “GitHub Actions service containers do not support `options: --privileged` on hosted runners.”
- **Problem**: GitHub’s workflow syntax docs explicitly support `jobs.<job_id>.services.<service_id>.options` and only document `--network` as unsupported. The cited docs do **not** prove `--privileged` is unavailable.
- **Impact**: Weakens a central CI conclusion.

### Issue 3: Service-container networking is oversimplified
- **Type**: missing nuance
- **Location**: “The same patterns apply: declare the emulator as a `services:` entry, expose port 4566, and point your AWS SDK at the service hostname.”
- **Problem**: GitHub docs distinguish between:
  - jobs running **on the runner host** → use `localhost` + mapped ports
  - jobs running **in a container** → use service hostname, no host port mapping needed  
  The report collapses these cases.
- **Impact**: Can produce incorrect CI YAML.

### Issue 4: GitLab guidance is characterized too strongly
- **Type**: unsupported claim
- **Location**: “GitLab's official guidance recommends the socket-bind pattern over DinD where privileged mode is unavailable.”
- **Problem**: GitLab docs present **socket binding** and **DinD** as separate patterns. They do not frame socket binding as a general recommendation “over” DinD in the way stated here.
- **Impact**: Makes the GitLab section sound more authoritative than the evidence supports.

### Issue 5: Floci JVM startup number is likely wrong
- **Type**: factual error
- **Location**: “The JVM variant starts in ~85ms…”
- **Problem**: A Floci-authored benchmark page reports JVM startup around **684 ms**, not ~85 ms.
- **Impact**: Undermines the startup-time comparison and the explanation for the benchmark discrepancy.

### Issue 6: MiniStack Testcontainers version looks wrong/out-of-date
- **Type**: factual error
- **Location**: “`org.ministack:testcontainers-ministack:0.1.3`”
- **Problem**: The official repo README shows `0.1.0`, and the repo page shows latest release **v0.1.2** on **April 16, 2026**. I did not find support for `0.1.3` in the cited official sources.
- **Impact**: Damages confidence in the dependency guidance.

### Issue 7: `withRealInfrastructure()` is not supported by the cited official source
- **Type**: unsupported claim
- **Location**: “The `withRealInfrastructure()` method mounts the Docker socket into the MiniStack container at test start…”
- **Problem**: The cited official README excerpt shows `MiniStackContainer`, `getEndpoint()`, and Spring `@ServiceConnection`, but not `withRealInfrastructure()`.
- **Impact**: Readers may rely on an API that is not established by the evidence provided.

### Issue 8: A blog post is mislabeled as a primary source
- **Type**: unsupported claim
- **Location**: “This is confirmed by a Spring Boot Floci migration blog post — a primary engineering report.”
- **Problem**: A blog post is not a primary project source unless it is directly from the project/repo/docs and clearly authoritative for that behavior. Here it is, at best, a secondary implementation note.
- **Impact**: Inflates confidence in the LocalStack-compat workaround claim.

### Issue 9: “Floci does not have a documented equivalent issue” is speculative
- **Type**: unsupported claim
- **Location**: “Floci does not have a documented equivalent issue; its Lambda container lifecycle is managed differently.”
- **Problem**: The evidence shown supports a networking distinction for Floci-in-Docker, but not enough to dismiss analogous host bind-mount problems. The conclusion jumps beyond the evidence.
- **Impact**: May make Floci look safer in CI than has actually been demonstrated.

### Issue 10: Important source inconsistencies were not surfaced
- **Type**: gap
- **Location**: overall findings
- **Problem**: The source set itself is inconsistent on basic product facts:
  - Floci appears as **32**, **33**, and **35+** services across official pages.
  - MiniStack appears as **40+** and **41** services.
  - MiniStack idle memory appears as **~21 MB** and **~30 MB**.  
  The report mentions the MiniStack RAM discrepancy, but not the broader count inconsistencies.
- **Impact**: The findings appear more settled than the source base actually is.

## Summary
- **Issues found**: 10
- **Overall reliability**: **Medium**
- **What would most improve the findings**:
  1. Replace secondary/blog evidence with official docs or repo code for CI/Testcontainers behavior.
  2. Tighten claims about GitHub/GitLab runner semantics.
  3. Resolve version/service-count inconsistencies explicitly instead of smoothing over them.

**Sources used**:  
- Floci docs: https://floci.io/floci/configuration/docker-compose/  
- Floci app config: https://floci.io/floci/configuration/application-yml/  
- Floci quick start: https://floci.io/floci/getting-started/quick-start/  
- Floci GitHub README: https://github.com/floci-io/floci  
- MiniStack README: https://raw.githubusercontent.com/ministackorg/ministack/main/README.md  
- MiniStack website: https://ministack.org/  
- MiniStack Testcontainers repo: https://github.com/ministackorg/testcontainers-ministack  
- GitHub Actions workflow syntax: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax  
- GitHub service containers docs: https://docs.github.com/en/actions/tutorials/use-containerized-services/use-docker-service-containers  
- GitLab Docker-in-Docker/socket binding docs: https://docs.gitlab.com/ci/docker/using_docker_build/  
- GitLab Docker executor docs: https://docs.gitlab.com/runner/executors/docker/

## Key Learnings:
1. The strongest weaknesses are not the headline conclusions, but the overconfident CI/platform claims around runner behavior.
2. The report mixes primary and secondary evidence without consistently signaling the difference.
3. Version and product-fact drift is already visible across official Floci and MiniStack materials, so any “high-confidence” claim should account for that explicitly.
