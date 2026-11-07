"""Consent Ledger: Append-only consent records per subject and purpose.

Helps demonstrate consent and its withdrawal (GDPR Art. 7(1) and 7(3)) but does not
decide lawfulness, does not cover erasure requests (deleting events is the store owner's
decision) and is not legal advice.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol, runtime_checkable

__all__ = [
    "ConsentError",
    "ConsentErrorCode",
    "ConsentEvent",
    "ConsentLedger",
    "ConsentStatus",
    "EventStore",
    "InMemoryEventStore",
    "LedgerEvent",
    "__version__",
]

__version__ = "0.1.0"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

ConsentErrorCode = Literal[
    "event_conflict",
    "clock_regression",
    "invalid_clock",
    "invalid_subject",
    "invalid_purpose",
    "invalid_policy_version",
    "invalid_source",
    "invalid_event_id",
    "store_full",
]

_SUBJECT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PURPOSE_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_POLICY_VERSION_RE = re.compile(
    r"^Pd{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]Pd|3[01])$".replace("Pd", r"\d")
)


class ConsentError(Exception):
    """Base exception raised by consent-ledger operations."""

    def __init__(self, code: ConsentErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: ConsentErrorCode = code


@dataclass(frozen=True)
class ConsentEvent:
    """An immutable recorded consent event."""

    event_id: str
    subject_id: str
    purpose: str
    action: Literal["grant", "withdraw"]
    policy_version: str
    source: str
    recorded_at: datetime
    seq: int


@dataclass(frozen=True)
class ConsentStatus:
    """Status of consent for a specific subject and purpose at a point in time."""

    state: Literal["granted", "withdrawn", "none", "stale"]
    policy_version: str | None
    since: datetime | None


@dataclass(frozen=True)
class LedgerEvent:
    """Telemetry/audit notification event emitted on ledger operations.

    Never includes subject_id or source for privacy preservation.
    """

    kind: Literal["recorded", "rejected"]
    purpose: str | None
    action: str | None
    code: str | None = None


@runtime_checkable
class EventStore(Protocol):
    """Storage contract for append-only consent events."""

    def append(self, e: ConsentEvent) -> None:
        """Append an event to the store."""
        ...

    def events_for(self, subject_id: str) -> list[ConsentEvent]:
        """Retrieve all events for a subject in recorded order."""
        ...

    def get(self, event_id: str) -> ConsentEvent | None:
        """Retrieve an event by its unique event_id."""
        ...

    def count(self) -> int:
        """Return the total count of events in the store."""
        ...


class InMemoryEventStore:
    """In-memory implementation of EventStore refusing when full without eviction."""

    def __init__(self, max_events: int = 1_000_000) -> None:
        if max_events < 1:
            raise ValueError("max_events must be positive")
        self.max_events = max_events
        self._events: list[ConsentEvent] = []
        self._by_id: dict[str, ConsentEvent] = {}
        self._by_subject: dict[str, list[ConsentEvent]] = {}

    def append(self, e: ConsentEvent) -> None:
        if len(self._events) >= self.max_events:
            raise ConsentError("store_full", "Event store capacity exceeded")
        self._events.append(e)
        self._by_id[e.event_id] = e
        if e.subject_id not in self._by_subject:
            self._by_subject[e.subject_id] = []
        self._by_subject[e.subject_id].append(e)

    def events_for(self, subject_id: str) -> list[ConsentEvent]:
        return list(self._by_subject.get(subject_id, []))

    def get(self, event_id: str) -> ConsentEvent | None:
        return self._by_id.get(event_id)

    def count(self) -> int:
        return len(self._events)


def _format_iso8601_utc(dt: datetime) -> str:
    """Format UTC datetime as YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS.ffffffZ."""
    dt_utc = dt.astimezone(timezone.utc)
    if dt_utc.microsecond:
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_valid_ascii_source(source: str) -> bool:
    if not (1 <= len(source) <= 64):
        return False
    return all(32 <= ord(c) <= 126 for c in source)


class ConsentLedger:
    """Append-only ledger managing consent grants and withdrawals."""

    def __init__(
        self,
        store: EventStore | None = None,
        *,
        clock: Callable[[], datetime],
        on_event: Callable[[LedgerEvent], None] | None = None,
    ) -> None:
        self._store: EventStore = store if store is not None else InMemoryEventStore()
        self._clock: Callable[[], datetime] = clock
        self._on_event: Callable[[LedgerEvent], None] | None = on_event
        self._last_recorded_at: datetime | None = None
        self._next_seq: int = 1

    def _notify(
        self,
        kind: Literal["recorded", "rejected"],
        purpose: str | None,
        action: str | None,
        code: str | None = None,
    ) -> None:
        if self._on_event is not None:
            try:
                self._on_event(LedgerEvent(kind=kind, purpose=purpose, action=action, code=code))
            except Exception:
                logger.exception("on_event callback raised an exception")

    def record(
        self,
        subject_id: str,
        purpose: str,
        action: Literal["grant", "withdraw"],
        policy_version: str,
        *,
        source: str,
        event_id: str,
    ) -> ConsentEvent:
        """Record a consent grant or withdrawal idempotently."""
        raw_purpose: str | None = purpose if isinstance(purpose, str) else None
        raw_action: str | None = action if isinstance(action, str) else None

        # 1. Validate fields
        if not isinstance(subject_id, str) or not _SUBJECT_ID_RE.match(subject_id):
            self._notify("rejected", raw_purpose, raw_action, "invalid_subject")
            raise ConsentError("invalid_subject", "Invalid subject_id format")

        if not isinstance(purpose, str) or not _PURPOSE_RE.match(purpose):
            self._notify("rejected", raw_purpose, raw_action, "invalid_purpose")
            raise ConsentError("invalid_purpose", "Invalid purpose format")

        if action not in ("grant", "withdraw"):
            self._notify("rejected", raw_purpose, raw_action, "invalid_purpose")
            raise ConsentError("invalid_purpose", "Action must be 'grant' or 'withdraw'")

        if not isinstance(policy_version, str) or not _POLICY_VERSION_RE.match(policy_version):
            self._notify("rejected", raw_purpose, raw_action, "invalid_policy_version")
            raise ConsentError("invalid_policy_version", "Invalid policy_version format")

        # Verify valid calendar date (e.g., reject 2026-02-30)
        try:
            datetime.strptime(policy_version, "%Y-%m-%d")
        except ValueError:
            self._notify("rejected", raw_purpose, raw_action, "invalid_policy_version")
            raise ConsentError(
                "invalid_policy_version", "Invalid policy_version calendar date"
            ) from None

        if not isinstance(source, str) or not _is_valid_ascii_source(source):
            self._notify("rejected", raw_purpose, raw_action, "invalid_source")
            raise ConsentError("invalid_source", "Invalid source format")

        if not isinstance(event_id, str) or not _EVENT_ID_RE.match(event_id):
            self._notify("rejected", raw_purpose, raw_action, "invalid_event_id")
            raise ConsentError("invalid_event_id", "Invalid event_id format")

        # 2. Clock validation
        try:
            now = self._clock()
        except Exception as exc:
            self._notify("rejected", raw_purpose, raw_action, "invalid_clock")
            raise ConsentError("invalid_clock", f"Clock failed: {exc}") from exc

        if not isinstance(now, datetime) or now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
            self._notify("rejected", raw_purpose, raw_action, "invalid_clock")
            raise ConsentError("invalid_clock", "Clock must return an aware datetime")

        now_utc = now.astimezone(timezone.utc)
        if self._last_recorded_at is not None and now_utc < self._last_recorded_at:
            self._notify("rejected", raw_purpose, raw_action, "clock_regression")
            raise ConsentError("clock_regression", "Clock regression detected")

        # 3. Idempotency check
        existing = self._store.get(event_id)
        if existing is not None:
            if (
                existing.subject_id == subject_id
                and existing.purpose == purpose
                and existing.action == action
                and existing.policy_version == policy_version
                and existing.source == source
            ):
                return existing
            self._notify("rejected", raw_purpose, raw_action, "event_conflict")
            raise ConsentError(
                "event_conflict", f"Event ID {event_id} already exists with differing payload"
            )

        # 4. Capacity and append
        event = ConsentEvent(
            event_id=event_id,
            subject_id=subject_id,
            purpose=purpose,
            action=action,
            policy_version=policy_version,
            source=source,
            recorded_at=now_utc,
            seq=self._next_seq,
        )

        try:
            self._store.append(event)
        except ConsentError as err:
            self._notify("rejected", raw_purpose, raw_action, err.code)
            raise

        self._last_recorded_at = now_utc
        self._next_seq += 1
        self._notify("recorded", purpose, action)
        return event

    def status(
        self,
        subject_id: str,
        purpose: str,
        *,
        at: datetime | None = None,
        min_policy_version: str | None = None,
    ) -> ConsentStatus:
        """Evaluate consent status for a subject and purpose, optionally point-in-time."""
        if at is not None:
            if not isinstance(at, datetime) or at.tzinfo is None or at.tzinfo.utcoffset(at) is None:
                raise ConsentError("invalid_clock", "'at' datetime must be timezone-aware")
            at_utc = at.astimezone(timezone.utc)
        else:
            at_utc = None

        events = self._store.events_for(subject_id)
        # Filter by purpose
        purpose_events = [e for e in events if e.purpose == purpose]

        # Filter by point-in-time
        if at_utc is not None:
            purpose_events = [e for e in purpose_events if e.recorded_at <= at_utc]

        if not purpose_events:
            return ConsentStatus(state="none", policy_version=None, since=None)

        # Sort by (recorded_at, seq)
        purpose_events.sort(key=lambda e: (e.recorded_at, e.seq))
        latest = purpose_events[-1]

        if latest.action == "withdraw":
            return ConsentStatus(
                state="withdrawn", policy_version=latest.policy_version, since=latest.recorded_at
            )

        # Action is 'grant'
        if min_policy_version is not None and latest.policy_version < min_policy_version:
            return ConsentStatus(
                state="stale", policy_version=latest.policy_version, since=latest.recorded_at
            )

        return ConsentStatus(
            state="granted", policy_version=latest.policy_version, since=latest.recorded_at
        )

    def history(self, subject_id: str) -> list[ConsentEvent]:
        """Return full history of consent events for a subject ordered by (recorded_at, seq)."""
        events = self._store.events_for(subject_id)
        return sorted(events, key=lambda e: (e.recorded_at, e.seq))

    def export(self, subject_id: str) -> str:
        """Export subject consent history to canonical JSON string."""
        events = self.history(subject_id)
        export_events = [
            {
                "action": e.action,
                "event_id": e.event_id,
                "policy_version": e.policy_version,
                "purpose": e.purpose,
                "recorded_at": _format_iso8601_utc(e.recorded_at),
                "source": e.source,
            }
            for e in events
        ]
        payload = {
            "events": export_events,
            "subject_id": subject_id,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
