# Architecture

## Design Overview

`consent_ledger` provides an append-only event-sourced ledger for user consent management.

### Components

1. **ConsentLedger**: Orchestrates validation, ordering, event recording, and status queries.
2. **ConsentEvent**: Frozen dataclass representing an immutable record in the ledger.
3. **EventStore Protocol**: Decouples event persistence from ledger business logic.
4. **InMemoryEventStore**: Default in-memory implementation with strict capacity limits to avoid silent event loss.
5. **ConsentStatus**: Evaluates the effective consent state (`granted`, `withdrawn`, `stale`, `none`) at any point in time.

### Validation Pipeline

When `ConsentLedger.record` is invoked, operations follow a strict sequence:
1. Field formats validation (subject_id, purpose, action, policy_version, source, event_id).
2. Time validation (aware UTC datetime, non-regressing clock).
3. Idempotency check (matches existing event or raises `event_conflict`).
4. Capacity check on store.
5. Event append and sequence increment.

On any failure, no event is committed to the store, and an `on_event` notification is dispatched without sensitive identifiers.
