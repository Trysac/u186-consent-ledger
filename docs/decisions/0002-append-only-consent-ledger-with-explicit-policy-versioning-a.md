# Append-Only Consent Ledger with Explicit Policy Versioning and Point-in-Time Status

Status: accepted (generated, pending human review)

## Context

Traditional boolean flags for consent do not provide verifiable audit trails under data protection frameworks such as GDPR Art. 7. SaaS solutions introduce external dependencies and privacy risks. A lightweight, embedded Python library is required to record versioned consent grants and withdrawals idempotently.

## Decision

Implement an append-only event-driven ConsentLedger using a pluggable EventStore protocol, immutable ConsentEvent dataclasses, deterministic sequence numbering, strict ISO 8601 UTC time tracking, and privacy-preserving LedgerEvent telemetry.

## Consequences

Applications gain deterministic point-in-time consent verification and audit export capabilities with zero external dependencies, while keeping storage capacity bounded and preventing clock regression.
