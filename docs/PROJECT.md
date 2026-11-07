# Project record

## Objective

To provide an append-only ledger for consent management that enables auditing, version tracking, and point-in-time status queries for subject purposes.

## Scope

- Append-only event storage for consent records.
- Validation of events (format, clock, idempotency).
- Point-in-time consent status evaluation.
- Export of consent history to canonical JSON.
- Support for `InMemoryEventStore` with strict capacity enforcement.

## Out of Scope

- Persistence adapters beyond the `EventStore` protocol.
- Tamper evidence or hash chaining (combine with a dedicated audit log library if required).
- UI or cookie banner integration.

## Factory run u186 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | gemini-3.8-flash | yes | 4472 | 9819 | 0 | 0 | 0.0201 |
| audit | gemini-3.1-flash-lite | no | 94052 | 422 | 0 | 320803 | 0.0322 |
| docs | gemini-3.1-flash-lite | no | 190580 | 1242 | 0 | 0 | 0.0495 |

Total: $0.1018. Prices: Anthropic list prices.
