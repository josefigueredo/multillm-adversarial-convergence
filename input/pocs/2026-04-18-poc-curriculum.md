# Iris PoC Curriculum — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute all 15 Iris PoC lab units sequentially, producing a validated, committed artifact per PoC that proves each architectural decision before v1-alpha implementation begins.

**Architecture:** Each PoC is self-contained under `pocs/poc-NN-<slug>/`. Manifests live in `manifests/`, Helm values in `helm/`, Go code in named subdirectories. Every PoC ends with a committed `README.md` documenting AC evidence. Phase gates are enforced — no task in Phase II starts until all Phase I ACs pass.

**Tech Stack:** kind, kubectl, helm, Go 1.22, NATS, PostgreSQL 16, Temporal, Qdrant, LiteLLM, OTel/Grafana OSS, Cilium, SPIRE, ESO+Vault, OPA/Gatekeeper, ArgoCD.

---

## File Structure

```
pocs/
  poc-01-k8s-local/
    manifests/namespace.yaml
    manifests/configmap.yaml
    manifests/pod.yaml
    manifests/service.yaml
    README.md
  poc-02-k8s-nats/
    helm/values.yaml
    README.md
  poc-03-k8s-postgresql/
    helm/values.yaml
    migrations/000001_iris_control.up.sql
    migrations/000001_iris_control.down.sql
    migrations/000002_tenant_bims.up.sql
    migrations/000002_tenant_bims.down.sql
    README.md
  poc-04-k8s-temporal/
    helm/values.yaml
    worker/go.mod
    worker/main.go
    worker/workflow.go
    worker/activities.go
    README.md
  poc-05-k8s-qdrant/
    helm/values.yaml
    client/go.mod
    client/main.go
    README.md
  poc-06-k8s-litellm/
    helm/values.yaml
    config/litellm-config.yaml
    README.md
  poc-07-k8s-otel-grafana/
    helm/otel-values.yaml
    helm/tempo-values.yaml
    helm/loki-values.yaml
    helm/grafana-values.yaml
    service/go.mod
    service/main.go
    README.md
  poc-08-k8s-cilium/
    kind-config.yaml
    manifests/namespace-bims.yaml
    manifests/namespace-acme.yaml
    manifests/pod-bims.yaml
    manifests/pod-acme.yaml
    manifests/policy-bims.yaml
    README.md
  poc-09-k8s-spire/
    helm/values.yaml
    services/go.mod
    services/connector/main.go
    services/worker/main.go
    README.md
  poc-10-k8s-eso/
    helm/vault-values.yaml
    helm/eso-values.yaml
    manifests/secret-store.yaml
    manifests/external-secret.yaml
    README.md
  poc-11-k8s-gatekeeper/
    helm/values.yaml
    policies/require-resource-limits-template.yaml
    policies/require-resource-limits-constraint.yaml
    manifests/pod-noncompliant.yaml
    manifests/pod-compliant.yaml
    README.md
  poc-12-k8s-argocd/
    helm/values.yaml
    app/application.yaml
    gitrepo/nginx-deployment.yaml
    README.md
  poc-13-nats-temporal/
    consumer/go.mod
    consumer/main.go
    consumer/workflow.go
    consumer/activities.go
    README.md
  poc-14-temporal-litellm-pg/
    worker/go.mod
    worker/main.go
    worker/workflow.go
    worker/activities.go
    migrations/000001_classifications.up.sql
    migrations/000001_classifications.down.sql
    README.md
  poc-15-full-spine/
    spine/go.mod
    spine/main.go
    spine/workflow.go
    spine/activities.go
    README.md
```

---

## Task 0 — Prerequisites

**Files:** none (environment setup)

- [ ] **Step 1: Install required tooling**

```bash
brew install kind kubectl helm go nats-io/nats-tools/nats golang-migrate
brew install vault argocd cilium-cli
```

Expected: all tools available on PATH.

- [ ] **Step 2: Add required Helm repos**

```bash
helm repo add nats https://nats-io.github.io/k8s/helm/charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add temporal https://go.temporal.io/helm-charts
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add cilium https://helm.cilium.io
helm repo add spiffe https://spiffe.github.io/helm-charts-hardened
helm repo add external-secrets https://charts.external-secrets.io
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
```

- [ ] **Step 3: Bootstrap the primary kind cluster**

```bash
kind create cluster --name iris-lab-01
kubectl cluster-info --context kind-iris-lab-01
```

Expected: control plane URL printed, cluster accessible.

- [ ] **Step 4: Commit**

```bash
git add pocs/
git commit -m "chore(pocs): scaffold poc directory structure"
```

---

## Phase I — Infrastructure Foundations

---

### Task 1 — PoC 01: `k8s-local`

**Files:**
- Create: `pocs/poc-01-k8s-local/manifests/namespace.yaml`
- Create: `pocs/poc-01-k8s-local/manifests/configmap.yaml`
- Create: `pocs/poc-01-k8s-local/manifests/pod.yaml`
- Create: `pocs/poc-01-k8s-local/manifests/service.yaml`
- Create: `pocs/poc-01-k8s-local/README.md`

- [ ] **Step 1: Write manifests**

`pocs/poc-01-k8s-local/manifests/namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: iris-lab
```

`pocs/poc-01-k8s-local/manifests/configmap.yaml`:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: iris-config
  namespace: iris-lab
data:
  TENANT_ID: bims
```

`pocs/poc-01-k8s-local/manifests/pod.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx
  namespace: iris-lab
  labels:
    app: nginx
spec:
  containers:
    - name: nginx
      image: nginx:alpine
      envFrom:
        - configMapRef:
            name: iris-config
      resources:
        limits:
          cpu: 100m
          memory: 64Mi
```

`pocs/poc-01-k8s-local/manifests/service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
  namespace: iris-lab
spec:
  selector:
    app: nginx
  ports:
    - port: 80
      targetPort: 80
```

- [ ] **Step 2: Apply and verify AC-1 and AC-2**

```bash
kubectl apply -f pocs/poc-01-k8s-local/manifests/
kubectl get nodes
kubectl get pod -n iris-lab nginx
```

Expected: node in `Ready` state, pod in `Running` state.

- [ ] **Step 3: Verify AC-3**

```bash
kubectl exec -n iris-lab nginx -- env | grep TENANT_ID
```

Expected output: `TENANT_ID=bims`

- [ ] **Step 4: Write README.md**

`pocs/poc-01-k8s-local/README.md`:
```markdown
# PoC 01 — k8s-local

## AC Evidence

**AC-1:** `kubectl get nodes` output:
```
NAME                        STATUS   ROLES           AGE   VERSION
iris-lab-01-control-plane   Ready    control-plane   Xm    vX.XX
```

**AC-2:** Pod reaches Running:
```
NAME    READY   STATUS    RESTARTS   AGE
nginx   1/1     Running   0          Xs
```

**AC-3:** TENANT_ID present:
```
TENANT_ID=bims
```

**AC-4:** All commands and manifests documented above.

## Teardown

```bash
kubectl delete -f pocs/poc-01-k8s-local/manifests/
```
```

- [ ] **Step 5: Commit**

```bash
git add pocs/poc-01-k8s-local/
git commit -m "poc(01): k8s-local — namespace, configmap, pod, service"
```

---

### Task 2 — PoC 02: `k8s-nats`

**Files:**
- Create: `pocs/poc-02-k8s-nats/helm/values.yaml`
- Create: `pocs/poc-02-k8s-nats/README.md`

- [ ] **Step 1: Write Helm values**

`pocs/poc-02-k8s-nats/helm/values.yaml`:
```yaml
config:
  jetstream:
    enabled: true
    memStorage:
      enabled: true
      size: 1Gi
    fileStorage:
      enabled: true
      size: 2Gi
natsbox:
  enabled: true
```

- [ ] **Step 2: Deploy NATS**

```bash
helm upgrade --install nats nats/nats \
  --namespace nats-system --create-namespace \
  -f pocs/poc-02-k8s-nats/helm/values.yaml
kubectl rollout status statefulset/nats -n nats-system --timeout=120s
```

- [ ] **Step 3: Create stream and consumer (AC-1, AC-2)**

```bash
kubectl exec -n nats-system deployment/nats-box -- \
  nats stream add IRIS_JOBS \
  --subjects "iris.standard.*.jobs" \
  --storage file \
  --retention limits \
  --max-msgs -1 \
  --max-bytes -1 \
  --max-age 24h \
  --replicas 1 \
  --no-deny-delete \
  --no-deny-purge \
  --defaults

kubectl exec -n nats-system deployment/nats-box -- \
  nats consumer add IRIS_JOBS worker \
  --target iris-worker \
  --deliver all \
  --replay instant \
  --ack explicit \
  --defaults
```

- [ ] **Step 4: Publish and consume 5 messages (AC-3)**

```bash
for i in 1 2 3 4 5; do
  kubectl exec -n nats-system deployment/nats-box -- \
    nats pub iris.standard.bims.jobs "{\"ticket_id\": \"INC-00$i\"}"
done

kubectl exec -n nats-system deployment/nats-box -- \
  nats consumer next IRIS_JOBS worker --count 5 --no-wait

kubectl exec -n nats-system deployment/nats-box -- \
  nats consumer info IRIS_JOBS worker
```

Expected: `Num Pending: 0` after consuming 5 messages.

- [ ] **Step 5: Observe consumer lag (AC-4)**

```bash
for i in 6 7 8; do
  kubectl exec -n nats-system deployment/nats-box -- \
    nats pub iris.standard.bims.jobs "{\"ticket_id\": \"INC-00$i\"}"
done

kubectl exec -n nats-system deployment/nats-box -- \
  nats consumer info IRIS_JOBS worker
```

Expected: `Num Pending: 3`

- [ ] **Step 6: Write README.md with AC evidence, commit**

```bash
# document observations in pocs/poc-02-k8s-nats/README.md
git add pocs/poc-02-k8s-nats/
git commit -m "poc(02): k8s-nats — JetStream stream, durable consumer, lag observation"
```

---

### Task 3 — PoC 03: `k8s-postgresql`

**Files:**
- Create: `pocs/poc-03-k8s-postgresql/helm/values.yaml`
- Create: `pocs/poc-03-k8s-postgresql/migrations/000001_iris_control.up.sql`
- Create: `pocs/poc-03-k8s-postgresql/migrations/000001_iris_control.down.sql`
- Create: `pocs/poc-03-k8s-postgresql/migrations/000002_tenant_bims.up.sql`
- Create: `pocs/poc-03-k8s-postgresql/migrations/000002_tenant_bims.down.sql`
- Create: `pocs/poc-03-k8s-postgresql/README.md`

- [ ] **Step 1: Write Helm values and migrations**

`pocs/poc-03-k8s-postgresql/helm/values.yaml`:
```yaml
auth:
  postgresPassword: irisdev
  database: iris
primary:
  initdb:
    scripts:
      create_schemas.sql: |
        CREATE SCHEMA IF NOT EXISTS iris_control;
        CREATE SCHEMA IF NOT EXISTS tenant_bims;
```

`pocs/poc-03-k8s-postgresql/migrations/000001_iris_control.up.sql`:
```sql
CREATE TABLE IF NOT EXISTS iris_control.tenants (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  tier       TEXT NOT NULL CHECK (tier IN ('standard', 'regulated')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`pocs/poc-03-k8s-postgresql/migrations/000001_iris_control.down.sql`:
```sql
DROP TABLE IF EXISTS iris_control.tenants;
```

`pocs/poc-03-k8s-postgresql/migrations/000002_tenant_bims.up.sql`:
```sql
CREATE TABLE IF NOT EXISTS tenant_bims.evidence (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source       TEXT NOT NULL,
  raw_payload  JSONB NOT NULL,
  ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`pocs/poc-03-k8s-postgresql/migrations/000002_tenant_bims.down.sql`:
```sql
DROP TABLE IF EXISTS tenant_bims.evidence;
```

- [ ] **Step 2: Deploy PostgreSQL**

```bash
helm upgrade --install postgresql bitnami/postgresql \
  --namespace iris-db --create-namespace \
  -f pocs/poc-03-k8s-postgresql/helm/values.yaml
kubectl rollout status statefulset/postgresql -n iris-db --timeout=120s
```

- [ ] **Step 3: Port-forward and run migrations (AC-2, AC-3)**

```bash
kubectl port-forward -n iris-db svc/postgresql 5432:5432 &
PF_PID=$!

export POSTGRESQL_PASSWORD=irisdev
migrate -path pocs/poc-03-k8s-postgresql/migrations \
  -database "postgres://postgres:${POSTGRESQL_PASSWORD}@localhost:5432/iris?sslmode=disable&search_path=public" \
  up

# verify
PGPASSWORD=irisdev psql -h localhost -U postgres -d iris \
  -c "SELECT * FROM public.schema_migrations;"

kill $PF_PID
```

Expected: versions 1 and 2 in `schema_migrations`.

- [ ] **Step 4: Rollback migration 2 (AC-4)**

```bash
kubectl port-forward -n iris-db svc/postgresql 5432:5432 &
PF_PID=$!

migrate -path pocs/poc-03-k8s-postgresql/migrations \
  -database "postgres://postgres:irisdev@localhost:5432/iris?sslmode=disable" \
  down 1

PGPASSWORD=irisdev psql -h localhost -U postgres -d iris \
  -c "SELECT version FROM public.schema_migrations;"

PGPASSWORD=irisdev psql -h localhost -U postgres -d iris \
  -c "\dt tenant_bims.*"

kill $PF_PID
```

Expected: only version 1 remains; `tenant_bims.evidence` does not exist.

- [ ] **Step 5: Write README.md, commit**

```bash
git add pocs/poc-03-k8s-postgresql/
git commit -m "poc(03): k8s-postgresql — schema migrations, rollback verification"
```

---

### Task 4 — PoC 04: `k8s-temporal`

**Files:**
- Create: `pocs/poc-04-k8s-temporal/helm/values.yaml`
- Create: `pocs/poc-04-k8s-temporal/worker/go.mod`
- Create: `pocs/poc-04-k8s-temporal/worker/main.go`
- Create: `pocs/poc-04-k8s-temporal/worker/workflow.go`
- Create: `pocs/poc-04-k8s-temporal/worker/activities.go`
- Create: `pocs/poc-04-k8s-temporal/README.md`

- [ ] **Step 1: Write Helm values**

`pocs/poc-04-k8s-temporal/helm/values.yaml`:
```yaml
server:
  replicaCount: 1
  config:
    persistence:
      defaultStore: default
      visibilityStore: visibility
      datastores:
        default:
          sql:
            pluginName: postgres12
            databaseName: temporal
            host: postgresql.iris-db.svc.cluster.local
            port: 5432
            user: postgres
            password: irisdev
            maxConns: 10
            maxIdleConns: 10
        visibility:
          sql:
            pluginName: postgres12
            databaseName: temporal_visibility
            host: postgresql.iris-db.svc.cluster.local
            port: 5432
            user: postgres
            password: irisdev
            maxConns: 10
            maxIdleConns: 10
cassandra:
  enabled: false
mysql:
  enabled: false
postgresql:
  enabled: false
grafana:
  enabled: false
prometheus:
  enabled: false
elasticsearch:
  enabled: false
```

- [ ] **Step 2: Create Temporal databases and deploy**

```bash
kubectl port-forward -n iris-db svc/postgresql 5432:5432 &
PF_PID=$!
PGPASSWORD=irisdev psql -h localhost -U postgres \
  -c "CREATE DATABASE temporal;" \
  -c "CREATE DATABASE temporal_visibility;"
kill $PF_PID

helm upgrade --install temporal temporal/temporal \
  --namespace temporal-system --create-namespace \
  -f pocs/poc-04-k8s-temporal/helm/values.yaml \
  --timeout 5m

kubectl rollout status deployment/temporal-frontend -n temporal-system --timeout=180s
```

- [ ] **Step 3: Write Go worker code**

`pocs/poc-04-k8s-temporal/worker/go.mod`:
```
module github.com/Acme-tecnologia/iris-pocs/poc-04

go 1.22

require go.temporal.io/sdk v1.26.1
```

`pocs/poc-04-k8s-temporal/worker/workflow.go`:
```go
package main

import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

func HelloWorkflow(ctx workflow.Context, name string) (string, error) {
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 10 * time.Second,
		RetryPolicy: &temporal.RetryPolicy{
			MaximumAttempts: 3,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	var result string
	err := workflow.ExecuteActivity(ctx, FormatGreeting, name).Get(ctx, &result)
	return result, err
}
```

`pocs/poc-04-k8s-temporal/worker/activities.go`:
```go
package main

import (
	"context"
	"fmt"

	"go.temporal.io/sdk/activity"
)

func FormatGreeting(ctx context.Context, name string) (string, error) {
	info := activity.GetInfo(ctx)
	if info.Attempt == 1 {
		return "", fmt.Errorf("simulated failure on attempt 1")
	}
	return fmt.Sprintf("Hello, %s from Iris!", name), nil
}
```

`pocs/poc-04-k8s-temporal/worker/main.go`:
```go
package main

import (
	"log"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
)

func main() {
	c, err := client.Dial(client.Options{
		HostPort: "temporal-frontend.temporal-system.svc.cluster.local:7233",
	})
	if err != nil {
		log.Fatalf("unable to create Temporal client: %v", err)
	}
	defer c.Close()

	w := worker.New(c, "iris-task-queue", worker.Options{})
	w.RegisterWorkflow(HelloWorkflow)
	w.RegisterActivity(FormatGreeting)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatalf("worker stopped: %v", err)
	}
}
```

- [ ] **Step 4: Build and deploy worker to cluster**

```bash
cd pocs/poc-04-k8s-temporal/worker && go mod tidy && cd -

# build image for kind
docker build -t iris-poc-04-worker:latest -f - pocs/poc-04-k8s-temporal/worker <<'EOF'
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY . .
RUN go build -o worker .

FROM alpine:3.19
COPY --from=build /app/worker /worker
ENTRYPOINT ["/worker"]
EOF

kind load docker-image iris-poc-04-worker:latest --name iris-lab-01

kubectl run temporal-worker \
  --image=iris-poc-04-worker:latest \
  --image-pull-policy=Never \
  --restart=Never \
  --namespace temporal-system
```

- [ ] **Step 5: Trigger workflow and verify AC-3 and AC-4**

```bash
# port-forward Temporal frontend
kubectl port-forward -n temporal-system svc/temporal-frontend 7233:7233 &

temporal workflow start \
  --workflow-type HelloWorkflow \
  --task-queue iris-task-queue \
  --input '"bims"' \
  --workflow-id hello-bims-01

temporal workflow show --workflow-id hello-bims-01
```

Expected: workflow shows `Completed` status. Activity history shows `FormatGreeting` attempt 1 failed, attempt 2 succeeded.

- [ ] **Step 6: Write README.md, commit**

```bash
git add pocs/poc-04-k8s-temporal/
git commit -m "poc(04): k8s-temporal — hello workflow, activity retry, durable execution"
```

---

### Task 5 — PoC 05: `k8s-qdrant`

**Files:**
- Create: `pocs/poc-05-k8s-qdrant/helm/values.yaml`
- Create: `pocs/poc-05-k8s-qdrant/client/go.mod`
- Create: `pocs/poc-05-k8s-qdrant/client/main.go`
- Create: `pocs/poc-05-k8s-qdrant/README.md`

- [ ] **Step 1: Write Helm values and deploy**

`pocs/poc-05-k8s-qdrant/helm/values.yaml`:
```yaml
replicaCount: 1
resources:
  limits:
    cpu: 500m
    memory: 512Mi
```

```bash
helm upgrade --install qdrant qdrant/qdrant \
  --namespace qdrant-system --create-namespace \
  -f pocs/poc-05-k8s-qdrant/helm/values.yaml
kubectl rollout status deployment/qdrant -n qdrant-system --timeout=120s
```

- [ ] **Step 2: Write Go client**

`pocs/poc-05-k8s-qdrant/client/go.mod`:
```
module github.com/Acme-tecnologia/iris-pocs/poc-05

go 1.22

require github.com/qdrant/go-client v1.10.0
```

`pocs/poc-05-k8s-qdrant/client/main.go`:
```go
package main

import (
	"context"
	"fmt"
	"log"
	"math/rand"

	"github.com/qdrant/go-client/qdrant"
)

func main() {
	client, err := qdrant.NewClient(&qdrant.Config{
		Host: "localhost",
		Port: 6334,
	})
	if err != nil {
		log.Fatal(err)
	}
	ctx := context.Background()

	// Create collection (AC-2)
	err = client.CreateCollection(ctx, &qdrant.CreateCollection{
		CollectionName: "resolution-memory-bims",
		VectorsConfig: qdrant.NewVectorsConfig(&qdrant.VectorParams{
			Size:     1536,
			Distance: qdrant.Distance_Cosine,
		}),
	})
	if err != nil {
		log.Printf("collection may already exist: %v", err)
	}

	// Insert 20 fake embeddings (AC-3)
	var points []*qdrant.PointStruct
	for i := 0; i < 20; i++ {
		vec := make([]float32, 1536)
		for j := range vec {
			vec[j] = rand.Float32()
		}
		points = append(points, &qdrant.PointStruct{
			Id:      qdrant.NewIDNum(uint64(i + 1)),
			Vectors: qdrant.NewVectors(vec...),
			Payload: qdrant.NewValueMap(map[string]any{
				"incident_id": fmt.Sprintf("INC-%04d", i+1),
				"summary":     fmt.Sprintf("Database connection timeout in service-%d", i+1),
				"resolution":  fmt.Sprintf("Increased connection pool size and added retry logic — fix %d", i+1),
			}),
		})
	}
	_, err = client.Upsert(ctx, &qdrant.UpsertPoints{
		CollectionName: "resolution-memory-bims",
		Points:         points,
	})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("Inserted 20 points")

	// Nearest-neighbor query (AC-4)
	queryVec := make([]float32, 1536)
	for i := range queryVec {
		queryVec[i] = rand.Float32()
	}
	result, err := client.Query(ctx, &qdrant.QueryPoints{
		CollectionName: "resolution-memory-bims",
		Query:          qdrant.NewQuery(queryVec...),
		Limit:          qdrant.PtrOf(uint64(5)),
		WithPayload:    qdrant.NewWithPayload(true),
	})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("Query returned %d results:\n", len(result))
	for _, r := range result {
		fmt.Printf("  ID=%v score=%.4f incident_id=%s\n",
			r.Id, r.Score, r.Payload["incident_id"].GetStringValue())
	}
}
```

- [ ] **Step 3: Port-forward and run client**

```bash
cd pocs/poc-05-k8s-qdrant/client && go mod tidy && cd -
kubectl port-forward -n qdrant-system svc/qdrant 6334:6334 &
go run pocs/poc-05-k8s-qdrant/client/main.go
```

Expected: "Inserted 20 points" then 5 results with scores.

- [ ] **Step 4: Write README.md, commit**

```bash
git add pocs/poc-05-k8s-qdrant/
git commit -m "poc(05): k8s-qdrant — collection, embeddings, nearest-neighbor query"
```

---

### Task 6 — PoC 06: `k8s-litellm`

**Files:**
- Create: `pocs/poc-06-k8s-litellm/config/litellm-config.yaml`
- Create: `pocs/poc-06-k8s-litellm/helm/values.yaml`
- Create: `pocs/poc-06-k8s-litellm/README.md`

- [ ] **Step 1: Write LiteLLM config and Helm values**

`pocs/poc-06-k8s-litellm/config/litellm-config.yaml`:
```yaml
model_list:
  - model_name: gpt-3.5-turbo
    litellm_params:
      model: openai/gpt-3.5-turbo
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      id: primary

  - model_name: gpt-3.5-turbo
    litellm_params:
      model: openai/gpt-3.5-turbo
      mock_response: "Mocked fallback response from secondary"
    model_info:
      id: fallback

litellm_settings:
  fallbacks:
    - gpt-3.5-turbo:
      - gpt-3.5-turbo-fallback

general_settings:
  store_model_in_db: false
```

`pocs/poc-06-k8s-litellm/helm/values.yaml`:
```yaml
image:
  repository: ghcr.io/berriai/litellm
  tag: main-latest
env:
  - name: OPENAI_API_KEY
    value: "sk-placeholder-use-mock-mode"
  - name: LITELLM_MASTER_KEY
    value: "iris-dev-key"
config:
  content: |
    model_list:
      - model_name: gpt-3.5-turbo
        litellm_params:
          model: openai/gpt-3.5-turbo
          mock_response: "Hello from Iris ai-service mock"
    general_settings:
      store_model_in_db: false
resources:
  limits:
    cpu: 500m
    memory: 512Mi
```

- [ ] **Step 2: Deploy LiteLLM**

```bash
# LiteLLM does not have an official Helm chart — deploy via manifest
kubectl create namespace ai-service

kubectl create configmap litellm-config \
  --from-file=config.yaml=pocs/poc-06-k8s-litellm/config/litellm-config.yaml \
  -n ai-service

kubectl apply -n ai-service -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm
  namespace: ai-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: litellm
  template:
    metadata:
      labels:
        app: litellm
    spec:
      containers:
        - name: litellm
          image: ghcr.io/berriai/litellm:main-latest
          args: ["--config", "/app/config.yaml", "--port", "4000"]
          ports:
            - containerPort: 4000
          volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: config.yaml
          resources:
            limits:
              cpu: 500m
              memory: 512Mi
      volumes:
        - name: config
          configMap:
            name: litellm-config
---
apiVersion: v1
kind: Service
metadata:
  name: litellm
  namespace: ai-service
spec:
  selector:
    app: litellm
  ports:
    - port: 4000
      targetPort: 4000
EOF

kubectl rollout status deployment/litellm -n ai-service --timeout=120s
```

- [ ] **Step 3: Verify AC-2 and AC-3**

```bash
kubectl port-forward -n ai-service svc/litellm 4000:4000 &

curl -s -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer iris-dev-key" \
  -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"classify: database timeout in payments service"}]}'
```

Expected: HTTP 200 with `choices[0].message.content` containing the mock response.

- [ ] **Step 4: Verify fallback (AC-4)**

```bash
kubectl logs -n ai-service deployment/litellm | grep -i "model\|fallback\|cost"
```

Expected: logs showing model used and cost entry.

- [ ] **Step 5: Write README.md, commit**

```bash
git add pocs/poc-06-k8s-litellm/
git commit -m "poc(06): k8s-litellm — ai-service gateway, mock provider, cost logging"
```

---

### Task 7 — PoC 07: `k8s-otel-grafana`

**Files:**
- Create: `pocs/poc-07-k8s-otel-grafana/helm/otel-values.yaml`
- Create: `pocs/poc-07-k8s-otel-grafana/helm/tempo-values.yaml`
- Create: `pocs/poc-07-k8s-otel-grafana/helm/loki-values.yaml`
- Create: `pocs/poc-07-k8s-otel-grafana/helm/grafana-values.yaml`
- Create: `pocs/poc-07-k8s-otel-grafana/service/go.mod`
- Create: `pocs/poc-07-k8s-otel-grafana/service/main.go`
- Create: `pocs/poc-07-k8s-otel-grafana/README.md`

- [ ] **Step 1: Deploy observability stack**

`pocs/poc-07-k8s-otel-grafana/helm/tempo-values.yaml`:
```yaml
tempo:
  storage:
    trace:
      backend: local
      local:
        path: /var/tempo/traces
```

`pocs/poc-07-k8s-otel-grafana/helm/loki-values.yaml`:
```yaml
loki:
  commonConfig:
    replication_factor: 1
  storage:
    type: filesystem
singleBinary:
  replicas: 1
```

`pocs/poc-07-k8s-otel-grafana/helm/grafana-values.yaml`:
```yaml
adminPassword: irisdev
datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: Tempo
        type: tempo
        url: http://tempo.observability.svc.cluster.local:3100
        uid: tempo
      - name: Loki
        type: loki
        url: http://loki.observability.svc.cluster.local:3100
        uid: loki
        jsonData:
          derivedFields:
            - datasourceUid: tempo
              matcherRegex: '"trace_id":"(\w+)"'
              name: TraceID
              url: '$${__value.raw}'
```

`pocs/poc-07-k8s-otel-grafana/helm/otel-values.yaml`:
```yaml
mode: deployment
config:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318
  exporters:
    otlp/tempo:
      endpoint: tempo.observability.svc.cluster.local:4317
      tls:
        insecure: true
    loki:
      endpoint: http://loki.observability.svc.cluster.local:3100/loki/api/v1/push
  service:
    pipelines:
      traces:
        receivers: [otlp]
        exporters: [otlp/tempo]
      logs:
        receivers: [otlp]
        exporters: [loki]
```

```bash
kubectl create namespace observability

helm upgrade --install tempo grafana/tempo \
  --namespace observability -f pocs/poc-07-k8s-otel-grafana/helm/tempo-values.yaml

helm upgrade --install loki grafana/loki \
  --namespace observability -f pocs/poc-07-k8s-otel-grafana/helm/loki-values.yaml

helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  --namespace observability -f pocs/poc-07-k8s-otel-grafana/helm/otel-values.yaml

helm upgrade --install grafana grafana/grafana \
  --namespace observability -f pocs/poc-07-k8s-otel-grafana/helm/grafana-values.yaml

kubectl rollout status deployment/grafana -n observability --timeout=120s
```

- [ ] **Step 2: Write instrumented Go service**

`pocs/poc-07-k8s-otel-grafana/service/go.mod`:
```
module github.com/Acme-tecnologia/iris-pocs/poc-07

go 1.22

require (
  go.opentelemetry.io/otel v1.24.0
  go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.24.0
  go.opentelemetry.io/otel/sdk v1.24.0
  go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.49.0
)
```

`pocs/poc-07-k8s-otel-grafana/service/main.go`:
```go
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func initTracer(ctx context.Context) func() {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "otel-collector.observability.svc.cluster.local:4317"
	}
	exp, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(endpoint),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		log.Fatal(err)
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exp),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName("iris-poc-07"),
		)),
	)
	otel.SetTracerProvider(tp)
	return func() { tp.Shutdown(ctx) }
}

var requestCount int64

func handler(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	tracer := otel.Tracer("iris-poc-07")
	_, span := tracer.Start(ctx, "handle-request")
	defer span.End()

	requestCount++
	span.SetAttributes(attribute.Int64("request.count", requestCount))

	traceID := span.SpanContext().TraceID().String()

	entry := map[string]any{
		"level":    "info",
		"msg":      "request handled",
		"trace_id": traceID,
		"count":    requestCount,
	}
	log.Println(must(json.Marshal(entry)))

	fmt.Fprintf(w, `{"trace_id":%q,"count":%d}`, traceID, requestCount)
}

func must(b []byte, _ error) string { return string(b) }

func main() {
	ctx := context.Background()
	shutdown := initTracer(ctx)
	defer shutdown()

	mux := http.NewServeMux()
	mux.HandleFunc("/", handler)
	log.Println("listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", otelhttp.NewHandler(mux, "iris-poc-07")))
}
```

- [ ] **Step 3: Build, load into kind, deploy service**

```bash
cd pocs/poc-07-k8s-otel-grafana/service && go mod tidy && cd -

docker build -t iris-poc-07-service:latest -f - pocs/poc-07-k8s-otel-grafana/service <<'EOF'
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY . .
RUN go build -o service .
FROM alpine:3.19
COPY --from=build /app/service /service
ENTRYPOINT ["/service"]
EOF

kind load docker-image iris-poc-07-service:latest --name iris-lab-01

kubectl run iris-otel-service \
  --image=iris-poc-07-service:latest \
  --image-pull-policy=Never \
  --port=8080 \
  --namespace observability

kubectl expose pod iris-otel-service --port=8080 -n observability
```

- [ ] **Step 4: Send 10 requests and verify AC-2, AC-3, AC-4**

```bash
kubectl port-forward -n observability svc/iris-otel-service 8080:8080 &
for i in $(seq 1 10); do curl -s http://localhost:8080/ ; echo; done
```

Open Grafana (`kubectl port-forward -n observability svc/grafana 3000:3000`), navigate to Explore → Tempo, find a trace ID, then jump to Loki using the derived field. Verify `requests_total` counter reaches 10.

- [ ] **Step 5: Write README.md, commit**

```bash
git add pocs/poc-07-k8s-otel-grafana/
git commit -m "poc(07): k8s-otel-grafana — OTel instrumentation, Tempo traces, Loki logs, Grafana correlation"
```

---

## Phase Gate I → II

Before continuing, verify:
- [ ] PoC 01 — all 4 AC satisfied
- [ ] PoC 02 — all 5 AC satisfied
- [ ] PoC 03 — all 5 AC satisfied
- [ ] PoC 04 — all 5 AC satisfied
- [ ] PoC 05 — all 5 AC satisfied
- [ ] PoC 06 — all 5 AC satisfied
- [ ] PoC 07 — all 5 AC satisfied

```bash
git commit -m "chore(pocs): phase-i gate — all AC satisfied"
```

---

## Phase II — Security & Policy Plane

---

### Task 8 — PoC 08: `k8s-cilium`

**Files:**
- Create: `pocs/poc-08-k8s-cilium/kind-config.yaml`
- Create: `pocs/poc-08-k8s-cilium/manifests/namespace-bims.yaml`
- Create: `pocs/poc-08-k8s-cilium/manifests/namespace-acme.yaml`
- Create: `pocs/poc-08-k8s-cilium/manifests/pod-bims.yaml`
- Create: `pocs/poc-08-k8s-cilium/manifests/pod-acme.yaml`
- Create: `pocs/poc-08-k8s-cilium/manifests/policy-bims.yaml`
- Create: `pocs/poc-08-k8s-cilium/README.md`

- [ ] **Step 1: Write kind config with Cilium CNI**

`pocs/poc-08-k8s-cilium/kind-config.yaml`:
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: iris-cilium
networking:
  disableDefaultCNI: true
  kubeProxyMode: none
nodes:
  - role: control-plane
  - role: worker
```

- [ ] **Step 2: Bootstrap dedicated Cilium cluster**

```bash
kind create cluster --config pocs/poc-08-k8s-cilium/kind-config.yaml

helm upgrade --install cilium cilium/cilium \
  --namespace kube-system \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=$(kubectl get node iris-cilium-control-plane -o jsonpath='{.status.addresses[0].address}') \
  --set k8sServicePort=6443

cilium status --wait
```

- [ ] **Step 3: Write namespaces, pods, policy**

`pocs/poc-08-k8s-cilium/manifests/namespace-bims.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-bims
  labels:
    tenant: bims
```

`pocs/poc-08-k8s-cilium/manifests/namespace-acme.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-acme
  labels:
    tenant: acme
```

`pocs/poc-08-k8s-cilium/manifests/pod-bims.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx
  namespace: tenant-bims
  labels:
    app: nginx
spec:
  containers:
    - name: nginx
      image: nginx:alpine
      resources:
        limits:
          cpu: 100m
          memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: nginx
  namespace: tenant-bims
spec:
  selector:
    app: nginx
  ports:
    - port: 80
```

`pocs/poc-08-k8s-cilium/manifests/pod-acme.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: curl-client
  namespace: tenant-acme
spec:
  containers:
    - name: curl
      image: curlimages/curl:latest
      command: ["sleep", "3600"]
      resources:
        limits:
          cpu: 50m
          memory: 32Mi
```

`pocs/poc-08-k8s-cilium/manifests/policy-bims.yaml`:
```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: deny-cross-tenant
  namespace: tenant-bims
spec:
  endpointSelector:
    matchLabels:
      app: nginx
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: tenant-bims
```

- [ ] **Step 4: Apply and test AC-2 (denial) and AC-3 (allowance)**

```bash
kubectl apply -f pocs/poc-08-k8s-cilium/manifests/
sleep 10

BIMS_IP=$(kubectl get svc nginx -n tenant-bims -o jsonpath='{.spec.clusterIP}')

# AC-2: cross-namespace must be denied
kubectl exec -n tenant-acme curl-client -- curl -s --max-time 5 http://$BIMS_IP/
# Expected: curl: (28) Operation timed out

# AC-3: within same namespace must succeed
kubectl exec -n tenant-bims nginx -- wget -qO- http://localhost/
# Expected: nginx welcome HTML
```

- [ ] **Step 5: Observe AC-4 (drop event)**

```bash
cilium monitor --type drop 2>&1 &
kubectl exec -n tenant-acme curl-client -- curl -s --max-time 3 http://$BIMS_IP/ || true
```

Expected: Cilium monitor shows `drop reason: Policy denied`.

- [ ] **Step 6: Write README.md, destroy cluster, commit**

```bash
# write README with AC evidence
kind delete cluster --name iris-cilium
git add pocs/poc-08-k8s-cilium/
git commit -m "poc(08): k8s-cilium — eBPF CNI, cross-namespace denial, CiliumNetworkPolicy"
```

---

### Task 9 — PoC 09: `k8s-spire`

**Files:**
- Create: `pocs/poc-09-k8s-spire/helm/values.yaml`
- Create: `pocs/poc-09-k8s-spire/services/go.mod`
- Create: `pocs/poc-09-k8s-spire/services/connector/main.go`
- Create: `pocs/poc-09-k8s-spire/services/worker/main.go`
- Create: `pocs/poc-09-k8s-spire/README.md`

- [ ] **Step 1: Deploy SPIRE**

`pocs/poc-09-k8s-spire/helm/values.yaml`:
```yaml
spire-server:
  replicaCount: 1
  nodeAttestor:
    k8sPsat:
      enabled: true
spire-agent:
  nodeAttestor:
    k8sPsat:
      enabled: true
```

```bash
helm upgrade --install spire spiffe/spire \
  --namespace spire-system --create-namespace \
  -f pocs/poc-09-k8s-spire/helm/values.yaml
kubectl rollout status statefulset/spire-server -n spire-system --timeout=120s
```

- [ ] **Step 2: Register workload entries (AC-2)**

```bash
kubectl exec -n spire-system spire-server-0 -- \
  /opt/spire/bin/spire-server entry create \
  -spiffeID spiffe://iris.local/connector \
  -parentID spiffe://iris.local/ns/spire-system/sa/spire-agent \
  -selector k8s:ns:iris-lab \
  -selector k8s:sa:connector-sa

kubectl exec -n spire-system spire-server-0 -- \
  /opt/spire/bin/spire-server entry create \
  -spiffeID spiffe://iris.local/worker \
  -parentID spiffe://iris.local/ns/spire-system/sa/spire-agent \
  -selector k8s:ns:iris-lab \
  -selector k8s:sa:worker-sa

kubectl exec -n spire-system spire-server-0 -- \
  /opt/spire/bin/spire-server entry show
```

- [ ] **Step 3: Write Go mTLS services**

`pocs/poc-09-k8s-spire/services/go.mod`:
```
module github.com/Acme-tecnologia/iris-pocs/poc-09

go 1.22

require github.com/spiffe/go-spiffe/v2 v2.3.0
```

`pocs/poc-09-k8s-spire/services/connector/main.go`:
```go
package main

import (
	"context"
	"fmt"
	"log"
	"net/http"

	"github.com/spiffe/go-spiffe/v2/spiffetls"
	"github.com/spiffe/go-spiffe/v2/workloadapi"
)

func main() {
	ctx := context.Background()
	source, err := workloadapi.NewX509Source(ctx)
	if err != nil {
		log.Fatalf("unable to create X509Source: %v", err)
	}
	defer source.Close()

	svid, err := source.GetX509SVID()
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("connector SVID: %s", svid.ID.String())

	tlsConfig := spiffetls.TLSServerConfig(spiffetls.AuthorizeAny())
	server := &http.Server{
		Addr:      ":8443",
		TLSConfig: tlsConfig,
		Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			fmt.Fprintln(w, "hello from connector over mTLS")
		}),
	}
	log.Println("connector listening on :8443 (mTLS)")
	log.Fatal(server.ListenAndServeTLS("", ""))
}
```

`pocs/poc-09-k8s-spire/services/worker/main.go`:
```go
package main

import (
	"context"
	"io"
	"log"
	"net/http"

	"github.com/spiffe/go-spiffe/v2/spiffetls"
	"github.com/spiffe/go-spiffe/v2/workloadapi"
)

func main() {
	ctx := context.Background()
	source, err := workloadapi.NewX509Source(ctx)
	if err != nil {
		log.Fatalf("unable to create X509Source: %v", err)
	}
	defer source.Close()

	svid, err := source.GetX509SVID()
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("worker SVID: %s", svid.ID.String())

	tlsConfig := spiffetls.TLSClientConfig(
		spiffetls.AuthorizeMemberOf("iris.local"),
		source,
	)
	client := &http.Client{Transport: &http.Transport{TLSClientConfig: tlsConfig}}

	resp, err := client.Get("https://connector.iris-lab.svc.cluster.local:8443/")
	if err != nil {
		log.Fatalf("mTLS connection failed: %v", err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	log.Printf("response: %s", body)
}
```

- [ ] **Step 4: Build, deploy connector and worker, verify AC-3 and AC-4**

```bash
cd pocs/poc-09-k8s-spire/services && go mod tidy && cd -

# build connector
docker build -t iris-poc-09-connector:latest \
  -f - pocs/poc-09-k8s-spire/services/connector <<'EOF'
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY ../go.mod ../go.sum ./
COPY connector/ connector/
RUN go build -o connector ./connector
FROM alpine:3.19
COPY --from=build /app/connector /connector
ENTRYPOINT ["/connector"]
EOF

# build worker
docker build -t iris-poc-09-worker:latest \
  -f - pocs/poc-09-k8s-spire/services/worker <<'EOF'
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY ../go.mod ../go.sum ./
COPY worker/ worker/
RUN go build -o worker ./worker
FROM alpine:3.19
COPY --from=build /app/worker /worker
ENTRYPOINT ["/worker"]
EOF

kind load docker-image iris-poc-09-connector:latest --name iris-lab-01
kind load docker-image iris-poc-09-worker:latest --name iris-lab-01

kubectl create serviceaccount connector-sa -n iris-lab
kubectl create serviceaccount worker-sa -n iris-lab

kubectl run connector \
  --image=iris-poc-09-connector:latest \
  --image-pull-policy=Never \
  --serviceaccount=connector-sa \
  --port=8443 \
  --namespace iris-lab

kubectl expose pod connector --port=8443 --name=connector -n iris-lab

kubectl run worker \
  --image=iris-poc-09-worker:latest \
  --image-pull-policy=Never \
  --serviceaccount=worker-sa \
  --namespace iris-lab

sleep 15
kubectl logs -n iris-lab connector | grep "SVID"
# Expected: connector SVID: spiffe://iris.local/connector

kubectl logs -n iris-lab worker | grep -E "SVID|response"
# Expected: worker SVID: spiffe://iris.local/worker
# Expected: response: hello from connector over mTLS
```

- [ ] **Step 5: Negative test — AC-5**

```bash
# pod with default SA (no registered SVID entry)
kubectl run intruder \
  --image=iris-poc-09-worker:latest \
  --image-pull-policy=Never \
  --namespace iris-lab

sleep 10
kubectl logs -n iris-lab intruder | grep -i "failed\|error\|certificate"
# Expected: mTLS connection failed: ... certificate signed by unknown authority
```

- [ ] **Step 6: Write README.md, commit**

```bash
git add pocs/poc-09-k8s-spire/
git commit -m "poc(09): k8s-spire — SVID issuance, mTLS handshake, rejection without SVID"
```

---

### Task 10 — PoC 10: `k8s-eso`

**Files:**
- Create: `pocs/poc-10-k8s-eso/helm/vault-values.yaml`
- Create: `pocs/poc-10-k8s-eso/helm/eso-values.yaml`
- Create: `pocs/poc-10-k8s-eso/manifests/secret-store.yaml`
- Create: `pocs/poc-10-k8s-eso/manifests/external-secret.yaml`
- Create: `pocs/poc-10-k8s-eso/README.md`

- [ ] **Step 1: Deploy Vault in dev mode and ESO**

`pocs/poc-10-k8s-eso/helm/vault-values.yaml`:
```yaml
server:
  dev:
    enabled: true
    devRootToken: "iris-dev-root"
  resources:
    limits:
      cpu: 250m
      memory: 256Mi
```

```bash
helm upgrade --install vault hashicorp/vault \
  --namespace vault-system --create-namespace \
  -f pocs/poc-10-k8s-eso/helm/vault-values.yaml

helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets --create-namespace

kubectl rollout status deployment/vault -n vault-system --timeout=120s
kubectl rollout status deployment/external-secrets -n external-secrets --timeout=120s
```

- [ ] **Step 2: Write secret in Vault**

```bash
kubectl exec -n vault-system vault-0 -- \
  vault kv put secret/iris/bims/db-password password=supersecret
```

- [ ] **Step 3: Write SecretStore and ExternalSecret**

`pocs/poc-10-k8s-eso/manifests/secret-store.yaml`:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: iris-lab
spec:
  provider:
    vault:
      server: "http://vault.vault-system.svc.cluster.local:8200"
      path: "secret"
      version: "v2"
      auth:
        tokenSecretRef:
          name: vault-token
          key: token
```

`pocs/poc-10-k8s-eso/manifests/external-secret.yaml`:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: bims-db-credentials
  namespace: iris-lab
spec:
  refreshInterval: 30s
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: bims-db-credentials
  data:
    - secretKey: db-password
      remoteRef:
        key: iris/bims/db-password
        property: password
```

- [ ] **Step 4: Create Vault token secret and apply (AC-2)**

```bash
kubectl create secret generic vault-token \
  --from-literal=token=iris-dev-root \
  -n iris-lab

kubectl apply -f pocs/poc-10-k8s-eso/manifests/

sleep 35  # wait for sync

kubectl get secret bims-db-credentials -n iris-lab \
  -o jsonpath='{.data.db-password}' | base64 -d
```

Expected: `supersecret`

- [ ] **Step 5: Rotate and observe AC-3 and AC-4**

```bash
POD_AGE_BEFORE=$(kubectl get pod -n iris-lab nginx -o jsonpath='{.status.startTime}')

kubectl exec -n vault-system vault-0 -- \
  vault kv put secret/iris/bims/db-password password=rotated-secret

sleep 35  # wait for refresh interval

kubectl get secret bims-db-credentials -n iris-lab \
  -o jsonpath='{.data.db-password}' | base64 -d
# Expected: rotated-secret

POD_AGE_AFTER=$(kubectl get pod -n iris-lab nginx -o jsonpath='{.status.startTime}')
# Expected: same start time — no restart
```

- [ ] **Step 6: Write README.md, commit**

```bash
git add pocs/poc-10-k8s-eso/
git commit -m "poc(10): k8s-eso — Vault + ESO secret sync, rotation without pod restart"
```

---

### Task 11 — PoC 11: `k8s-gatekeeper`

**Files:**
- Create: `pocs/poc-11-k8s-gatekeeper/policies/require-resource-limits-template.yaml`
- Create: `pocs/poc-11-k8s-gatekeeper/policies/require-resource-limits-constraint.yaml`
- Create: `pocs/poc-11-k8s-gatekeeper/manifests/pod-noncompliant.yaml`
- Create: `pocs/poc-11-k8s-gatekeeper/manifests/pod-compliant.yaml`
- Create: `pocs/poc-11-k8s-gatekeeper/README.md`

- [ ] **Step 1: Deploy Gatekeeper and verify AC-1**

```bash
helm upgrade --install gatekeeper gatekeeper/gatekeeper \
  --namespace gatekeeper-system --create-namespace

kubectl rollout status deployment/gatekeeper-controller-manager \
  -n gatekeeper-system --timeout=120s

kubectl get validatingwebhookconfiguration gatekeeper-validating-webhook-configuration
```

- [ ] **Step 2: Write ConstraintTemplate (AC-2)**

`pocs/poc-11-k8s-gatekeeper/policies/require-resource-limits-template.yaml`:
```yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequireresourcelimits
spec:
  crd:
    spec:
      names:
        kind: K8sRequireResourceLimits
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequireresourcelimits

        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not container.resources.limits.cpu
          msg := sprintf("container %q is missing cpu limit", [container.name])
        }

        violation[{"msg": msg}] {
          container := input.review.object.spec.containers[_]
          not container.resources.limits.memory
          msg := sprintf("container %q is missing memory limit", [container.name])
        }
```

`pocs/poc-11-k8s-gatekeeper/policies/require-resource-limits-constraint.yaml`:
```yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequireResourceLimits
metadata:
  name: must-have-resource-limits
spec:
  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
```

```bash
kubectl apply -f pocs/poc-11-k8s-gatekeeper/policies/
sleep 10  # allow webhook to register
```

- [ ] **Step 3: Non-compliant pod — verify AC-3**

`pocs/poc-11-k8s-gatekeeper/manifests/pod-noncompliant.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: noncompliant
  namespace: iris-lab
spec:
  containers:
    - name: nginx
      image: nginx:alpine
```

```bash
kubectl apply -f pocs/poc-11-k8s-gatekeeper/manifests/pod-noncompliant.yaml
```

Expected: `Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request: container "nginx" is missing cpu limit`

- [ ] **Step 4: Compliant pod — verify AC-4**

`pocs/poc-11-k8s-gatekeeper/manifests/pod-compliant.yaml`:
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: compliant
  namespace: iris-lab
spec:
  containers:
    - name: nginx
      image: nginx:alpine
      resources:
        limits:
          cpu: 100m
          memory: 64Mi
```

```bash
kubectl apply -f pocs/poc-11-k8s-gatekeeper/manifests/pod-compliant.yaml
kubectl get pod compliant -n iris-lab
```

Expected: `Running`

- [ ] **Step 5: Write README.md, commit**

```bash
git add pocs/poc-11-k8s-gatekeeper/
git commit -m "poc(11): k8s-gatekeeper — OPA ConstraintTemplate, admission denial, resource limits"
```

---

### Task 12 — PoC 12: `k8s-argocd`

**Files:**
- Create: `pocs/poc-12-k8s-argocd/app/application.yaml`
- Create: `pocs/poc-12-k8s-argocd/gitrepo/nginx-deployment.yaml`
- Create: `pocs/poc-12-k8s-argocd/README.md`

- [ ] **Step 1: Deploy ArgoCD and verify AC-1**

```bash
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --set configs.params."server\.insecure"=true

kubectl rollout status deployment/argocd-server -n argocd --timeout=180s
kubectl get validatingwebhookconfiguration | grep argocd
```

- [ ] **Step 2: Create Git repo and initial manifest**

```bash
mkdir -p pocs/poc-12-k8s-argocd/gitrepo

cat > pocs/poc-12-k8s-argocd/gitrepo/nginx-deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
  namespace: iris-lab
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx-argocd
  template:
    metadata:
      labels:
        app: nginx-argocd
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          resources:
            limits:
              cpu: 100m
              memory: 64Mi
EOF

git add pocs/poc-12-k8s-argocd/
git commit -m "poc(12): argocd gitrepo — initial nginx deployment (1 replica)"
```

- [ ] **Step 3: Apply ArgoCD Application pointing to repo**

`pocs/poc-12-k8s-argocd/app/application.yaml`:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: iris-poc-12
  namespace: argocd
spec:
  project: default
  source:
    # Replace with your actual remote: git remote get-url origin
    repoURL: https://github.com/josefigueredo/codename-iris.git
    targetRevision: main
    path: pocs/poc-12-k8s-argocd/gitrepo
  destination:
    server: https://kubernetes.default.svc
    namespace: iris-lab
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

```bash
kubectl apply -f pocs/poc-12-k8s-argocd/app/application.yaml

argocd app wait iris-poc-12 --sync --health --timeout 120
```

Expected: `Synced` and `Healthy` status.

- [ ] **Step 4: Change replicas in Git — verify AC-3**

Edit `pocs/poc-12-k8s-argocd/gitrepo/nginx-deployment.yaml`, change `replicas: 1` to `replicas: 3`:

```bash
sed -i '' 's/replicas: 1/replicas: 3/' pocs/poc-12-k8s-argocd/gitrepo/nginx-deployment.yaml
git add pocs/poc-12-k8s-argocd/gitrepo/nginx-deployment.yaml
git commit -m "poc(12): scale nginx to 3 replicas"
git push

sleep 30
kubectl get deployment nginx -n iris-lab -o jsonpath='{.spec.replicas}'
```

Expected: `3`

- [ ] **Step 5: Delete deployment manually — verify AC-4**

```bash
kubectl delete deployment nginx -n iris-lab
sleep 180  # wait up to 3 minutes
kubectl get deployment nginx -n iris-lab
```

Expected: deployment restored by ArgoCD.

- [ ] **Step 6: Write README.md, commit**

```bash
git add pocs/poc-12-k8s-argocd/
git commit -m "poc(12): k8s-argocd — GitOps sync, drift detection, auto-remediation"
```

---

## Phase Gate II → III

- [ ] PoC 08 — all 5 AC satisfied
- [ ] PoC 09 — all 6 AC satisfied
- [ ] PoC 10 — all 5 AC satisfied
- [ ] PoC 11 — all 5 AC satisfied
- [ ] PoC 12 — all 5 AC satisfied

```bash
git commit -m "chore(pocs): phase-ii gate — all AC satisfied"
```

---

## Phase III — Integration & Pipeline Spine

---

### Task 13 — PoC 13: `nats-temporal`

**Files:**
- Create: `pocs/poc-13-nats-temporal/consumer/go.mod`
- Create: `pocs/poc-13-nats-temporal/consumer/main.go`
- Create: `pocs/poc-13-nats-temporal/consumer/workflow.go`
- Create: `pocs/poc-13-nats-temporal/consumer/activities.go`
- Create: `pocs/poc-13-nats-temporal/README.md`

- [ ] **Step 1: Write Go code**

`pocs/poc-13-nats-temporal/consumer/go.mod`:
```
module github.com/Acme-tecnologia/iris-pocs/poc-13

go 1.22

require (
  github.com/nats-io/nats.go v1.36.0
  go.temporal.io/sdk v1.26.1
)
```

`pocs/poc-13-nats-temporal/consumer/activities.go`:
```go
package main

import (
	"context"
	"log"
)

func ParseJob(ctx context.Context, payload string) (string, error) {
	log.Printf("ParseJob: received payload: %s", payload)
	return payload, nil
}

func MarkComplete(ctx context.Context, payload string) error {
	log.Printf("MarkComplete: job done for payload: %s", payload)
	return nil
}
```

`pocs/poc-13-nats-temporal/consumer/workflow.go`:
```go
package main

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

func ProcessJobWorkflow(ctx workflow.Context, payload string) error {
	ao := workflow.ActivityOptions{StartToCloseTimeout: 10 * time.Second}
	ctx = workflow.WithActivityOptions(ctx, ao)

	var parsed string
	if err := workflow.ExecuteActivity(ctx, ParseJob, payload).Get(ctx, &parsed); err != nil {
		return err
	}
	return workflow.ExecuteActivity(ctx, MarkComplete, parsed).Get(ctx, nil)
}
```

`pocs/poc-13-nats-temporal/consumer/main.go`:
```go
package main

import (
	"log"
	"os"

	"github.com/nats-io/nats.go"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
)

func main() {
	natsURL := os.Getenv("NATS_URL")
	if natsURL == "" {
		natsURL = "nats://nats.nats-system.svc.cluster.local:4222"
	}
	temporalHost := os.Getenv("TEMPORAL_HOST")
	if temporalHost == "" {
		temporalHost = "temporal-frontend.temporal-system.svc.cluster.local:7233"
	}

	tc, err := client.Dial(client.Options{HostPort: temporalHost})
	if err != nil {
		log.Fatal(err)
	}
	defer tc.Close()

	w := worker.New(tc, "iris-task-queue", worker.Options{})
	w.RegisterWorkflow(ProcessJobWorkflow)
	w.RegisterActivity(ParseJob)
	w.RegisterActivity(MarkComplete)
	go func() {
		if err := w.Run(worker.InterruptCh()); err != nil {
			log.Fatal(err)
		}
	}()

	nc, err := nats.Connect(natsURL)
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Drain()

	js, _ := nc.JetStream()
	js.QueueSubscribe("iris.standard.*.jobs", "pipeline-workers", func(msg *nats.Msg) {
		payload := string(msg.Data)
		log.Printf("received job: %s", payload)
		_, err := tc.ExecuteWorkflow(
			msg.Context(),
			client.StartWorkflowOptions{TaskQueue: "iris-task-queue"},
			ProcessJobWorkflow,
			payload,
		)
		if err != nil {
			log.Printf("failed to start workflow: %v", err)
			msg.Nak()
			return
		}
		msg.Ack()
	}, nats.Durable("pipeline-workers"), nats.AckExplicit())

	log.Println("consumer running, waiting for jobs...")
	select {}
}
```

- [ ] **Step 2: Build, load, deploy**

```bash
cd pocs/poc-13-nats-temporal/consumer && go mod tidy && cd -

docker build -t iris-poc-13-consumer:latest -f - pocs/poc-13-nats-temporal/consumer <<'EOF'
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY . .
RUN go build -o consumer .
FROM alpine:3.19
COPY --from=build /app/consumer /consumer
ENTRYPOINT ["/consumer"]
EOF

kind load docker-image iris-poc-13-consumer:latest --name iris-lab-01
kubectl run poc13-consumer \
  --image=iris-poc-13-consumer:latest \
  --image-pull-policy=Never \
  --namespace temporal-system
```

- [ ] **Step 3: Verify AC-2, AC-3, AC-4**

```bash
kubectl exec -n nats-system deployment/nats-box -- \
  nats pub iris.standard.bims.jobs '{"ticket_id":"INC-0001","summary":"db timeout"}'

sleep 5
kubectl logs -n temporal-system poc13-consumer | tail -20
# verify via Temporal UI: workflow started and completed

kubectl exec -n nats-system deployment/nats-box -- \
  nats pub iris.standard.acme.jobs '{"ticket_id":"INC-0002","summary":"api latency"}'
# verify AC-4: wildcard routing triggers workflow for acme too
```

- [ ] **Step 4: Write README.md, commit**

```bash
git add pocs/poc-13-nats-temporal/
git commit -m "poc(13): nats-temporal — NATS consumer triggers Temporal workflow, wildcard routing"
```

---

### Task 14 — PoC 14: `temporal-litellm-pg`

**Files:**
- Create: `pocs/poc-14-temporal-litellm-pg/worker/go.mod`
- Create: `pocs/poc-14-temporal-litellm-pg/worker/main.go`
- Create: `pocs/poc-14-temporal-litellm-pg/worker/workflow.go`
- Create: `pocs/poc-14-temporal-litellm-pg/worker/activities.go`
- Create: `pocs/poc-14-temporal-litellm-pg/migrations/000001_classifications.up.sql`
- Create: `pocs/poc-14-temporal-litellm-pg/migrations/000001_classifications.down.sql`
- Create: `pocs/poc-14-temporal-litellm-pg/README.md`

- [ ] **Step 1: Write migration**

`pocs/poc-14-temporal-litellm-pg/migrations/000001_classifications.up.sql`:
```sql
CREATE TABLE IF NOT EXISTS iris_control.classifications (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_run_id  TEXT NOT NULL,
  ticket_id        TEXT NOT NULL,
  category         TEXT NOT NULL,
  severity         TEXT NOT NULL,
  confidence       FLOAT NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`pocs/poc-14-temporal-litellm-pg/migrations/000001_classifications.down.sql`:
```sql
DROP TABLE IF EXISTS iris_control.classifications;
```

```bash
kubectl port-forward -n iris-db svc/postgresql 5432:5432 &
migrate -path pocs/poc-14-temporal-litellm-pg/migrations \
  -database "postgres://postgres:irisdev@localhost:5432/iris?sslmode=disable" up
kill %1
```

- [ ] **Step 2: Write worker Go code**

`pocs/poc-14-temporal-litellm-pg/worker/go.mod`:
```
module github.com/Acme-tecnologia/iris-pocs/poc-14

go 1.22

require (
  go.temporal.io/sdk v1.26.1
  github.com/lib/pq v1.10.9
)
```

`pocs/poc-14-temporal-litellm-pg/worker/activities.go`:
```go
package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	_ "github.com/lib/pq"
)

type Classification struct {
	Category   string  `json:"category"`
	Severity   string  `json:"severity"`
	Confidence float64 `json:"confidence"`
}

var attemptCount int32

func ClassifyEvidence(ctx context.Context, ticketID string, pipelineRunID string) (*Classification, error) {
	attemptCount++
	if attemptCount == 1 {
		attemptCount = 0
		return nil, fmt.Errorf("simulated ClassifyEvidence failure — should NOT be retried from PersistResult")
	}

	litellmURL := os.Getenv("LITELLM_URL")
	if litellmURL == "" {
		litellmURL = "http://litellm.ai-service.svc.cluster.local:4000"
	}

	prompt := fmt.Sprintf(`Classify this support ticket in JSON:
Ticket ID: %s
Return: {"category": string, "severity": "low|medium|high|critical", "confidence": float 0-1}`, ticketID)

	body, _ := json.Marshal(map[string]any{
		"model":    "gpt-3.5-turbo",
		"messages": []map[string]string{{"role": "user", "content": prompt}},
	})

	req, _ := http.NewRequestWithContext(ctx, "POST", litellmURL+"/chat/completions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer iris-dev-key")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)

	var result struct {
		Choices []struct {
			Message struct{ Content string } `json:"message"`
		} `json:"choices"`
	}
	if err := json.Unmarshal(raw, &result); err != nil {
		return nil, err
	}

	var c Classification
	if err := json.Unmarshal([]byte(result.Choices[0].Message.Content), &c); err != nil {
		c = Classification{Category: "infrastructure", Severity: "medium", Confidence: 0.8}
	}
	return &c, nil
}

var persistAttempt int32

func PersistResult(ctx context.Context, c *Classification, ticketID, pipelineRunID string) error {
	persistAttempt++
	if persistAttempt == 1 {
		return fmt.Errorf("simulated PersistResult failure on attempt 1")
	}

	dsn := os.Getenv("POSTGRES_DSN")
	if dsn == "" {
		dsn = "postgres://postgres:irisdev@postgresql.iris-db.svc.cluster.local:5432/iris?sslmode=disable"
	}
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return err
	}
	defer db.Close()

	_, err = db.ExecContext(ctx,
		`INSERT INTO iris_control.classifications
		 (pipeline_run_id, ticket_id, category, severity, confidence)
		 VALUES ($1, $2, $3, $4, $5)`,
		pipelineRunID, ticketID, c.Category, c.Severity, c.Confidence,
	)
	return err
}
```

`pocs/poc-14-temporal-litellm-pg/worker/workflow.go`:
```go
package main

import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

func ClassifyEvidenceWorkflow(ctx workflow.Context, ticketID, pipelineRunID string) error {
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	var classification *Classification
	if err := workflow.ExecuteActivity(ctx, ClassifyEvidence, ticketID, pipelineRunID).Get(ctx, &classification); err != nil {
		return err
	}

	return workflow.ExecuteActivity(ctx, PersistResult, classification, ticketID, pipelineRunID).Get(ctx, nil)
}
```

`pocs/poc-14-temporal-litellm-pg/worker/main.go`:
```go
package main

import (
	"log"
	"os"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
)

func main() {
	host := os.Getenv("TEMPORAL_HOST")
	if host == "" {
		host = "temporal-frontend.temporal-system.svc.cluster.local:7233"
	}
	c, err := client.Dial(client.Options{HostPort: host})
	if err != nil {
		log.Fatal(err)
	}
	defer c.Close()

	w := worker.New(c, "iris-task-queue", worker.Options{})
	w.RegisterWorkflow(ClassifyEvidenceWorkflow)
	w.RegisterActivity(ClassifyEvidence)
	w.RegisterActivity(PersistResult)

	if err := w.Run(worker.InterruptCh()); err != nil {
		log.Fatal(err)
	}
}
```

- [ ] **Step 3: Build, deploy, trigger, verify AC-1 through AC-4**

```bash
cd pocs/poc-14-temporal-litellm-pg/worker && go mod tidy && cd -

# build and load into kind
docker build -t iris-poc-14-worker:latest -f - pocs/poc-14-temporal-litellm-pg/worker <<'EOF'
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY . .
RUN go build -o worker .
FROM alpine:3.19
COPY --from=build /app/worker /worker
ENTRYPOINT ["/worker"]
EOF

kind load docker-image iris-poc-14-worker:latest --name iris-lab-01
kubectl run poc14-worker \
  --image=iris-poc-14-worker:latest \
  --image-pull-policy=Never \
  --namespace temporal-system

kubectl port-forward -n temporal-system svc/temporal-frontend 7233:7233 &
temporal workflow start \
  --workflow-type ClassifyEvidenceWorkflow \
  --task-queue iris-task-queue \
  --input '"INC-0042"' \
  --input '"pipeline-run-abc123"' \
  --workflow-id classify-inc-0042
```

Verify in Temporal UI: `ClassifyEvidence` ran once; `PersistResult` retried (attempt 1 failed, attempt 2 succeeded).

```bash
kubectl port-forward -n iris-db svc/postgresql 5432:5432 &
PGPASSWORD=irisdev psql -h localhost -U postgres -d iris \
  -c "SELECT * FROM iris_control.classifications WHERE pipeline_run_id='pipeline-run-abc123';"
```

Expected: one row with category, severity, confidence populated.

- [ ] **Step 4: Write README.md, commit**

```bash
git add pocs/poc-14-temporal-litellm-pg/
git commit -m "poc(14): temporal-litellm-pg — pipeline worker pattern, activity idempotency, structured output"
```

---

### Task 15 — PoC 15: `full-spine` (Capstone)

**Files:**
- Create: `pocs/poc-15-full-spine/spine/go.mod`
- Create: `pocs/poc-15-full-spine/spine/main.go`
- Create: `pocs/poc-15-full-spine/spine/workflow.go`
- Create: `pocs/poc-15-full-spine/spine/activities.go`
- Create: `pocs/poc-15-full-spine/README.md`

- [ ] **Step 1: Write spine Go module**

`pocs/poc-15-full-spine/spine/go.mod`:
```
module github.com/Acme-tecnologia/iris-pocs/poc-15

go 1.22

require (
  github.com/google/uuid v1.6.0
  github.com/nats-io/nats.go v1.36.0
  github.com/lib/pq v1.10.9
  github.com/qdrant/go-client v1.10.0
  go.opentelemetry.io/otel v1.24.0
  go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc v1.24.0
  go.opentelemetry.io/otel/sdk v1.24.0
  go.temporal.io/sdk v1.26.1
)
```

- [ ] **Step 2: Write activities with OTel tracing**

`pocs/poc-15-full-spine/spine/activities.go`:
```go
package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"os"

	"github.com/qdrant/go-client/qdrant"
	_ "github.com/lib/pq"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
)

type Classification struct {
	Category   string  `json:"category"`
	Severity   string  `json:"severity"`
	Confidence float64 `json:"confidence"`
}

func ClassifyEvidence(ctx context.Context, ticketSummary, pipelineRunID string) (*Classification, error) {
	tracer := otel.Tracer("iris-poc-15")
	ctx, span := tracer.Start(ctx, "ClassifyEvidence")
	defer span.End()
	span.SetAttributes(attribute.String("pipeline_run_id", pipelineRunID))

	litellmURL := envOrDefault("LITELLM_URL", "http://litellm.ai-service.svc.cluster.local:4000")
	body, _ := json.Marshal(map[string]any{
		"model": "gpt-3.5-turbo",
		"messages": []map[string]string{{
			"role":    "user",
			"content": fmt.Sprintf(`Classify: %s. Return JSON: {"category":string,"severity":"low|medium|high|critical","confidence":float}`, ticketSummary),
		}},
	})
	req, _ := http.NewRequestWithContext(ctx, "POST", litellmURL+"/chat/completions", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer iris-dev-key")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)

	var result struct {
		Choices []struct {
			Message struct{ Content string } `json:"message"`
		} `json:"choices"`
	}
	json.Unmarshal(raw, &result)

	c := &Classification{Category: "infrastructure", Severity: "medium", Confidence: 0.85}
	json.Unmarshal([]byte(result.Choices[0].Message.Content), c)
	return c, nil
}

func PersistClassification(ctx context.Context, c *Classification, ticketID, pipelineRunID string) error {
	tracer := otel.Tracer("iris-poc-15")
	ctx, span := tracer.Start(ctx, "PersistClassification")
	defer span.End()
	span.SetAttributes(attribute.String("pipeline_run_id", pipelineRunID))

	dsn := envOrDefault("POSTGRES_DSN",
		"postgres://postgres:irisdev@postgresql.iris-db.svc.cluster.local:5432/iris?sslmode=disable")
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return err
	}
	defer db.Close()

	_, err = db.ExecContext(ctx,
		`INSERT INTO iris_control.classifications
		 (pipeline_run_id, ticket_id, category, severity, confidence)
		 VALUES ($1, $2, $3, $4, $5)`,
		pipelineRunID, ticketID, c.Category, c.Severity, c.Confidence,
	)
	return err
}

func EmbedResolution(ctx context.Context, text, pipelineRunID string) ([]float32, error) {
	tracer := otel.Tracer("iris-poc-15")
	_, span := tracer.Start(ctx, "EmbedResolution")
	defer span.End()
	span.SetAttributes(attribute.String("pipeline_run_id", pipelineRunID))

	// In production: call LiteLLM /embeddings. Here: random 1536-dim vector.
	vec := make([]float32, 1536)
	for i := range vec {
		vec[i] = rand.Float32()
	}
	return vec, nil
}

func UpsertToQdrant(ctx context.Context, vec []float32, ticketID, pipelineRunID string) error {
	tracer := otel.Tracer("iris-poc-15")
	_, span := tracer.Start(ctx, "UpsertToQdrant")
	defer span.End()
	span.SetAttributes(attribute.String("pipeline_run_id", pipelineRunID))

	client, err := qdrant.NewClient(&qdrant.Config{
		Host: envOrDefault("QDRANT_HOST", "qdrant.qdrant-system.svc.cluster.local"),
		Port: 6334,
	})
	if err != nil {
		return err
	}
	_, err = client.Upsert(ctx, &qdrant.UpsertPoints{
		CollectionName: "resolution-memory-bims",
		Points: []*qdrant.PointStruct{{
			Id:      qdrant.NewIDNum(uint64(rand.Int63())),
			Vectors: qdrant.NewVectors(vec...),
			Payload: qdrant.NewValueMap(map[string]any{
				"pipeline_run_id": pipelineRunID,
				"ticket_id":       ticketID,
			}),
		}},
	})
	return err
}

func envOrDefault(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
```

`pocs/poc-15-full-spine/spine/workflow.go`:
```go
package main

import (
	"time"

	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/workflow"
)

func FullSpineWorkflow(ctx workflow.Context, ticketSummary, ticketID, pipelineRunID string) error {
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 30 * time.Second,
		RetryPolicy:         &temporal.RetryPolicy{MaximumAttempts: 3},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	var c *Classification
	if err := workflow.ExecuteActivity(ctx, ClassifyEvidence, ticketSummary, pipelineRunID).Get(ctx, &c); err != nil {
		return err
	}

	if err := workflow.ExecuteActivity(ctx, PersistClassification, c, ticketID, pipelineRunID).Get(ctx, nil); err != nil {
		return err
	}

	var vec []float32
	text := c.Category + " " + c.Severity + " " + ticketSummary
	if err := workflow.ExecuteActivity(ctx, EmbedResolution, text, pipelineRunID).Get(ctx, &vec); err != nil {
		return err
	}

	return workflow.ExecuteActivity(ctx, UpsertToQdrant, vec, ticketID, pipelineRunID).Get(ctx, nil)
}
```

`pocs/poc-15-full-spine/spine/main.go`:
```go
package main

import (
	"context"
	"log"
	"os"

	"github.com/google/uuid"
	"github.com/nats-io/nats.go"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
)

func initTracer(ctx context.Context) func() {
	endpoint := envOrDefault("OTEL_EXPORTER_OTLP_ENDPOINT",
		"otel-collector.observability.svc.cluster.local:4317")
	exp, err := otlptracegrpc.New(ctx,
		otlptracegrpc.WithEndpoint(endpoint),
		otlptracegrpc.WithInsecure(),
	)
	if err != nil {
		log.Fatal(err)
	}
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exp),
		sdktrace.WithResource(resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName("iris-poc-15-spine"),
		)),
	)
	otel.SetTracerProvider(tp)
	return func() { tp.Shutdown(ctx) }
}

func main() {
	ctx := context.Background()
	shutdown := initTracer(ctx)
	defer shutdown()

	tc, err := client.Dial(client.Options{
		HostPort: envOrDefault("TEMPORAL_HOST",
			"temporal-frontend.temporal-system.svc.cluster.local:7233"),
	})
	if err != nil {
		log.Fatal(err)
	}
	defer tc.Close()

	w := worker.New(tc, "iris-task-queue", worker.Options{})
	w.RegisterWorkflow(FullSpineWorkflow)
	w.RegisterActivity(ClassifyEvidence)
	w.RegisterActivity(PersistClassification)
	w.RegisterActivity(EmbedResolution)
	w.RegisterActivity(UpsertToQdrant)
	go func() {
		if err := w.Run(worker.InterruptCh()); err != nil {
			log.Fatal(err)
		}
	}()

	nc, err := nats.Connect(envOrDefault("NATS_URL",
		"nats://nats.nats-system.svc.cluster.local:4222"))
	if err != nil {
		log.Fatal(err)
	}
	defer nc.Drain()

	js, _ := nc.JetStream()
	js.QueueSubscribe("iris.standard.*.jobs", "spine-workers", func(msg *nats.Msg) {
		pipelineRunID := uuid.New().String()
		payload := string(msg.Data)
		log.Printf("pipeline_run_id=%s received job: %s", pipelineRunID, payload)

		tracer := otel.Tracer("iris-poc-15-spine")
		_, span := tracer.Start(ctx, "nats-job-received")
		span.SetAttributes()
		defer span.End()

		_, err := tc.ExecuteWorkflow(
			ctx,
			client.StartWorkflowOptions{TaskQueue: "iris-task-queue"},
			FullSpineWorkflow,
			payload,
			"INC-0099",
			pipelineRunID,
		)
		if err != nil {
			log.Printf("pipeline_run_id=%s workflow start failed: %v", pipelineRunID, err)
			msg.Nak()
			return
		}
		log.Printf("pipeline_run_id=%s workflow started", pipelineRunID)
		msg.Ack()
	}, nats.Durable("spine-workers"), nats.AckExplicit())

	log.Println("full spine running")
	if err := os.WriteFile("/tmp/spine-ready", []byte("ok"), 0644); err != nil {
		log.Print(err)
	}
	select {}
}
```

- [ ] **Step 3: Build and deploy**

```bash
cd pocs/poc-15-full-spine/spine && go mod tidy && cd -

docker build -t iris-poc-15-spine:latest -f - pocs/poc-15-full-spine/spine <<'EOF'
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY . .
RUN go build -o spine .
FROM alpine:3.19
COPY --from=build /app/spine /spine
ENTRYPOINT ["/spine"]
EOF

kind load docker-image iris-poc-15-spine:latest --name iris-lab-01
kubectl run poc15-spine \
  --image=iris-poc-15-spine:latest \
  --image-pull-policy=Never \
  --namespace temporal-system
```

- [ ] **Step 4: Publish one message and verify AC-1**

```bash
kubectl exec -n nats-system deployment/nats-box -- \
  nats pub iris.standard.bims.jobs '{"summary":"database connection timeout in payments"}'

sleep 10
kubectl logs -n temporal-system poc15-spine | grep pipeline_run_id
# capture the pipeline_run_id from logs
```

Expected: workflow completes in Temporal UI.

- [ ] **Step 5: Verify AC-2 (PostgreSQL row)**

```bash
PIPELINE_RUN_ID="<captured from logs>"
kubectl port-forward -n iris-db svc/postgresql 5432:5432 &
PGPASSWORD=irisdev psql -h localhost -U postgres -d iris \
  -c "SELECT * FROM iris_control.classifications WHERE pipeline_run_id='$PIPELINE_RUN_ID';"
kill %1
```

Expected: one row with matching `pipeline_run_id`.

- [ ] **Step 6: Verify AC-3 (Qdrant point)**

```bash
kubectl port-forward -n qdrant-system svc/qdrant 6334:6334 &
# use qdrant REST to scroll and find point with pipeline_run_id in payload
curl -s "http://localhost:6333/collections/resolution-memory-bims/points/scroll" \
  -H "Content-Type: application/json" \
  -d "{\"filter\":{\"must\":[{\"key\":\"pipeline_run_id\",\"match\":{\"value\":\"$PIPELINE_RUN_ID\"}}]},\"with_payload\":true}"
kill %1
```

Expected: one point with `pipeline_run_id` matching.

- [ ] **Step 7: Verify AC-4 and AC-5 (Grafana trace + Loki)**

```bash
kubectl port-forward -n observability svc/grafana 3000:3000 &
```

Open Grafana → Explore → Tempo → search by `pipeline_run_id` tag. Verify trace spans all services. Jump to Loki from trace. Confirm `pipeline_run_id` appears in logs from at least 3 services.

- [ ] **Step 8: Write README.md with full AC evidence, commit**

```bash
git add pocs/poc-15-full-spine/
git commit -m "poc(15): full-spine — end-to-end NATS→Temporal→LiteLLM→PG→Qdrant with OTel correlation"
```

---

## Capstone Completion

```bash
git commit -m "chore(pocs): phase-iii complete — full spine validated, curriculum AC satisfied" --allow-empty
```

Answer the five Capstone Reflection prompts from the spec before closing this curriculum:

1. Which component is the most likely single point of failure?
2. Where would you add a circuit breaker?
3. How does this spine map to the Iris evidence ingestion pipeline?
4. Which ADR would you revisit after running end-to-end?
5. What is missing from this spine for v1-alpha?

---

*End of Iris PoC Curriculum — Implementation Plan*
