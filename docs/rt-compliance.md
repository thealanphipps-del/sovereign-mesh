# 📊 Best Practical Request Tracker (RT) Schema Compliance

This document maps our swarm's memory databases directly to the data modeling guidelines of **Best Practical's Request Tracker (RT)**, the legendary enterprise issue-tracking engine.

---

## 🛠️ Data Modeling Principles

Best Practical's RT utilizes a highly scalable, event-driven auditing paradigm. Rather than storing flat status records, every operational action writes a permanent **Transaction** row referencing a parent **Ticket**. Our swarm implements this exact data structure to guarantee 100% auditable supervision trace mapping.

```
                      ┌──────────────────┐
                      │    RT::Ticket    │
                      └────────┬─────────┘
                               │ (1 to Many)
                               ▼
                    ┌─────────────────────┐
                    │   RT::Transaction   │
                    └──────────┬──────────┘
                               │ (Event Types)
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
    [ Type: Create ]     [ Type: Status ]      [ Type: Set ]
    * Seeding Logs       * State Changes       * Value Overrides
```

---

## 📐 Relational Database Schema Maps

The `agent_pedigree.db` SQLite catalog contains two fully RT-compliant tables:

### 1. The `tickets` Table
This table holds the operational tickets submitted by active agents or human supervisors.

| Column | SQL Type | Description | RT Compliance Mapping |
|--------|----------|-------------|-----------------------|
| `ticket_id` | `INTEGER` | Auto-incrementing primary key | Unique Ticket Identifier |
| `Queue` | `TEXT` | Work queue name (e.g. `Swarm-Mutations`, `Time-Machine`) | Queue Partitioning |
| `Subject` | `TEXT` | Summary of the proposed action | Ticket Subject Text |
| `Status` | `TEXT` | Lifecycle status (`new`, `resolved`, `rejected`) | Ticket Lifecycle Status |
| `Owner` | `TEXT` | Assigned worker agent (`Nobody` or specific agent) | Assigned Ticket Owner |
| `Creator` | `TEXT` | Proposing agent ID | Principal Creator |
| `Priority` | `INTEGER` | Task execution urgency index | Numerical Priority Model |
| `TimeEstimated` | `INTEGER` | Expected operational timeframe (minutes) | Duration Estimator |
| `TimeWorked` | `INTEGER` | Time already expended on task | Accumulator Metrics |
| `TimeLeft` | `INTEGER` | Remaining estimate to resolution | Active Delta Track |
| `Created` | `TEXT` | Timestamp of proposal creation | ISO Creation Date |
| `Resolved` | `TEXT` | Timestamp of commit/rejection resolution | ISO Resolution Date |
| `LastUpdated` | `TEXT` | Timestamp of most recent modification | ISO Update Track |
| `LastUpdatedBy`| `TEXT` | Agent performing the modification | Modifying Principal |

### 2. The `transactions` Table
Tracks every lifecycle event and state parameter override.

| Column | SQL Type | Description | RT Compliance Mapping |
|--------|----------|-------------|-----------------------|
| `transaction_id`| `INTEGER` | Unique Transaction sequence key | Transaction Identifier |
| `ObjectType` | `TEXT` | Target type reference (e.g., `RT::Ticket`) | Polymorphic Type Binding |
| `ObjectId` | `INTEGER` | Foreign key referencing `tickets.ticket_id` | Core Object Reference |
| `TimeTaken` | `INTEGER` | Work hours spent on this transaction | Activity Duration |
| `Type` | `TEXT` | Event classification (`Create`, `Status`, `Set`, `Timeline-Fork`) | Transaction Event Type |
| `Field` | `TEXT` | Modified parameter key (e.g., `model_temperature`) | target Parameter Field |
| `OldValue` | `TEXT` | Pre-mutation parameter value | Historical State |
| `NewValue` | `TEXT` | Post-mutation parameter value | Advanced State |
| `Data` | `TEXT` | Narrative description of the event | Detailed Transaction log |
| `Creator` | `TEXT` | Executing agent ID | Acting Principal |
| `Created` | `TEXT` | Timestamp of transaction logging | ISO Timestamp |
