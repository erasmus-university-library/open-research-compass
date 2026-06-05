#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — edit these before running
# ---------------------------------------------------------------------------
RESOURCE_GROUP="duck-agent-rg"
LOCATION="westeurope"
ACR_NAME="duckagentacr"          # globally unique, lowercase, 5-50 chars
AKS_NAME="duck-agent-aks"
STORAGE_ACCOUNT="duckagentsa"    # globally unique, lowercase, 3-24 chars
FILE_SHARE_DUCKDB="duckdb-data"
FILE_SHARE_MODELS="model-cache"
DUCKDB_FILE="./academic.duckdb"
HELM_RELEASE="duck-agent"
HELM_NAMESPACE="duck-agent"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo -e "\n\033[1;34m==> $*\033[0m"; }
require() { command -v "$1" &>/dev/null || { echo "Required tool not found: $1"; exit 1; }; }

require az
require docker
require helm
require kubectl

# ---------------------------------------------------------------------------
# 0. Secrets
# ---------------------------------------------------------------------------
if [[ -f .env ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs)
fi

if [[ -z "${AZURE_AI_API_KEY:-}" ]]; then
  read -rsp "Enter AZURE_AI_API_KEY: " AZURE_AI_API_KEY
  echo
fi

if [[ -z "${AZURE_AI_API_BASE:-}" ]]; then
  read -rsp "Enter AZURE_AI_API_BASE: " AZURE_AI_API_BASE
  echo
fi

# ---------------------------------------------------------------------------
# 1. Resource group
# ---------------------------------------------------------------------------
log "Creating resource group: $RESOURCE_GROUP"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none

# ---------------------------------------------------------------------------
# 2. Azure Container Registry — build and push all images
# ---------------------------------------------------------------------------
log "Creating container registry: $ACR_NAME"
az acr create \
  --name "$ACR_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --sku Basic \
  --admin-enabled true \
  --output none

ACR_SERVER="${ACR_NAME}.azurecr.io"
ACR_PASSWORD=$(az acr credential show \
  --name "$ACR_NAME" \
  --query "passwords[0].value" \
  --output tsv)

log "Logging into ACR"
docker login "$ACR_SERVER" \
  --username "$ACR_NAME" \
  --password "$ACR_PASSWORD"

log "Building and pushing images"
docker build --file services/embeddings/Dockerfile --tag "${ACR_SERVER}/embeddings:latest" .
docker push "${ACR_SERVER}/embeddings:latest"

docker build --file services/mcp/Dockerfile --tag "${ACR_SERVER}/mcp:latest" .
docker push "${ACR_SERVER}/mcp:latest"

docker build --file services/agent/Dockerfile --tag "${ACR_SERVER}/agent:latest" .
docker push "${ACR_SERVER}/agent:latest"

docker build --file ui/Dockerfile --tag "${ACR_SERVER}/frontend:latest" ui/
docker push "${ACR_SERVER}/frontend:latest"

# ---------------------------------------------------------------------------
# 3. AKS cluster — attach ACR so pods can pull images without image pull secrets
# ---------------------------------------------------------------------------
log "Creating AKS cluster: $AKS_NAME (this takes ~5 minutes)"
az aks create \
  --name "$AKS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --node-count 2 \
  --node-vm-size Standard_D4s_v3 \
  --attach-acr "$ACR_NAME" \
  --generate-ssh-keys \
  --output none

log "Fetching kubeconfig"
az aks get-credentials \
  --name "$AKS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --overwrite-existing

# ---------------------------------------------------------------------------
# 4. Azure Files storage — replaces Docker volumes
# ---------------------------------------------------------------------------
log "Creating storage account: $STORAGE_ACCOUNT"
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --output none

STORAGE_KEY=$(az storage account keys list \
  --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[0].value" \
  --output tsv)

log "Creating file shares"
az storage share create \
  --name "$FILE_SHARE_DUCKDB" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --output none

az storage share create \
  --name "$FILE_SHARE_MODELS" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --output none

log "Uploading academic.duckdb"
az storage file upload \
  --share-name "$FILE_SHARE_DUCKDB" \
  --source "$DUCKDB_FILE" \
  --account-name "$STORAGE_ACCOUNT" \
  --account-key "$STORAGE_KEY" \
  --output none

# ---------------------------------------------------------------------------
# 5. Helm install
# ---------------------------------------------------------------------------
log "Installing Helm chart"
helm upgrade --install "$HELM_RELEASE" ./deploy/helm/duck-agent \
  --namespace "$HELM_NAMESPACE" \
  --create-namespace \
  --set image.registry="$ACR_SERVER" \
  --set azureAiApiKey="$AZURE_AI_API_KEY" \
  --set azureAiApiBase="$AZURE_AI_API_BASE" \
  --set storage.accountName="$STORAGE_ACCOUNT" \
  --set storage.accountKey="$STORAGE_KEY" \
  --wait \
  --timeout 10m

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "Waiting for frontend LoadBalancer IP..."
kubectl get service frontend \
  --namespace "$HELM_NAMESPACE" \
  --watch=false \
  --output jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true

FRONTEND_IP=$(kubectl get service frontend \
  --namespace "$HELM_NAMESPACE" \
  --output jsonpath='{.status.loadBalancer.ingress[0].ip}')

echo ""
echo "  App URL: http://${FRONTEND_IP}/app/default"
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n $HELM_NAMESPACE           # check pod status"
echo "  kubectl logs -n $HELM_NAMESPACE deploy/embeddings  # service logs"
echo "  helm upgrade duck-agent ./deploy/helm/duck-agent ... # redeploy after changes"
echo "  helm uninstall duck-agent -n $HELM_NAMESPACE        # tear down"
echo "  ./deploy/update-aks.sh SERVICE                      # build, push, and deploy service with next tag"
