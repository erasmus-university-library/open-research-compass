#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — must match deploy-aks.sh
# ---------------------------------------------------------------------------
ACR_NAME="duckagentacr"
AKS_NAME="duck-agent-aks"
RESOURCE_GROUP="duck-agent-rg"
HELM_RELEASE="duck-agent"
HELM_NAMESPACE="duck-agent"

SERVICES=(embeddings mcp agent frontend)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo -e "\n\033[1;34m==> $*\033[0m"; }

usage() {
  cat <<EOF
Usage: ./update.sh <service> [tag]

  <service>   One of: ${SERVICES[*]}
  [tag]       Image tag to deploy (default: auto-increments the current tag)

Examples:
  ./update.sh agent              # build, push, and deploy agent with next tag
  ./update.sh agent v2.0        # build, push, and deploy agent as v2.0
  ./update.sh embeddings v1.3   # update embeddings service
EOF
  exit 1
}

# ---------------------------------------------------------------------------
# Validate args
# ---------------------------------------------------------------------------
[[ $# -lt 1 ]] && usage

SERVICE="$1"
VALID=false
for s in "${SERVICES[@]}"; do [[ "$s" == "$SERVICE" ]] && VALID=true; done
[[ "$VALID" == false ]] && { echo "Unknown service: $SERVICE. Must be one of: ${SERVICES[*]}"; exit 1; }

# ---------------------------------------------------------------------------
# Resolve image tag — auto-increment if not supplied
# ---------------------------------------------------------------------------
ACR_SERVER="${ACR_NAME}.azurecr.io"

if [[ $# -ge 2 ]]; then
  TAG="$2"
else
  log "Resolving current tag for $SERVICE from ACR"
  CURRENT_TAG=$(az acr repository show-tags \
    --name "$ACR_NAME" \
    --repository "$SERVICE" \
    --orderby time_desc \
    --top 1 \
    --output tsv 2>/dev/null || echo "")

  if [[ -z "$CURRENT_TAG" || "$CURRENT_TAG" == "latest" ]]; then
    TAG="v1.1"
  else
    # Increment the patch number: v1.2 → v1.3
    MAJOR=$(echo "$CURRENT_TAG" | cut -d. -f1 | tr -d 'v')
    MINOR=$(echo "$CURRENT_TAG" | cut -d. -f2)
    TAG="v${MAJOR}.$((MINOR + 1))"
  fi
  echo "  Auto-selected tag: $TAG"
fi

# ---------------------------------------------------------------------------
# Resolve Dockerfile and deploy timeout
# ---------------------------------------------------------------------------
case "$SERVICE" in
  embeddings) DOCKERFILE="Dockerfile.embeddings"; BUILD_CONTEXT=".";   TIMEOUT="12m" ;;
  mcp)        DOCKERFILE="Dockerfile.agent";      BUILD_CONTEXT=".";   TIMEOUT="5m"  ;;
  agent)      DOCKERFILE="Dockerfile.agent";      BUILD_CONTEXT=".";   TIMEOUT="5m"  ;;
  frontend)   DOCKERFILE="ui/Dockerfile";         BUILD_CONTEXT="ui/"; TIMEOUT="5m"  ;;
esac

# ---------------------------------------------------------------------------
# Build and push
# ---------------------------------------------------------------------------
IMAGE="${ACR_SERVER}/${SERVICE}:${TAG}"

log "Logging into ACR"
az acr login --name "$ACR_NAME"

log "Building $IMAGE"
docker build --file "$DOCKERFILE" --tag "$IMAGE" "$BUILD_CONTEXT"

log "Pushing $IMAGE"
docker push "$IMAGE"

# ---------------------------------------------------------------------------
# Ensure kubectl is pointed at the right cluster
# ---------------------------------------------------------------------------
log "Fetching kubeconfig for $AKS_NAME"
az aks get-credentials \
  --name "$AKS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --overwrite-existing

# ---------------------------------------------------------------------------
# Helm rolling update
# ---------------------------------------------------------------------------
log "Deploying $SERVICE:$TAG via Helm"

# Load Azure AI credentials from .env if present
AZURE_AI_API_KEY="${AZURE_AI_API_KEY:-}"
AZURE_AI_API_BASE="${AZURE_AI_API_BASE:-}"
AZ_MODEL="${AZ_MODEL:-}"
if [[ -f .env ]]; then
  AZURE_AI_API_KEY=$(grep -E '^AZURE_AI_API_KEY=' .env | cut -d= -f2-)
  AZURE_AI_API_BASE=$(grep -E '^AZURE_AI_API_BASE=' .env | cut -d= -f2-)
  AZ_MODEL=$(grep -E '^AZ_MODEL=' .env | cut -d= -f2-)
fi

helm upgrade "$HELM_RELEASE" ./helm/duck-agent \
  --namespace "$HELM_NAMESPACE" \
  --reuse-values \
  --set "${SERVICE}.image.tag=${TAG}" \
  --set "azureAiApiKey=${AZURE_AI_API_KEY}" \
  --set "azureAiApiBase=${AZURE_AI_API_BASE}" \
  ${AZ_MODEL:+--set "azModel=${AZ_MODEL}"} \
  --wait \
  --timeout "$TIMEOUT"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "Done — $SERVICE updated to $TAG"
echo ""
echo "  kubectl rollout status deploy/$SERVICE -n $HELM_NAMESPACE"
echo "  kubectl logs -n $HELM_NAMESPACE deploy/$SERVICE --tail=50"
echo "  helm rollback $HELM_RELEASE -n $HELM_NAMESPACE   # undo if needed"
