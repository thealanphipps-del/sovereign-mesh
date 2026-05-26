#!/bin/bash
# ==============================================================================
# SOVEREIGN MESH - GCP GPU CONTAINER PROVISIONING & DEPLOYMENT SCRIPT
# Provisions Google Artifact Registry, builds the container, and launches training.
# ==============================================================================
set -e

# --- CONFIG ---
PROJECT_ID="model-loader-495607-m2"
REGION="us-central1"
ZONE="us-central1-c"
REPOSITORY="sovereign-neural-repo"
IMAGE_NAME="sovereign-27-300m"
TAG="latest"
INSTANCE_NAME="sovereign-training-gpu"
GPU_TYPE="nvidia-tesla-t4" # T4/L4 for general, A100 for heavy training
GPU_COUNT=1

CYAN="\033[96m"
GREEN="\033[92m"
GOLD="\033[93m"
RESET="\033[0m"
BOLD="\033[1m"

echo -e "${GOLD}============================================================${RESET}"
echo -e "${BOLD}  SOVEREIGN-27: CONTAINERIZED GPU DEPLOYMENT DISPATCHER${RESET}"
echo -e "${GOLD}============================================================${RESET}"
echo -e "${CYAN}GCP Project:${RESET} ${PROJECT_ID}"
echo -e "${CYAN}Target Region:${RESET} ${REGION} (${ZONE})"
echo -e "${CYAN}GPU Config:${RESET}  ${GPU_COUNT}x ${GPU_TYPE}"
echo ""

# --- STEP 1: Enable Google Cloud Container Services ---
echo -e "${GOLD}[STEP 1] Activating necessary GCP Container APIs...${RESET}"
gcloud services enable artifactregistry.googleapis.com compute.googleapis.com --project="${PROJECT_ID}"
echo -e "${GREEN}[OK] APIs activated.${RESET}"

# --- STEP 2: Configure Docker Auth with GCP ---
echo -e "${GOLD}[STEP 2] Authenticating local Docker to Google Artifact Registry...${RESET}"
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet --project="${PROJECT_ID}"
echo -e "${GREEN}[OK] Authentication completed.${RESET}"

# --- STEP 3: Create Artifact Registry Repository ---
echo -e "${GOLD}[STEP 3] Verifying Artifact Registry Repository...${RESET}"
gcloud artifacts repositories create "${REPOSITORY}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Sovereign Swarm GPU Training Images" \
    --project="${PROJECT_ID}" 2>/dev/null || echo -e "${CYAN}[INFO] Repository already exists.${RESET}"
echo -e "${GREEN}[OK] Repository ready.${RESET}"

# --- STEP 4: Build Docker Image Locally ---
FULL_IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${TAG}"
echo -e "${GOLD}[STEP 4] Building Sovereign-27 GPU container...${RESET}"
echo -e "${CYAN}URI:${RESET} ${FULL_IMAGE_URI}"
docker build -t "${IMAGE_NAME}:${TAG}" -t "${FULL_IMAGE_URI}" .
echo -e "${GREEN}[OK] Container built successfully.${RESET}"

# --- STEP 5: Push Container to GCP ---
echo -e "${GOLD}[STEP 5] Pushing container to Google Artifact Registry...${RESET}"
docker push "${FULL_IMAGE_URI}"
echo -e "${GREEN}[OK] Container pushed to GCR.${RESET}"

# --- STEP 6: Spin Up GPU Compute Instance with Container OS ---
echo -e "${GOLD}[STEP 6] Provisioning GPU compute VM and attaching container...${RESET}"
gcloud compute instances create-with-container "${INSTANCE_NAME}" \
    --project="${PROJECT_ID}" \
    --zone="${ZONE}" \
    --machine-type="n1-standard-4" \
    --accelerator="type=${GPU_TYPE},count=${GPU_COUNT}" \
    --container-image="${FULL_IMAGE_URI}" \
    --container-restart-policy="never" \
    --metadata="install-nvidia-driver=True" \
    --boot-disk-size="50GB" \
    --boot-disk-type="pd-ssd" \
    --tags=sovereign-mesh-node \
    --maintenance-policy="TERMINATE"

echo -e "${GREEN}[OK] GPU Compute Instance online running training container!${RESET}"

# --- STEP 7: Stream Telemetry Verification ---
echo ""
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo -e "${GREEN}${BOLD}  🚀 DEPLOYMENT DISPATCH COMPLETE: SOVEREIGN-27 ONLINE${RESET}"
echo -e "${GREEN}${BOLD}============================================================${RESET}"
echo -e "${CYAN}VM Instance:${RESET}      ${INSTANCE_NAME}"
echo -e "${CYAN}Image URI:${RESET}        ${FULL_IMAGE_URI}"
echo -e "${CYAN}GPU Accelerator:${RESET}  ${GPU_COUNT}x ${GPU_TYPE}"
echo ""
echo -e "${GOLD}To check training logs in real-time, execute:${RESET}"
echo -e "  gcloud compute instances get-serial-port-output ${INSTANCE_NAME} --zone=${ZONE} --project=${PROJECT_ID}"
echo ""
