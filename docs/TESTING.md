# Testing

Tests are located in `tests/` and cover the public API behavior, validation logic, and compliance with the specification.

- `tests/test_consent_ledger.py`: Contains acceptance tests that verify:
    - Recording grants/withdrawals.
    - Point-in-time status queries.
    - Idempotency checks.
    - Clock regression prevention.
    - Validation errors for inputs (subjects, purposes, policy versions).
    - Capacity enforcement (`store_full`).
    - JSON export format correctness.
    - Telemetry notification logic for recorded and rejected events.
