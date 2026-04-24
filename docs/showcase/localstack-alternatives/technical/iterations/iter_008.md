# Iteration 008 — API compatibility and behavioral fidelity vs real AWS for core services

**Status:** keep  
**Scores:** coverage=67.5, quality=65.0, total=66.0  
**Timestamp:** 2026-04-24T12:48:14.541826+00:00  

---

I now have sufficient evidence. Let me compose the research output.

---

### Findings

**Research dimension: API compatibility and behavioral fidelity vs real AWS for S3, SQS, DynamoDB, and Lambda (Floci vs MiniStack, April 24 2026)**

---

#### S3 — Error Codes, ETags, and Response Shapes

**Floci** passes its own Python compatibility suite (`sdk-test-python/tests/test_s3.py`) for core operations: create/delete/list buckets, object put/get/head/delete/copy, tagging, CORS, and S3→SQS event notifications. The `test_head_object` test explicitly asserts `LastModified.microsecond == 0`, confirming Floci matches the second-precision timestamp format AWS uses (not millisecond). However, Floci's tests do **not** explicitly verify ETag format (MD5 for single-part uploads vs. `<md5>-<N>` for multipart). ETag presence is assumed but its shape is not validated.

Active divergences in Floci on S3: issue [#556](https://github.com/floci-io/floci/issues/556) — `S3Control.ListTagsForResource` rejects plain bucket ARNs (`arn:aws:s3:::bucket-name`) when called by Terraform AWS provider v6/Go SDK v2.

**MiniStack** has a richer S3 test file (58KB vs Floci's 12KB). It explicitly tests:
- `ListBuckets` must return `BucketArn` (`arn:aws:s3:::{bucket}`) and `BucketRegion` per item — a field fidelity check absent from Floci's suite
- `DeleteBucket` must return `BucketNotEmpty` and `NoSuchBucket` error codes exactly
- Idempotent `CreateBucket` (same bucket twice returns 200, not an error)
- Chunked Transfer-Encoding (`x-amz-content-sha256: STREAMING-AWS4-HMAC-SHA256-PAYLOAD`) — critical for AWS SDK v2 Java/Go

Active divergences in MiniStack on S3: issue [#447](https://github.com/ministackorg/ministack/issues/447) (filed April 24) — `S3Control.TagResource` silently drops tags because the handler only has a PUT branch but AWS SDK Go v2 sends POST with XML; `json.loads` on the XML body throws, the except swallows it, and 204 is returned with no data stored. This causes Terraform `default_tags` on `aws_s3_bucket` to loop with perpetual drift. Issue [#428](https://github.com/ministackorg/ministack/issues/428) — `S3 Bucket ARN not set` in some contexts.

**ETag format**: Neither tool validates ETag format explicitly in their published test suites. Neither documents a known divergence, but neither can be confirmed fidelity-correct for multipart ETags without dedicated tests.

---

#### SQS — ReceiptHandle Opacity and Response Shapes

**Floci** covers queues, send/receive/delete, DLQ routing, visibility timeout, long polling (asserts elapsed ≥ 1.8s for 2s wait), message attributes, and batch operations. The DLQ test creates a main queue and DLQ, sends a message, receives it past `maxReceiveCount`, and asserts the DLQ receives it — end-to-end SQS dead-letter behavior tested.

**MiniStack** tests the same core set plus several additional fidelity checks that Floci's suite does not cover:
- `ApproximateReceiveCount` system attribute increments correctly (1 after first receive, 2 after second)
- FIFO deduplication scope (`DeduplicationScope=messageGroup`): same body in different groups enqueues twice; same body in same group deduplicates to same `MessageId`
- `DelaySeconds=2`: message not visible immediately, visible after 2.5s
- `test_sqs_batch_delete_invalid_receipt_handle`: invalid ReceiptHandle populates `Failed` list (not visible in Floci's suite)
- Exact error code check: `AWS.SimpleQueueService.NonExistentQueue` — matching AWS exactly

On ReceiptHandle opacity: both tools return a ReceiptHandle token and both test that passing it to `DeleteMessage` / `ChangeMessageVisibility` succeeds. Neither explicitly tests that the token is opaque (non-decodable), because that's not typically an application-code concern — applications should not decode ReceiptHandles.

No open SQS bugs in either repo as of April 24, 2026.

---

#### DynamoDB — Pagination Tokens, ConditionalCheckFailedException, and Concurrency

This is the highest-signal fidelity dimension. Two critical Floci bugs were filed in the last 48 hours before this report.

**Floci Critical Bug #587** ([filed April 24, 2026](https://github.com/floci-io/floci/issues/587)): **GSI Query pagination infinite loop with duplicate sort keys.** On a GSI query, Floci's `LastEvaluatedKey` contains only the index keys (`GSI1PK`, `GSI1SK`), not the base-table keys (`PK`, `SK`). AWS returns all four. When multiple items share the same `(GSI1PK, GSI1SK)`, Floci's `ExclusiveStartKey` matcher (linear scan, breaks on first hit) always lands on the same item, returning identical pages indefinitely. Reproducer shows 5 items, `limit=2`, same `GSI1SK`: pages 2 and 3 are identical. **Any application using `ExclusiveStartKey` pagination on a GSI where items share the same index sort key will hang forever against Floci.** This is a direct application-breaking divergence.

**Floci Critical Bug #571** ([filed April 23, 2026](https://github.com/floci-io/floci/issues/571)): **UpdateItem atomic counter not serialized under concurrency.** 50 concurrent `UpdateItem` calls with `SET cnt = if_not_exists(cnt, :start) + :inc` return duplicate counter values. Real DynamoDB serializes these via internal partition-level locking. Applications using DynamoDB's `UpdateItem` as an atomic ID generator will silently allocate duplicate IDs. As a downstream consequence, `PutItem` with `attribute_not_exists(PK)` on the duplicate key raises `ConditionalCheckFailedException` spuriously — the error code fires correctly, but on a logically wrong condition. **This means `ConditionalCheckFailedException` will appear where AWS would not raise it, and will not appear (from the counter's perspective) where writes actually conflict at the counter level.**

**MiniStack** has zero open DynamoDB bugs. Its test file is 58KB (vs Floci's 22KB). MiniStack's test suite includes:
- `ReturnConsumedCapacity=TOTAL` shape validation: `ConsumedCapacity[0].CapacityUnits == 1.0` for a single item, `2.0` for a table-plus-GSI put, `4.0` for a batch-write of two items on a table with one GSI — precise numeric fidelity matching AWS billing model
- DynamoDB Streams: `LatestStreamArn` present after `StreamSpecification` enabled; all three write operations (put, update, delete) succeed with streams active
- PITR: `RecoveryPeriodInDays == 35` after enabling PITR — correct default matches AWS

MiniStack's test suite does not include an explicit pagination test on GSI with duplicate sort keys (a gap), but no corresponding open bug is reported.

---

#### Lambda — Execution Model, Cold/Warm Semantics, and Service Integration

**Floci** uses real Docker containers via the AWS public ECR Lambda runtime images (`public.ecr.aws/lambda/<runtime>`). This is the strongest possible fidelity approach for Lambda. The architecture supports all runtimes: Java (java8–java25), Python (3.9–3.14), Node.js (16.x–24.x), Ruby (3.2–3.4), .NET (6–10), Go (1.x), and custom runtimes.

However, three active Lambda bugs materially impact behavioral fidelity:

**Floci Bug #432** ([April 14, 2026](https://github.com/floci-io/floci/issues/432)): **Lambda containers cannot reach S3 via virtual-hosted-style hostname.** The wildcard DNS record `*.localhost.floci.cloud` resolves to a public AWS-owned IP (e.g., `76.223.54.146`), not to the Floci container. AWS SDK clients inside Lambda containers use virtual-hosted-style addressing by default (`my-bucket.localhost.floci.cloud:4566`). The TCP connection goes to a live AWS endpoint, hangs, and the Lambda times out. Workaround: set `s3ForcePathStyle: true` in the Lambda handler or use `http://floci:4566` directly — but neither matches how production code runs. **Any Lambda function that reads from S3 with the default SDK addressing style will time out against Floci.**

**Floci Bug #485** ([April 16, 2026](https://github.com/floci-io/floci/issues/485)): **Container handle leak and warm pool drain on function timeout.** When an invocation times out, the timed-out container is never released (orphan Docker process visible in `docker ps`), and `drainFunction()` destroys all *other* warm containers for the same function. Every subsequent call becomes a cold start. Real AWS returns the container to the warm pool or stops it cleanly, and other warm instances are unaffected. **Applications that hit timeout conditions will see escalating cold-start latency and Docker container accumulation against Floci — a silent behavioral drift.**

**Floci Bug #547** ([April 20, 2026](https://github.com/floci-io/floci/issues/547)): **Handler validation rejects nested Python/Node module paths.** `CreateFunction` with `Handler: "apps.foo.src.lambda_handler.lambda_handler"` returns a validation error in Floci 1.5.5. Real AWS defers handler resolution to invocation time. Split on `.` takes `[0]` instead of splitting on the last `.`. **Monorepo Python/Node Lambda handlers (a common production pattern) cannot be registered in Floci.**

**MiniStack** uses Python-native warm workers for Python and Node.js runtimes (subprocess-based execution), with Docker/RIE for other runtimes. This means cold-start latency is not simulated for Python/Node: every invocation is warm. For Java, Go, .NET — Floci's Docker-based model is more faithful.

MiniStack has fixed a corresponding Lambda handler path bug: `test_lambda_python_nested_handler_slash_form` confirms that `pkg/sub/mod.hello` (slash-form) works, meaning nested paths are accepted. This is the same class of bug that Floci still has open as #547.

MiniStack's `test_lambda_esm_sqs` is an end-to-end SQS→Lambda event source mapping test: creates a queue, creates a function, creates an ESM with `BatchSize=5`, sends a message, polls the queue, and asserts the message was consumed by Lambda. Floci has no equivalent end-to-end ESM integration test in its published compatibility suite.

---

#### End-to-End Service Boundary Behaviors

| Boundary | Floci | MiniStack |
|---|---|---|
| S3 → SQS event notification | Tested: `test_s3_notifications.py` | In `test_s3.py` (58KB) |
| SQS → Lambda ESM trigger | Not in compat test suite | Tested: `test_lambda_esm_sqs` |
| Lambda → S3 (runtime access) | **Bug #432: DNS fails silently with default addressing** | No equivalent open bug |
| SQS DLQ after maxReceiveCount | Tested in `test_sqs.py` | Tested in `test_sqs.py` |
| DynamoDB Streams → Lambda ESM | Not in compat suite, but architecture doc claims support | In `test_dynamodb.py` and `test_lambda.py` |
| API Gateway → Lambda | Tested; but **Bug #574: TOKEN authorizer context not forwarded** | Extensive test_apigatewayv1.py (57KB), test_apigatewayv2.py (78KB) |

---

### Evidence

- Floci test count, by SDK: **[README.md](https://github.com/floci-io/floci/blob/main/README.md)** — Java 889, Node 360, Python 264, Go 136, AWS CLI 145, Rust 86, IaC 45 = **1,850+ total** (self-reported, run against Floci not against AWS; not independently verified as 100% passing on current HEAD)
- Floci open bug count: **32 open issues** as of April 24, 2026 [[issues](https://github.com/floci-io/floci/issues)]
- MiniStack open bug count: **17 open issues** (of which ~5 are labeled `bug`) as of April 24, 2026 [[issues](https://github.com/ministackorg/ministack/issues)]
- Floci DynamoDB GSI pagination bug: [#587](https://github.com/floci-io/floci/issues/587) filed April 24, 2026 — `LastEvaluatedKey` missing base-table keys causes infinite loop
- Floci DynamoDB atomic counter bug: [#571](https://github.com/floci-io/floci/issues/571) filed April 23, 2026 — 50 concurrent `UpdateItem` returns duplicates
- Floci Lambda→S3 DNS bug: [#432](https://github.com/floci-io/floci/issues/432) — `*.localhost.floci.cloud` resolves to `76.223.54.146` (public AWS IP) inside Lambda containers
- Floci Lambda warm pool drain bug: [#485](https://github.com/floci-io/floci/issues/485) — timeout leaks container handle, drains other warm containers
- Floci Lambda nested handler bug: [#547](https://github.com/floci-io/floci/issues/547) — `split(".")[0]` instead of `rsplit(".", 1)` for module path
- MiniStack S3Control tag bug: [#447](https://github.com/ministackorg/ministack/issues/447) — POST body with XML content parsed as JSON, silently dropped
- MiniStack Lambda nested handler: **fixed** — `test_lambda_python_nested_handler_slash_form` passes
- MiniStack Lambda SQS ESM: **tested** — `test_lambda_esm_sqs` in `tests/test_lambda.py` (109KB file)
- MiniStack DynamoDB ConsumedCapacity precision: `ConsumedCapacity.CapacityUnits == 2.0` for put on table+1GSI, `4.0` for batch of 2 on table+1GSI — exact numeric match to AWS billing model
- MiniStack SQS `ApproximateReceiveCount` tested: `"1"` after first receive, `"2"` after re-receive — [[test_sqs.py](https://github.com/ministackorg/ministack/blob/main/tests/test_sqs.py)]

---

### Trade-offs

**When Floci's fidelity approach is better:**
- Java, .NET, Go, Ruby, and custom runtime Lambda execution: Floci uses real Docker AWS Lambda runtime images. MiniStack falls back to Docker/RIE for these, which is also real, but Floci's explicit runtime mapping table and documented Lambda test suite give more confidence.
- IAM policy enforcement: Floci has `enforcement-enabled: true` to actually deny calls based on policy. MiniStack supports IAM CRUD but offers no enforcement mode. If you're testing whether a missing IAM statement causes a 403, only Floci can do that.
- STS coverage: Floci documents all 7 STS operations. MiniStack is thinner here.

**When MiniStack's fidelity approach is better:**
- DynamoDB today (April 2026): Two critical Floci bugs (#587, #571) affect GSI pagination and atomic counters. MiniStack has no open DynamoDB bugs and a significantly larger test suite.
- Lambda nested module paths: MiniStack explicitly fixed and regression-tested this. Floci's #547 is still open.
- SQS FIFO deduplication scopes and system attributes: MiniStack's tests are more granular (DeduplicationScope, `ApproximateReceiveCount`, delay semantics).
- S3 response shape fidelity: MiniStack tests `BucketArn` and `BucketRegion` in `ListBuckets`; Floci does not.
- End-to-end SQS→Lambda ESM: MiniStack tests this end-to-end; Floci does not in its published compatibility suite.
- Python/Node Lambda cold-start simulation: Neither tool simulates cold-start accurately, but MiniStack is transparent about using warm workers, whereas Floci's warm pool bugs (#485) make cold/warm behavior unpredictably wrong under timeout conditions.
- Athena SQL execution: MiniStack executes real SQL via DuckDB. Floci returns empty results.

**When the fidelity gap affects CI reliability vs. local dev differently:**
- Floci's Lambda→S3 DNS bug (#432) only manifests when Lambda runs inside Docker containers and uses virtual-hosted-style S3 addressing. In CI with `network_mode: host`, it may be masked. In Testcontainers (bridge networking by default), it will fail silently.
- Floci's DynamoDB concurrency bug (#571) only manifests under concurrent load. Sequential CI tests won't trigger it. A load test or parallel CI suite will.
- MiniStack's S3Control tag bug (#447) only matters for Terraform provider v6 with `default_tags`. Pre-v6 Terraform is unaffected.

---

### Confidence

**High confidence:**
- Floci DynamoDB GSI pagination bug (#587): Confirmed by code-level analysis (DynamoDbService.java#L500-515), reproducer script, and precise description of the root cause.
- Floci Lambda→S3 DNS bug (#432): Confirmed by DNS trace (`nslookup` from inside container), network topology analysis, and multiple verified workarounds.
- MiniStack S3Control tag bug (#447): Confirmed by code-level root cause analysis (`ministack/app.py:614-670`), Terraform trace log, and state file inspection.
- Floci Lambda nested handler bug (#547): Confirmed by code reference (`LambdaService.java:933`), reproducer, and matching MiniStack fix in test suite.

**Medium confidence:**
- Floci DynamoDB atomic counter bug (#571): Submitted with a Java async client reproducer. The fix is straightforward (add partition-level serialization), but the issue is labeled `pending-validation` which suggests it may have a narrower scope than described.
- MiniStack Lambda execution fidelity for Python/Node (warm workers): The test suite is comprehensive but warm workers bypass the real Lambda Runtime API. Subtle Runtime API behavior (extensions, `/runtime/init/error`, `/runtime/invocation/response` headers) is not validated.
- ETag format fidelity: No evidence from either tool's test suite about multipart ETag format (`<md5>-<N>`). Neither has a known open bug on this, but it's an untested claim.
- Floci "1,850+ tests with 100% pass rate": Count verified in README. The claim of 100% pass rate is self-reported and not verifiable from a public CI dashboard. The CHANGELOG shows ongoing bug fixes to the same services these tests cover, which is inconsistent with a clean pass on the current revision.

**Unresolved:**
- Neither tool has been independently benchmarked against AWS SDK conformance tests (e.g., the `smithy-rs` protocol tests or the official `aws-sdk-java-v2` wire protocol tests). The fidelity claims are based on self-authored test suites, which can have blind spots.
- SQS ReceiptHandle format: AWS returns a URL-encoded, opaque base64 string. Neither tool's tests validate the token format. An application that encodes a predictable internal state into ReceiptHandle (which real AWS doesn't do) would still work against both tools but could expose the emulator's implementation details.

---

### New Questions

1. **DynamoDB Transactions under concurrency**: Given Floci's confirmed non-serialized `UpdateItem`, does `TransactWriteItems` provide correct isolation? The concurrency bug in atomic counters suggests the underlying DynamoDB write serialization is broken — if `TransactWriteItems` shares the same write path, transaction isolation guarantees may be violated in ways that only appear under concurrent load.

2. **Lambda Runtime API fidelity**: MiniStack uses warm workers that bypass the Lambda Runtime API (`/runtime/invocation/next`, `/runtime/invocation/{id}/response`). Extensions and Lambda Powertools components that hook into the Runtime API lifecycle (init, shutdown hooks) depend on these endpoints. Neither tool's test suite covers Lambda extensions or Runtime API lifecycle. This is an untested dimension that could affect teams using Lambda Powertools or custom layers.

3. **CloudFormation resource coverage vs. real IaC stacks**: Both tools list CloudFormation support but no tool publishes a resource-type coverage matrix comparable to the AWS CloudFormation registry. Floci has IaC compatibility tests (14 Terraform, 14 OpenTofu, 17 CDK tests), but these cover narrow scenarios. The real question — how many production-style CDK/Terraform stacks with S3, Lambda, SQS, SNS, API Gateway, DynamoDB, IAM, Step Functions resources deploy successfully with zero manual workarounds — remains unanswered for both tools.

---

## Peer Review (codex-cli)

I found 10 material issues.

### Issue 1: Floci test counts are factually wrong
- **Type**: factual error
- **Location**: “Java 889, Node 360, Python 264, Go 136, AWS CLI 145, Rust 86, IaC 45 = **1,850+ total**”
- **Problem**: Floci’s current README shows **889 / 360 / 264 / 120 / 138 / 69 / 14 / 14 / 5 = 1,873**, not the numbers quoted here. Several per-module counts are off.
- **Impact**: Weakens confidence in the evidence section because the easiest-to-verify numbers are inaccurate.

### Issue 2: `ListBuckets` / `BucketArn` claim is likely wrong for general-purpose buckets
- **Type**: factual error
- **Location**: “`ListBuckets` must return `BucketArn` (`arn:aws:s3:::{bucket}`) and `BucketRegion` per item”
- **Problem**: AWS docs say `BucketArn` in `ListBuckets` is **only supported for directory buckets**, not ordinary general-purpose buckets. So presenting `arn:aws:s3:::{bucket}` as a general fidelity target is misleading.
- **Impact**: This may invert the conclusion: a test could be asserting behavior that AWS itself does not guarantee for normal buckets.

### Issue 3: `BucketRegion` nuance is missing
- **Type**: missing nuance
- **Location**: same `ListBuckets` passage
- **Problem**: AWS docs say `BucketRegion` is included **if the request contains at least one valid parameter**. The finding states it as an unconditional per-item fidelity field.
- **Impact**: Overstates MiniStack fidelity and understates the conditional nature of AWS’s actual response shape.

### Issue 4: ETag discussion oversimplifies AWS behavior
- **Type**: missing nuance
- **Location**: “ETag format (MD5 for single-part uploads vs. `<md5>-<N>` for multipart)”
- **Problem**: AWS explicitly says an S3 ETag **may or may not** be an MD5 digest. For SSE-KMS/SSE-C objects, even single-request uploads are not MD5-based. Multipart ETags also are not a stable general-purpose checksum contract.
- **Impact**: The review frames ETag fidelity too narrowly and risks judging emulators against an incomplete AWS model.

### Issue 5: ReceiptHandle format claim is unsupported and overly specific
- **Type**: unsupported claim
- **Location**: “AWS returns a URL-encoded, opaque base64 string.”
- **Problem**: AWS docs describe ReceiptHandle as a unique handle tied to a receive action, but do **not** promise “URL-encoded base64” as a compatibility contract.
- **Impact**: Introduces a spec claim that is stricter than the public AWS contract.

### Issue 6: The more important SQS ReceiptHandle fidelity check was missed
- **Type**: gap
- **Location**: “Neither explicitly tests that the token is opaque…”
- **Problem**: The bigger AWS-compatibility behavior is that **each receive returns a new ReceiptHandle**, and using an old one may succeed but not actually delete the message. That is documented AWS behavior and is more important than whether the token is “decodable.”
- **Impact**: The analysis focuses on a low-value property and misses a high-value one.

### Issue 7: “No open SQS bugs” / “zero open DynamoDB bugs” is not evidence of correctness
- **Type**: unsupported claim
- **Location**: “No open SQS bugs in either repo…” and “**MiniStack** has zero open DynamoDB bugs.”
- **Problem**: Absence of open issues is not proof of absence of defects. It may reflect coverage gaps, labeling, or unreported bugs. The finding sometimes treats issue counts as fidelity evidence.
- **Impact**: Biases the comparison toward “no reported bug == correct,” which is not a sound review standard.

### Issue 8: The Floci GSI pagination conclusion is too absolute
- **Type**: unsupported claim
- **Location**: “**Any application** using `ExclusiveStartKey` pagination on a GSI where items share the same index sort key **will hang forever**”
- **Problem**: The reproducer supports a severe duplicate-page bug, but “any application” and “hang forever” are too strong. Some clients cap page count, detect repeated cursors, or stop on duplicate IDs.
- **Impact**: Overstates certainty and makes the report sound less rigorous than the underlying bug actually is.

### Issue 9: DynamoDB “internal partition-level locking” is presented as fact without AWS support
- **Type**: unsupported claim
- **Location**: “Real DynamoDB serializes these via internal partition-level locking.”
- **Problem**: AWS documents atomicity and ordered application of writes, but not the internal mechanism as “partition-level locking.” That is implementation speculation.
- **Impact**: Blurs the line between observed behavior and hypothesized root cause.

### Issue 10: Lambda fidelity conclusions are internally overstated
- **Type**: missing nuance
- **Location**: “This is the strongest possible fidelity approach for Lambda.” and later “Neither tool simulates cold-start accurately”
- **Problem**: Using AWS runtime images improves runtime environment fidelity, but Lambda fidelity also depends on Runtime API lifecycle, networking, init/shutdown semantics, `/tmp`, extensions, concurrency, throttling, and event source integration. The report later admits important gaps, which undercuts the earlier superlative.
- **Impact**: The Lambda section mixes a strong headline claim with later caveats that materially limit that claim.

## Summary
- **Issues found**: 10
- **Overall reliability**: **Medium**
- **What would most improve the findings**:  
  1. Re-verify all numeric counts and repo snapshot claims.  
  2. Separate **documented AWS behavior** from **inference/root-cause theory**.  
  3. Add missing AWS nuance for `ListBuckets`, ETags, and SQS receipt handles.  
  4. Replace “no open bugs” reasoning with direct evidence from tests or reproductions.

**Sources used**:  
- Floci README: https://raw.githubusercontent.com/floci-io/floci/main/README.md  
- Floci issue #432: https://github.com/floci-io/floci/issues/432  
- AWS S3 `ListBuckets`: https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListBuckets.html  
- AWS S3 `Bucket` shape: https://docs.aws.amazon.com/AmazonS3/latest/API/API_Bucket.html  
- AWS S3Control `TagResource`: https://docs.aws.amazon.com/AmazonS3/latest/API/API_control_TagResource.html  
- AWS S3 ETag docs: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/objectsummary/e_tag.html  
- AWS SQS `ReceiveMessage`: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_ReceiveMessage.html  
- AWS SQS `DeleteMessage` behavior: https://docs.aws.amazon.com/sdkfornet/v4/apidocs/items/SQS/MSQSDeleteMessageDeleteMessageRequest.html  
- AWS DynamoDB atomicity / counters: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/WorkingWithItems.html  
- AWS Lambda runtimes: https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html  
- MiniStack docs: https://ministack.org/docs  
- MiniStack PyPI page: https://pypi.org/project/ministack/
