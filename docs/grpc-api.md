# 🔌 gRPC Remote Execution & Swarm Sync API Plane

This document specifies the bidirectional remote execution protocols, socket configurations, failover operations, and protobuf interfaces governing the Swarm Mesh on **Port `1111`**.

---

## 🛰️ gRPC Connection Configurations

*   **gRPC Control Server:** Listens on port `1111` across all active nodes.
*   **Protobuf Contract:** Compiled from [sync.proto](file:///home/aellok/sovereign_mesh/proto/sync.proto) using standard gRPC generators.
*   **Handshake Protocol:** Performs a ping-pong check to calculate network latency and verify online capabilities before launching any execution blocks.

---

## 🛠️ Protobuf Service Specifications

The [sync.proto](file:///home/aellok/sovereign_mesh/proto/sync.proto) schema declares five core RPC endpoints:

```protobuf
service AgentSync {
    // 1. Connectivity Check
    rpc Ping (PingRequest) returns (PingResponse);

    // 2. 7-Layer Pedigree Graph Traversal
    rpc TracePedigree (PedigreeRequest) returns (PedigreeResponse);

    // 3. 4/5 Majority Swarm Mutation Proposal
    rpc ProposeSwarmMutation (MutationRequest) returns (MutationResponse);

    // 4. Ledger Cryptographic Audit Queries
    rpc QuerySwarmLedger (LedgerQueryRequest) returns (LedgerQueryResponse);

    // 5. JetWeb Time Machine RetroactiveTimeline Override
    rpc TimeTravelOverride (TimeTravelRequest) returns (TimeTravelResponse);
}
```

---

## 🛡️ SSH Failover Remote Execution

To ensure absolute operational resilience in high-latency or unstable networks, the [grpc_client.py](file:///home/aellok/sovereign_mesh/grpc_node/grpc_client.py) execution dialer implements an **automatic fallback mechanism**.

```
[ Initiate remote Execution Command ]
                 │
                 ▼
     { Is gRPC Port 1111 Active? }
                 │
        ┌────────┴────────┐
        ▼ (YES)           ▼ (NO / Latency Timeout)
   [ Execute via ]   [ FALLBACK: Trigger POSIX ]
   [  gRPC Server ]   [ remote SSH Command Pipe ]
                          │
                          ▼
                 * Dial remote SSH Port 22
                 * Verify SSH Keys matching target
                 * Stream command stdout to terminal
```

This guarantees that even if a node's gRPC daemon goes offline or becomes blocked, human operators and agent swarms can maintain supervision controls over all server terminals via fallback POSIX SSH pipelines.
