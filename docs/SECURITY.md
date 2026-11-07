# Security and Privacy

## Threat Model

### Defended
- **Idempotency**: Prevents duplicate event insertion with the same `event_id`.
- **Integrity**: `record` rejects events on clock regression, invalid time, or malformed data before persistence.
- **Privacy**: The `on_event` callback purposefully excludes `subject_id` and `source` in its `LedgerEvent` telemetry to avoid PII leakage in monitoring systems.
- **Capacity**: `InMemoryEventStore` enforces a hard `max_events` limit and refuses new events rather than silently evicting data, which is critical for compliance records.

### Not Defended
- **Right to Erasure (GDPR Art. 17)**: This library is strictly append-only. Deleting or redacting events from the store is the responsibility of the store implementation or the owner's operational process.
- **Legal Lawfulness**: This is a technical bookkeeping tool; it does not determine whether consent was lawfully obtained or sufficient for a specific processing activity.
