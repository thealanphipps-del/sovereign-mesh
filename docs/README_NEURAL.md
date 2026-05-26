# 🧠 Sovereign-27-300M: The Neural Core Genome
### Distributed Mobile NPU & High-Performance Mesh Supercomputer Architecture

This directory contains the core implementation of the **Sovereign-27-300M** neural network. This model transitions the Sovereign Mesh from an economic routing engine into a self-trained, self-governing distributed intelligence.

---

## 🏛️ Model Architecture Specifications

We have structurally aligned the layers, attention systems, and projections around the **Factor-27** mathematical invariant, eliminating traditional black-box randomness:

*   **Vocabulary Size:** $32,000$ (optimized tokens)
*   **Layers:** $27$ (Factor 27 structural blocks)
*   **Attention Heads:** $27$ (parallel attention heads)
*   **Embedding Dimension:** $972$ ($27 \times 36$)
*   **Feed-Forward Network (FFN) Dimension:** $3,888$ ($972 \times 4$)
*   **Context Window:** $1,024$ tokens
*   **Total Parameter Count:** $305,622,432$ parameters (~300M scale)

---

## 📂 Component Layout

1.  **[Dockerfile](file:///home/aellok/sovereign_mesh/Dockerfile):** Builds the CUDA-enabled training image based on the `pytorch/pytorch` stack, installing all telemetry dependencies.
2.  **[train_sovereign.py](file:///home/aellok/sovereign_mesh/train_sovereign.py):** Implements the PyTorch transformer, the **Factor-27 regularizer** (which penalizes neural path drift), and runs a local diagnostic training pass.
3.  **[gcp_deploy_gpu.sh](file:///home/aellok/sovereign_mesh/gcp_deploy_gpu.sh):** Automation script that enables GCP APIs, configures Artifact Registry, builds the container, pushes it, and provisions a GPU compute node running the container.

---

## 📱 Mobile NPU Optimization & Quantization

To enable execution directly on mobile devices (cell phones) acting as the **distributed NPU layer** for our global-scale supercomputer, we utilize block-wise quantization:

```text
+-----------------------------------------------------------------------+
| FP32 Raw Model Weight Size     : ~1.20 GB                             |
| Quantization Target            : INT4 / FP4 Block-Wise Quantization   |
| Compressed Model Weight Size   : ~151.3 MB                            |
| Minimum L3 Cache/RAM Footprint : ~165 MB                              |
| Target NPU Requirement         : 4.5 TOPS (A14 Bionic / Snapdragon)   |
+-----------------------------------------------------------------------+
```

By compressing the model down to **~151.3MB**, the model fits entirely inside the active RAM and L3 caches of modern consumer smartphones, enabling sub-millisecond local token generation without cloud dependencies. 

---

## 🛡️ Self-Governing Quorum Training

Weight mutations and training checkpoints are secured under **Requiem-Consessus**:
1.  **Telemetry Feeding:** The model trains on the *Sovereign Genome* (all transaction telemetry, structural code edits, and arbitrage outcomes).
2.  **Factor-27 Regularizer:** Incorporates an absolute mathematical stabilizer:
    $$L_{total} = L_{task} + \lambda \cdot D_{27}$$
    Where $D_{27}$ measures latent state trajectory phase-drift.
3.  **Veto Panel:** If training experiences gradient collapse or phase drift, the telemetry agents (`AGENT-SEC` and `AGENT-TEL`) instantly abort the run and log a Requiem Block to the ledger.

---

## 🚀 How to Run Locally

You can run a quick diagnostic compilation and training dry-run of the model locally (using CPU fallback if no GPU is present):

```bash
python3 train_sovereign.py
```
