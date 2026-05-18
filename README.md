# 🌀 JetWeb Time Machine & Sovereign Swarm Control Plane
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-brightgreen.svg)](https://www.python.org/)
[![gRPC: Enabled](https://img.shields.io/badge/gRPC-Enabled-cyan.svg)](https://grpc.io/)
[![Best Practical: RT Compliant](https://img.shields.io/badge/Request_Tracker-RT_Compliant-purple.svg)](https://bestpractical.com/)

Welcome to the core codebase for the **JetWeb Time Machine** and the **Sovereign Swarm Mesh Control Plane**, available publicly at [jetweb.us](http://jetweb.us). 

This repository hosts a state-of-the-art multi-agent execution framework combining **cryptographic blockchain ledgers**, **4/5 swarm consensus mechanics**, **zero-copy memory bus teleportation**, **Best Practical Request Tracker (RT) compliant auditable ticketing**, and retroactive state timeline refactoring (the **JetWeb Time Machine**).

---

## 🗺️ System Blueprint

```
                      [ Human Supervisor / Web Portal ]
                                      │ (HTTP/REST on Port 8080)
                                      ▼
                      [ Swarm Dashboard Web Server ]
                                      │
                 ┌────────────────────┴────────────────────┐
                 │ (Direct Query)                          │ (gRPC on Port 1111)
                 ▼                                         ▼
     [(SQLite agent_pedigree.db)]             [ gRPC Swarm Control Plane ]
     ├── tickets (RT-Compliant)                            │
     ├── transactions (RT-Compliant)                       ▼
     └── ledger (Verifiable Blocks)             { Swarm Representative Voting }
                                                           │
                                            ┌──────────────┴──────────────┐
                                     (Consensus YES)                (Consensus NO)
                                            ▼                             ▼
                                   [ Commit Block & ]            [ Reject Ticket & ]
                                   [ Rebuild State  ]            [ Minority Report ]
```

---

## 📦 Core Component Directory

*   **`grpc_node/`**
    *   [grpc_server.py](file:///home/aellok/sovereign_mesh/grpc_node/grpc_server.py): Core server orchestrating the 7-Layer pedigree DB, consensus proposals, blockchain ledger, and the JetWeb Time Machine timeline refactoring.
    *   [grpc_client.py](file:///home/aellok/sovereign_mesh/grpc_node/grpc_client.py): CLI interface wrapper supporting interactive testing of all swarm APIs.
    *   [web_server.py](file:///home/aellok/sovereign_mesh/grpc_node/web_server.py): Native REST web server serving the supervision workspace on Port `8080`.
    *   [index.html](file:///home/aellok/sovereign_mesh/grpc_node/index.html): Cybernetic styled Single Page Application dashboard featuring real-time interactive ticket creators and live transaction logs.
*   **`memory_bus/`**
    *   [server.py](file:///home/aellok/sovereign_mesh/memory_bus/server.py) & [client.py](file:///home/aellok/sovereign_mesh/memory_bus/client.py): Zero-copy RAM bus enabling instantaneous virtual teleportation of agents between server environments on Port `11111`.
*   **`proto/`**
    *   [sync.proto](file:///home/aellok/sovereign_mesh/proto/sync.proto): Protobuf definitions for all bidirectional node handshakes.
*   **`mesh_control.sh`**
    *   [mesh_control.sh](file:///home/aellok/sovereign_mesh/mesh_control.sh): Master bash controller script for starting/stopping servers, running clients, and checking ports.

---

## 📚 Deep-Dive Architecture Manuals

For a detailed manual on individual sub-systems, refer to the following GitHub Markdown documents inside `docs/`:

1.  **[7-Layer Pedigree Graph & Swarm Consensus Engine](docs/architecture.md)**: Details voting representation, Layer hierarchies, and minority report research simulations.
2.  **[JetWeb Time Machine & Cryptographic Cascade Re-mining](docs/jetweb-time-machine.md)**: Complete guide to timeline bifurcation, block re-signing, and state tree collapse.
3.  **[Best Practical Request Tracker (RT) Schema Compliance](docs/rt-compliance.md)**: Explains tickets and transactions schemas, and auditable event transaction streams.
4.  **[gRPC Remote Execution API Plane](docs/grpc-api.md)**: Protocols and interfaces for POSIX remote syncs, port mappings, and handshakes.
5.  **[Zero-Copy Shared Memory Teleportation Bus](docs/memory-bus.md)**: Physics of zero-copy `/dev/shm` buffer loading and memory mapping.

---

## ⚡ Quick Start & Execution

### 1. Prerequisites
Ensure you have **Python 3.8+** and **gRPC tools** installed on your POSIX environment:
```bash
pip install grpcio grpcio-tools
```

### 2. Spawn Sovereign Daemons
Launch the gRPC server, memory bus, and the web portal control dashboard via the orchestrator:
```bash
bash mesh_control.sh start
```
*Output Verification:*
```
[STARTING MESH SERVERS]
Launching gRPC Server (Port 1111) in background...
Launching Memory Bus Server (Port 11111) in background...
Launching Swarm Dashboard Web Server (Port 8080) in background...
SUCCESS: Sovereign Mesh & Web Portal are online and listening!
```

### 3. Open Swarm Dashboard
Navigate your web browser to the human supervision portal:
```
http://localhost:8080
```

### 4. Propose Swarm Mutation (CLI)
Submit a state mutation proposal through the local gRPC dialer:
```bash
python3 grpc_node/grpc_client.py --propose model_temperature=0.85 --reason "Optimize creativity"
```

### 5. Trigger Timeline Bifurcation (CLI)
Activate retroactive Time-Travel rewriting at a targeted block:
```bash
python3 grpc_node/grpc_client.py --timemachine 2 --rewrite model_temperature=0.42 --reason "Override historic anomaly"
```

---

## 🌐 Production Host Integration
This repository is configured to be hosted at **[jetweb.us](http://jetweb.us)**. The native REST server served on port `8080` handles high-frequency polling and utilizes responsive, interactive layouts making it immediately suitable for public web deployments.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
