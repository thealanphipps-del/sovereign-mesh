# ⏰ JetWeb Time Machine & Timeline Refactoring Engine

This document outlines the operational mechanics behind the **JetWeb Time Machine**, a retroactive state refactoring engine that enables supervisors to go back in time, override past swarm decisions, and programmatically recalculate ledger histories.

---

## ⏳ The Retroactive Refactoring Concept

In a standard distributed ledger or blockchain, past blocks are immutable; they can never be modified. However, the JetWeb Time Machine introduces a **verifiable state-collapse hard-fork mechanism** for supervised agent swarms.

If an agent or human supervisor determines that a decision made at Block index `T` was suboptimal or malicious, they can invoke the Time Machine to rewrite that decision:

```
Legacy Ledger:
[Block 1] ──► [Block 2 (Bad Key=Val)] ──► [Block 3] ──► [Block 4] (Corrupted State)

            INVOKE TIME MACHINE OVERRIDE AT BLOCK 2

Refactored Ledger (New Hash Sequence):
[Block 1] ──► [Block 2' (New Key=Val)] ──► [Block 3'] ──► [Block 4'] (Harmonized State)
```

---

## 🔒 Cryptographic Cascade Re-Mining

To prevent cryptographic corruption (where subsequent blocks would have invalid `previous_hash` chains), the Time Machine performs an **instantaneous cascade re-mining algorithm**:

1.  **Block Targeting:** The database locks and retrieves all blocks sequentially from index `1` to `N`.
2.  **Payload Mutation:** The targeted block `T`'s payload, consensus votes, and minority reports are overwritten with the supervisor's new overrides.
3.  **Hash Recalculation:** The Time Machine recalculates Block `T`'s unique SHA-256 signature using the new payload parameters:
    $$\text{Hash}_T = \text{SHA256}(T \mathbin{\Vert} \text{PrevHash}_T \mathbin{\Vert} \text{Timestamp}_T \mathbin{\Vert} \text{AgentId}_T \mathbin{\Vert} \text{NewPayload}_T \mathbin{\Vert} \text{NewVotes}_T \mathbin{\Vert} \text{NewMinorityReport}_T)$$
4.  **Sequential Chain Propagation:** For every subsequent block $i$ (where $i > T$):
    *   The `previous_hash` parameter is updated to $\text{Hash}_{i-1}$.
    *   The Block's unique signature $\text{Hash}_i$ is recomputed, cascade-linking the entire cryptographic chain to the end of the ledger.
5.  **State Tree Replay:** To ensure state consistency:
    *   The `master_knowledge` state table is cleared entirely.
    *   The database sequentially replays the newly mined ledger payload blocks in ascending index order, rebuilding the active operational database.

---

## 📝 Time Machine Ticket Logging

To maintain complete accountability under Request Tracker principles, every Time Machine override triggers:
1.  A ticket in the `Time-Machine` queue.
2.  A `Create` transaction.
3.  A `Timeline-Fork` transaction detail-logging the transition from `Block #T legacy state` to `Block #T overridden state`, including hashes.
