#!/bin/bash
# ==============================================================================
# SOVEREIGN MESH - OUT-OF-BAND (OOB) NEURAL CORE IGNITION SCRIPT
# Enforces zero-allocation orchestration and ignites the new Stratum Inference Pool
# ==============================================================================
set -e

BASE_DIR="/home/aellok/sovereign_mesh"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

echo "🌌 [OOB-NEURAL] Initializing Out-of-Band Neural Swarm Environment..."

# 1. Terminate Legacy Services
echo "🛑 [OOB-NEURAL] Cleaning up legacy gRPC and Python stubs..."
pkill -f "grpc_server.py" || true
pkill -f "web_server.py" || true
pkill -f "memory_bus/server.py" || true
pkill -f "mesh_server" || true
sleep 1

# 2. Compile and Verify Go Suite
echo "🛠️ [OOB-NEURAL] Verifying the new zero-allocation Go 1.26 binary suite..."
cd "$BASE_DIR"

# Verify or compile mesh_server if missing
if [ ! -f "./mesh_server" ]; then
    echo "📦 [OOB-NEURAL] Compiling Go mesh_server..."
    /home/aellok/go/bin/go build -o ./mesh_server ./cmd/mesh_server/main.go
fi

# 3. Configure Local Firewall/Network Routing
echo "📡 [OOB-NEURAL] Setting up local port routing for Termux and GCP bridges..."
# Ensure ports 1111 (gRPC), 3333 (Stratum Inference), and 11111 (Memory Bus) are open locally
if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 1111/tcp comment 'Sovereign gRPC Control Bus'
    sudo ufw allow 3333/tcp comment 'Stratum Inference Pool'
    sudo ufw allow 11111/tcp comment 'HighSpeed Memory Bus'
    echo "   [OK] UFW firewall profiles updated."
fi

# 4. Ignite Core Services (gRPC Bus & HighSpeed Memory Bus)
echo "🚀 [OOB-NEURAL] Launching high-performance Go Mesh Server..."
export ANTIGRAVITY_NODE_ID="LOCAL-QUORUM-MASTER"
export GOTOOLCHAIN=local

# Start mesh_server in the background (Handles gRPC on 1111 and ledger on 11111)
nohup ./mesh_server > "$LOG_DIR/mesh_server.log" 2>&1 &
MESH_PID=$!
echo "   [OK] Go Mesh Server ignited under PID: $MESH_PID"

# 5. Start the Stratum Inference Pool Server
# The new Stratum server is built directly into the Go controller interface
echo "🚀 [OOB-NEURAL] Launching Stratum Distributed Inference Pool..."
# We can trigger the Stratum pool directly via sovereign-cli or local runner
nohup ./sovereign-cli --stratum-start --port=3333 > "$LOG_DIR/stratum_pool.log" 2>&1 &
STRATUM_PID=$!
echo "   [OK] Stratum Inference Pool online under PID: $STRATUM_PID"

# 6. Final Telemetry Audit
sleep 3
echo ""
echo "=== ACTIVE SERVICES PORT CHECK ==="
ss -tlnp | grep -E "1111|3333|11111" || echo "⚠️ Warning: Some ports failed to bind!"
echo ""
echo "✅ [OOB-NEURAL] NEW MESH IGNITION SEQUENCE COMPLETED."
echo "👉 Stratum Inference Pool is listening at 127.0.0.1:3333 (Permits Termux connections)"
echo "👉 gRPC Control Plane is active at 127.0.0.1:1111"
echo ""
