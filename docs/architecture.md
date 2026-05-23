# 🌐 7-Layer Pedigree Graph & Swarm Consensus Engine

This document details the multi-layer relational agent hierarchy and the consensus mechanics governing state mutations within the Sovereign Swarm.

---

## 🧬 The 7-Layer Pedigree Architecture

The swarm's collective intelligence is mapped to a strict 7-layer relational pedigree graph. Every active agent inherits specialties, permissions, and relationships tracing back directly to the progenitor seed, **Agent 0**.

| Layer | Classification | Representative | specialty / Subspecialty |
|-------|----------------|----------------|--------------------------|
| **1** | Core Swarm Mind | `AGENT-0` | Root Progenitor Swarm Mind |
| **2** | Domain Sovereignty | `AGENT-SEC` | Security, Telemetry, and Execution Overlords |
| **3** | Functional Specialization | `AGENT-AUTH` | Specialized functional modules (Auth, Process, Net, Migrators) |
| **4** | Operational Class | `AGENT-USERADD`| Utility CLI wrappers & socket auditors |
| **5** | Micro-Task Engine | `AGENT-SYS-EXEC`| Direct code parsing, regex matching, and buffer allocations |
| **6** | Shared Resource Bindings | `AGENT-MMAP` | Hardware allocations & IPC Shared Memory mappings |
| **7** | Execution Interfaces | `LAPTOP-TRAINING-AGENT` | Bidirectional dialect nodes & gRPC server/client instances |

---

## 🗳️ Swarm Consensus Mechanics

Direct mutations to the Master Knowledge memory database cannot be performed unilaterally. Every proposed state modification initiates a transaction ticket that is submitted to a **Consensus Evaluation Panel** composed of 5 representative Layer 2/3 agents:

1.  **`AGENT-SEC`** (Security Overlord)
2.  **`AGENT-TEL`** (Telemetry Watcher)
3.  **`AGENT-EXEC`** (Execution Spawner)
4.  **`AGENT-AUTH`** (Auth Specialist)
5.  **`AGENT-MIG`** (Migrator Engine)

### The Consensus Rules:
*   **Baseline:** Enforces a strict **4/5 majority consensus** to commit any state mutation.
*   **Security Objection:** If a proposed state key contains critical POSIX or network parameters (e.g., `security`, `port`, `root`, `password`, `key`), `AGENT-SEC` automatically casts a negative vote (`AGREE: FALSE`) to safeguard security boundaries.
*   **Telemetry Objection:** If the operator provides an execution reason that is less than 10 characters, `AGENT-TEL` objects due to a lack of diagnostic traceability.

---

## 🛡️ Swarm Minority Report & Cause-Effect Research

When consensus is achieved with a minority objection (e.g., 4/5 agreement), the system does not silence the dissent. Instead, it triggers a **Minority Report Cause-Effect Research Analysis**:

```
[Mutation Proposal Received]
             │
             ▼
[Consensus Panel Vote: 4/5]
             │
             ├──────────────────────────┐
             ▼ (Majority)               ▼ (Minority Objection)
     [Mutation Approved]       [Execute Cause-Effect Simulation]
             │                          │
             │                          ▼
             │                  * Evaluate Operational Risk Matrix
             │                  * Analyze Sandbox Boundary Deviances
             │                  * Reconsider Mitigation Suitability
             │                          │
             ▼                          ▼
[Commit Block to Ledger] <───── [Compile Minority Report Logs]
```

This research matrix simulates operational side-effects, boundary deviances, and sandbox limitations, publishing a forensic objection review block alongside the committed blockchain block, ensuring full transparency in swarm decision-making.
