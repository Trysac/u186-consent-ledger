# consent-ledger

Append-only consent records per subject and purpose with policy versions, point-in-time status, stale consent detection, idempotent events and JSON export.

## The Problem

Products often record consent as a mutable boolean column that is overwritten on every change. This makes it impossible to reconstruct the state of consent at a specific time, to verify which policy version was in effect, or to audit a user's consent history. `consent-ledger` solves this by keeping consent as an append-only, versioned ledger that answers point-in-time questions deterministically.

## Installation

```bash
pip install consent-ledger
```

## Usage

```python
from datetime import datetime, timezone
from consent_ledger import ConsentLedger

ledger = ConsentLedger(clock=lambda: datetime.now(timezone.utc))
ledger.record("usr_123", "marketing", "grant", "2026-01-01", source="web", event_id="evt_1")
status = ledger.status("usr_123", "marketing", min_policy_version="2026-01-01")
assert status.state == "granted"
print(ledger.export("usr_123"))
```

## Summary of API

- `ConsentLedger(store, clock, on_event)`: Main entry point for recording and querying.
- `record(...)`: Records a grant/withdraw event; fails on clock regression or conflict.
- `status(...)`: Returns `granted`, `withdrawn`, `none`, or `stale` (point-in-time).
- `history(...)`: Full event sequence for a subject.
- `export(...)`: JSON representation of history.

### Errors
Raises `ConsentError` with codes: `event_conflict`, `clock_regression`, `invalid_clock`, `invalid_subject`, `invalid_purpose`, `invalid_policy_version`, `invalid_source`, `invalid_event_id`, `store_full`.

## Why not a Consent SaaS?

Using `consent-ledger` keeps your audit trail local and under your control, ensuring you have deterministic answers without relying on third-party availability or data egress costs.

## Compliance

This utility helps demonstrate consent and its withdrawal (GDPR Art. 7(1) and 7(3)) but does not decide lawfulness, does not cover erasure requests (deleting events is the store owner's decision) and is not legal advice. See [docs/SECURITY.md](docs/SECURITY.md).
