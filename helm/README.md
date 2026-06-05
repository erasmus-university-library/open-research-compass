# Helm Chart — duck-agent

Deploys the full Open Research Compass stack to a Kubernetes cluster (tested on AKS).

## Prerequisites

| Tool | Version |
|---|---|
| [Helm](https://helm.sh/docs/intro/install/) | 3.x |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | 1.28+ |
| A running Kubernetes cluster with the Azure Files CSI driver enabled (included by default on AKS 1.21+) |

## Quick start (automated)

The `deploy-aks.sh` script at the repo root provisions all Azure infrastructure and installs the chart in one step:

```bash
# From the repo root
./deploy-aks.sh
```

It reads `AZURE_AI_API_KEY` and `AZURE_AI_API_BASE` from `.env` or prompts for them interactively. See [deploy-aks.sh](#deploy-akssh) below for what it does.

## Manual install

If your cluster and Azure storage already exist, install directly with Helm:

```bash
helm upgrade --install duck-agent ./helm/duck-agent \
  --namespace duck-agent \
  --create-namespace \
  --set image.registry=<acr-name>.azurecr.io \
  --set azureAiApiKey=<your-azure-ai-api-key> \
  --set azureAiApiBase=<your-azure-ai-endpoint> \
  --set azModel=azure_ai/Mistral-Large-3 \
  --set storage.accountName=<storage-account-name> \
  --set storage.accountKey=<storage-account-key> \
  --wait \
  --timeout 10m
```

`--wait` blocks until all pods pass their readiness probes. The embeddings service loads a ~570 MB model on startup, so allow up to 10 minutes on first deploy.

## Configuration reference

All values live in [duck-agent/values.yaml](duck-agent/values.yaml). The four values below have no defaults and **must** be supplied at install time — never commit them.

| Value | Required | Description |
|---|---|---|
| `image.registry` | Yes | Container registry hostname, e.g. `duckagentacr.azurecr.io` |
| `azureAiApiKey` | Yes | Azure AI API key |
| `azureAiApiBase` | Yes | Azure AI endpoint URL, e.g. `https://your-endpoint.services.ai.azure.com/models` |
| `azModel` | Yes | Model identifier, e.g. `azure_ai/Mistral-Large-3` |
| `storage.accountName` | Yes | Azure Storage account name |
| `storage.accountKey` | Yes | Azure Storage account key (used to mount Azure Files shares) |

The remaining values have sensible defaults but can be overridden:

### Images

| Value | Default | Description |
|---|---|---|
| `image.pullPolicy` | `IfNotPresent` | Kubernetes image pull policy |
| `image.pullSecret` | `""` | Name of an existing `imagePullSecret` to attach to all pods. Leave empty when using AKS managed identity with `--attach-acr` (the default in `deploy-aks.sh`). Set this when deploying to a non-AKS cluster or when the managed identity attachment is not configured. |
| `embeddings.image.repository` | `embeddings` | Image name (appended to `image.registry`) |
| `embeddings.image.tag` | `latest` | Image tag |
| `mcp.image.repository` | `mcp` | |
| `mcp.image.tag` | `latest` | |
| `agent.image.repository` | `agent` | |
| `agent.image.tag` | `latest` | |
| `frontend.image.repository` | `frontend` | |
| `frontend.image.tag` | `latest` | |

### Replicas and resources

| Value | Default | Description |
|---|---|---|
| `embeddings.replicas` | `1` | Keep at 1 — the model is loaded into memory per replica |
| `embeddings.resources.requests.cpu` | `2` | |
| `embeddings.resources.requests.memory` | `4Gi` | |
| `mcp.replicas` | `1` | DuckDB is a single-file database; scale only if using read-only queries |
| `mcp.resources.requests.cpu` | `1` | |
| `mcp.resources.requests.memory` | `2Gi` | |
| `agent.replicas` | `1` | Stateless — safe to scale horizontally |
| `agent.resources.requests.cpu` | `1` | |
| `agent.resources.requests.memory` | `2Gi` | |
| `frontend.replicas` | `1` | Stateless — safe to scale horizontally |
| `frontend.resources.requests.cpu` | `500m` | |
| `frontend.resources.requests.memory` | `1Gi` | |

### Storage

The chart uses static Azure Files PersistentVolumes. Both shares must exist in the storage account before installing.

| Value | Default | Description |
|---|---|---|
| `storage.duckdb.shareName` | `duckdb-data` | Azure Files share containing `academic.duckdb` |
| `storage.duckdb.size` | `5Gi` | PVC size request |
| `storage.modelCache.shareName` | `model-cache` | Azure Files share for the BAAI/bge-m3 model cache |
| `storage.modelCache.size` | `10Gi` | PVC size request |

### Readiness probe tuning

The embeddings service takes ~2 minutes to load its model. If pods are being killed before they finish starting (e.g. on slow nodes or a cold model cache), increase the initial delay:

```bash
--set embeddings.readinessProbe.initialDelaySeconds=180
```

| Value | Default |
|---|---|
| `embeddings.readinessProbe.initialDelaySeconds` | `120` |
| `embeddings.readinessProbe.periodSeconds` | `15` |
| `embeddings.readinessProbe.failureThreshold` | `10` |

### Frontend service type

By default the frontend is exposed via a `LoadBalancer` service (Azure assigns a public IP). To use an existing Ingress controller instead, set:

```bash
--set frontend.service.type=ClusterIP
```

Then add your own Ingress resource pointing to the `frontend` service on port `3000`.

## Updating after a code change

Rebuild and push the changed image, then upgrade the release. Use a versioned tag rather than `latest` in production to make rollbacks reliable.

```bash
# Example: update the agent service
docker build --file Dockerfile.agent --tag <acr>.azurecr.io/agent:v1.1 .
docker push <acr>.azurecr.io/agent:v1.1

helm upgrade duck-agent ./helm/duck-agent \
  --namespace duck-agent \
  --reuse-values \
  --set agent.image.tag=v1.1
```

`--reuse-values` carries forward all previously supplied `--set` values (registry, keys, etc.) so you only need to specify what changed.

## Rollback

```bash
helm history duck-agent -n duck-agent          # list revisions
helm rollback duck-agent <revision> -n duck-agent
```

## Uninstall

```bash
helm uninstall duck-agent -n duck-agent
```

This removes all Kubernetes resources managed by the chart. The PersistentVolumes use `reclaimPolicy: Retain`, so the underlying Azure Files data (DuckDB file and model cache) is **not** deleted. To also delete the Azure infrastructure:

```bash
az group delete --name duck-agent-rg --yes
```

## Startup order

Services start in dependency order enforced by init containers:

```
embeddings (ready)
  └─► mcp (ready)
        └─► agent (ready)
              └─► frontend
```

Each service's init container polls its upstream over the cluster-internal DNS name before the main container starts. This mirrors the Docker Compose `depends_on` / healthcheck behaviour.

## Secrets

Two Kubernetes Secrets are created by the chart:

| Secret | Key | Source |
|---|---|---|
| `azure-ai-secret` | `api_key`, `api_base` | `--set azureAiApiKey=...`, `--set azureAiApiBase=...` |
| `azure-files-secret` | `azurestorageaccountname`, `azurestorageaccountkey` | `--set storage.accountName/Key=...` |

These values are base64-encoded by Helm at install time and never written to `values.yaml`.

## deploy-aks.sh

The deploy script performs these steps in order:

1. Creates the resource group, ACR, and pushes all four images
2. Creates an AKS cluster (`Standard_D4s_v3` × 2 nodes) with `--attach-acr` so pods can pull images without image pull secrets
3. Creates an Azure Storage account with two file shares and uploads `academic.duckdb`
4. Runs `helm upgrade --install` with the required `--set` values

Edit the variables at the top of the script to change resource names or location before running.
