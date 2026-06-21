#!/bin/bash
# =============================================================================
# Cloud Run 部署腳本（fifa World Cup agent）
# =============================================================================
#
# 用途：
#   建置映像並部署到 Cloud Run。本專案使用 SQLite（無外部 DB），
#   因此不需要 VPC Connector / 固定出口 IP。
#
# 執行方式：
#   ./gcp_Dev.sh
#
# 部署前檢查清單：
# - [ ] 已切換正確 GCP 專案 (project_id)
# - [ ] image_name 指向正確的 Artifact Registry repo 與 tag
# - [ ] Secrets（OPENAI_API_KEY / APIFOOTBALL_KEY / TAVILY_KEY / WC_API_KEYS）已建立於 Secret Manager
# - [ ] --port 與 Dockerfile / uvicorn 綁定的 PORT 一致
# =============================================================================

# set -x
project_id=""
region="asia-east1"
image_name=""
dockerfile_name="Dockerfile"
service_name=""
service_account=""


# Step 1: Set GCP Project
echo "[Step-1] Setting GCP project to '$project_id'..."
gcloud config set project "$project_id"
if [ $? -ne 0 ]; then
  echo "[Step-1] Failed to set GCP project. Exiting script." >&2
  exit 1
else
  echo "[Step-1] Successfully set GCP project to '$project_id'."
fi

# Step 2: Authenticate Docker with GCP Artifact Registry
echo "[Step-2] Authenticating Docker with GCP Artifact Registry in region '$region'..."
gcloud auth configure-docker "$region-docker.pkg.dev"
if [ $? -ne 0 ]; then
  echo "[Step-2] Docker authentication with GCP Artifact Registry failed. Exiting script." >&2
  exit 1
else
  echo "[Step-2] Successfully authenticated Docker with GCP Artifact Registry."
fi

# Step 3: Build the Docker image
echo "[Step-3] Building Docker image '$image_name' using Dockerfile '$dockerfile_name'..."
docker buildx build \
  --platform=linux/amd64 \
  --tag "$image_name" \
  -f "$dockerfile_name" \
  .
if [ $? -ne 0 ]; then
  echo "[Step-3] Docker image build failed. Exiting script." >&2
  exit 1
else
  echo "[Step-3] Successfully built Docker image '$image_name'."
fi

# Step 4: Push the Docker image to Artifact Registry
echo "[Step-4] Pushing Docker image '$image_name' to Artifact Registry..."
docker push "$image_name"
if [ $? -ne 0 ]; then
  echo "[Step-4] Failed to push Docker image to Artifact Registry. Exiting script." >&2
  exit 1
else
  echo "[Step-4] Successfully pushed Docker image '$image_name' to Artifact Registry."
fi

# Step 5: Deploy the Docker image to Cloud Run
echo "[Step-5] Deploying Docker image '$image_name' to Cloud Run service '$service_name'..."
# IMPORTANT: --max-instances 1 is required for quota correctness.
# This service uses SQLite as its sole daily-quota store (100 req/day for API-Football).
# Scaling out to multiple instances would cause each instance to maintain its own counter,
# leading to quota overruns. Any scale-out would require an external quota store (e.g. Redis/Firestore).
# --allow-unauthenticated: Cloud Run auth is disabled intentionally; the app enforces auth
# via its own X-API-Key middleware layer.
gcloud run deploy "$service_name" \
  --image "$image_name" \
  --platform "managed" \
  --region "$region" \
  --port 8887 \
  --cpu 1 \
  --memory "1Gi" \
  --min-instances 0 \
  --max-instances 1 \
  --timeout "180s" \
  --concurrency 50 \
  --update-secrets=OPENAI_API_KEY=OPENAI_API_KEY:latest,APIFOOTBALL_KEY=APIFOOTBALL_KEY:latest,TAVILY_KEY=TAVILY_KEY:latest,WC_API_KEYS=WC_API_KEYS:latest \
  --set-env-vars="OPENAI_DEFAULT_MODEL=gpt-4o-mini,WC_SEASON=2022,STORAGE_BACKEND=sqlite" \
  --allow-unauthenticated
if [ $? -ne 0 ]; then
  echo "[Step-5] Cloud Run deployment failed. Exiting script." >&2
  exit 1
else
  echo "[Step-5] Successfully deployed Docker image to Cloud Run service '$service_name'."
fi
