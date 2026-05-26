# ==============================================================================
# SOVEREIGN-27 NEURAL CORE: GPU-ENABLED TRAINING CONTAINER
# Optimized for GCP T4/L4/A100 compute nodes and 300M parameter model training
# ==============================================================================

FROM pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime

LABEL maintainer="Alan Phipps <thealanphipps@gmail.com>"
LABEL version="3.0.0"
LABEL description="Sovereign-27-300M GPU training container with Factor-27 loss regularization"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Set execution workspace
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python packages required for optimization and logging
RUN pip install --no-cache-dir \
    transformers==4.38.1 \
    accelerate==0.27.2 \
    tensorboard==2.16.2 \
    protobuf==4.25.3 \
    grpcio==1.62.0 \
    scipy==1.12.0

# Copy the neural training model and utility files
COPY train_sovereign.py /workspace/train_sovereign.py

# Expose ports for real-time telemetry streaming (TensorBoard & gRPC status)
EXPOSE 6006 1111

# Define runtime entrypoint
ENTRYPOINT ["python", "train_sovereign.py"]
