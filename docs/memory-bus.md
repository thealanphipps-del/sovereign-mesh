# ⚡ High-Speed Shared Memory Zero-Copy Teleportation Bus

This document details the architecture of our **High-Speed RAM Memory Bus**, served on **Port `11111`**, enabling virtual agent teleportation between server environments using zero-copy `/dev/shm` shared memory maps.

---

## 🚀 Concept of Virtual Teleportation

In standard architectures, transferring large agent memory states, neural weights, or relational tables requires serializing, transmitting over socket protocols, and deserializing. This introduces severe latency.

Our Memory Bus eliminates this bottleneck on shared local and hypervisor environments. Using a **Zero-Copy mmap direct buffer interface**, agents can instantly write state buffers directly into POSIX shared memory pages:

```
[ Agent on Node A ]                       [ Agent on Node B ]
        │                                         ▲
        ▼ (Direct Write)                          │ (Direct Read)
┌───────────────────────────────────────────────────────────┐
│              /dev/shm/sovereign_page_table               │ (POSIX Shared RAM Page)
└───────────────────────────────────────────────────────────┘
        ▲                                         ▲
        └───────────────────┬─────────────────────┘
                            │ (Telemetry Sync)
                            ▼
               [ Memory Bus Port 11111 ]
```

---

## ⚙️ Memory Bus Page Allocation

When `mesh_control.sh` initializes the High-Speed RAM Bus:
1.  **Memory Seeding:** The memory bus server creates a `sovereign_page_table` directly inside the system's volatile shared memory folder `/dev/shm/`.
2.  **Shared Memory Map (`mmap`):** It maps a $64\text{MB}$ memory buffer block, reserving partitions for agent state synchronization.
3.  **Active Slot Registry:** Teleporting agents query Port `11111` to request a memory slot, instantly receive a direct pointer to the RAM address segment, and read/write states with **zero CPU serialization overhead**.
4.  **Resilience Tracking:** If a hypervisor link drops, the memory bus automatically falls back to streaming state payloads via standard TCP streams to maintain operational continuity.
