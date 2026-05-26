#!/bin/bash
# ==============================================================================
# SOVEREIGN-27: EPHEMERAL GOOGLE CLOUD RUN GPU DEPLOYMENT SCRIPT
# Deploys as a serverless container that scales to zero (dies) when idle.
# ==============================================================================
set -e

# --- CONFIG ---
PROJECT_ID="model-loader-495607-m2"
REGION="us-central1"
REPOSITORY="sovereign-neural-repo"
IMAGE_NAME="sovereign-27-300m"
TAG="latest"
SERVICE_NAME="sovereign-27-pool"

CYAN="\033[96m"
GREEN="\033[92m"
GOLD="\033[93m"
RESET="\033[0m"
BOLD="\033[1m"

echo -e "${GOLD}============================================================${RESET}"
echo -e "${BOLD}  SOVEREIGN-27: SERVERLESS CLOUD RUN GPU DISPATCHER${RESET}"
echo -e "${GOLD}============================================================${RESET}"
echo -e "${CYAN}GCP Project:${RESET}   ${PROJECT_ID}"
echo -e "${CYAN}Target Region:${RESET} ${REGION}"
echo -e "${CYAN}Service Name:${RESET}  ${SERVICE_NAME}"
echo -e "${CYAN}Parameters:${RESET}    Scale-to-Zero (min-scale: 0) | Nvidia L4 GPU"
echo ""

FULL_IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${TAG}"

# --- STEP 1: Enable Google Cloud Run Beta APIs ---
echo -e "${GOLD}[STEP 1] Verifying Cloud Run and Registry APIs...${RESET}"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com --project="${PROJECT_ID}"
echo -e "${GREEN}[OK] APIs ready.${RESET}"

# --- STEP 2: Tag and Push Container to Registry ---
echo -e "${GOLD}[STEP 2] Pushing latest Sovereign-27 container image to registry...${RESET}"
docker tag "sovereign-27-300m:latest" "${FULL_IMAGE_URI}"
docker push "${FULL_IMAGE_URI}"
echo -e "${GREEN}[OK] Container pushed successfully.${RESET}"

# --- STEP 3: Deploy to Google Cloud Run with GPU (Scale-to-Zero) ---
echo -e "${GOLD}[STEP 3] Deploying serverless Cloud Run GPU service...${RESET}"
gcloud beta run deploy "${SERVICE_NAME}" \
    --image="${FULL_IMAGE_URI}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --cpu=4 \
    --memory=16Gi \
    --gpu=1 \
    --gpu-type="nvidia-l4" \
    --min-instances=0 \
    --max-instances=5 \
    --port=3333 \
    --no-allow-unauthenticated \
    --set-env-vars="GEMINI_API_KEY=AIzaSyCqMMdPm1s6MuXy06yiWUlIQ0CJ1C-rPWk,GOTOOLCHAIN=local" \
    --quiet

# --- STEP 4: Retrieve Deploy URL ---
DEPLOY_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")

echo ""
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo -e "${GREEN}${BOLD}  ✅ SERVERLESS CLOUD RUN GPU DEPLOYED SUCCESSFULLY!${RESET}"
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo -e "${CYAN}Service URL:${RESET}   ${DEPLOY_URL}"
echo -e "${CYAN}Registry URI:${RESET}  ${FULL_IMAGE_URI}"
echo -e "${CYAN}Min Scale:${RESET}     0 (scales to zero / dies when idle)"
echo -e "${CYAN}Max Scale:${RESET}     5 instances"
echo -e "${CYAN}GPU Alloc:${RESET}     1x NVIDIA L4 GPU per instance"
echo ""
echo -e "${GOLD}To check live serverless metrics and logs, execute:${RESET}"
echo -e "  gcloud run services describe ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
