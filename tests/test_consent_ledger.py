"""Comprehensive tests for consent_ledger."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from consent_ledger import (
    ConsentError,
    ConsentEvent,
    ConsentLedger,
    InMemoryEventStore,
    LedgerEvent,
)


def test_acceptance_item_1() -> None:
    # Acceptance test 1
    clock_time = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger = ConsentLedger(clock=lambda: clock_time)
    event = ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")
    assert isinstance(event, ConsentEvent)

    status_m = ledger.status("s1", "marketing")
    assert status_m.state == "granted"
    assert status_m.policy_version == "2026-01-01"
    assert status_m.since == datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)

    status_a = ledger.status("s1", "analytics")
    assert status_a.state == "none"


def test_acceptance_item_2() -> None:
    # Acceptance test 2: withdraw recorded at 11:00
    t_1000 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    t_1100 = datetime(2026, 11, 6, 11, 0, 0, tzinfo=timezone.utc)
    t_1030 = datetime(2026, 11, 6, 10, 30, 0, tzinfo=timezone.utc)
    t_0900 = datetime(2026, 11, 6, 9, 0, 0, tzinfo=timezone.utc)

    current_time = t_1000
    ledger = ConsentLedger(clock=lambda: current_time)
    ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")

    current_time = t_1100
    ledger.record("s1", "marketing", "withdraw", "2026-01-01", source="web", event_id="e2")

    assert ledger.status("s1", "marketing").state == "withdrawn"
    assert ledger.status("s1", "marketing", at=t_1030).state == "granted"
    assert ledger.status("s1", "marketing", at=t_0900).state == "none"


def test_acceptance_item_3() -> None:
    # Acceptance test 3: stale consent vs later grant
    t0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger = ConsentLedger(clock=lambda: t0)
    ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")

    st = ledger.status("s1", "marketing", min_policy_version="2026-06-01")
    assert st.state == "stale"

    ledger.record("s1", "marketing", "grant", "2026-06-01", source="web", event_id="e2")
    st2 = ledger.status("s1", "marketing", min_policy_version="2026-06-01")
    assert st2.state == "granted"


def test_acceptance_item_4() -> None:
    # Acceptance test 4: idempotency and conflict
    t0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger = ConsentLedger(clock=lambda: t0)
    e1 = ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")

    # Recording e1 again with identical fields returns original event and len(history('s1')) == 1
    e1_dup = ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")
    assert e1_dup == e1
    assert len(ledger.history("s1")) == 1

    # Recording e1 with action 'withdraw' raises ConsentError with code 'event_conflict'
    with pytest.raises(ConsentError) as exc_info:
        ledger.record("s1", "marketing", "withdraw", "2026-01-01", source="web", event_id="e1")
    assert exc_info.value.code == "event_conflict"
    assert len(ledger.history("s1")) == 1


def test_acceptance_item_5() -> None:
    # Acceptance test 5: clock regression and naive clock
    t1 = datetime(2026, 11, 6, 11, 0, 0, tzinfo=timezone.utc)
    t0 = datetime(2026, 11, 6, 9, 0, 0, tzinfo=timezone.utc)
    current_time: Any = t1
    ledger = ConsentLedger(clock=lambda: current_time)
    ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")

    current_time = t0
    with pytest.raises(ConsentError) as exc_info:
        ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e2")
    assert exc_info.value.code == "clock_regression"
    assert len(ledger.history("s1")) == 1

    # Naive clock raises invalid_clock
    current_time = datetime(2026, 11, 6, 12, 0, 0)
    with pytest.raises(ConsentError) as exc_info2:
        ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e3")
    assert exc_info2.value.code == "invalid_clock"


def test_acceptance_item_6() -> None:
    # Acceptance test 6: field validation and store_full
    t0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger = ConsentLedger(clock=lambda: t0)

    with pytest.raises(ConsentError) as exc1:
        ledger.record("a b", "marketing", "grant", "2026-01-01", source="web", event_id="e1")
    assert exc1.value.code == "invalid_subject"

    with pytest.raises(ConsentError) as exc2:
        ledger.record("s1", "Marketing", "grant", "2026-01-01", source="web", event_id="e1")
    assert exc2.value.code == "invalid_purpose"

    with pytest.raises(ConsentError) as exc3:
        ledger.record("s1", "marketing", "grant", "2026-1-1", source="web", event_id="e1")
    assert exc3.value.code == "invalid_policy_version"

    # InMemoryEventStore(max_events=2)
    small_store = InMemoryEventStore(max_events=2)
    ledger2 = ConsentLedger(store=small_store, clock=lambda: t0)
    ledger2.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")
    ledger2.record("s1", "marketing", "withdraw", "2026-01-01", source="web", event_id="e2")

    with pytest.raises(ConsentError) as exc4:
        ledger2.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e3")
    assert exc4.value.code == "store_full"
    assert small_store.count() == 2
    assert len(ledger2.history("s1")) == 2


def test_acceptance_item_7() -> None:
    # Acceptance test 7: export string exact format
    clock_time = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger = ConsentLedger(clock=lambda: clock_time)
    ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")

    expected = '{"events":[{"action":"grant","event_id":"e1","policy_version":"2026-01-01","purpose":"marketing","recorded_at":"2026-11-06T10:00:00Z","source":"web"}],"subject_id":"s1"}'
    assert ledger.export("s1") == expected


def test_acceptance_item_8() -> None:
    # Acceptance test 8: on_event telemetry and privacy guarantee
    events: list[LedgerEvent] = []
    clock_time = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger = ConsentLedger(clock=lambda: clock_time, on_event=events.append)

    # Successful record
    ledger.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")
    assert len(events) == 1
    assert events[0] == LedgerEvent(kind="recorded", purpose="marketing", action="grant", code=None)

    # Failed record with error code
    with pytest.raises(ConsentError):
        ledger.record(
            "invalid subject!", "marketing", "grant", "2026-01-01", source="web", event_id="e2"
        )

    assert len(events) == 2
    assert events[1] == LedgerEvent(
        kind="rejected", purpose="marketing", action="grant", code="invalid_subject"
    )

    # Verify no payload contains subject_id or source
    for ev in events:
        assert not hasattr(ev, "subject_id")
        assert not hasattr(ev, "source")
        # String representation check
        assert "s1" not in repr(ev)
        assert "web" not in repr(ev)


def test_edge_cases_and_error_paths() -> None:
    t0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger = ConsentLedger(clock=lambda: t0)

    # Action validation
    with pytest.raises(ConsentError) as exc:
        ledger.record(
            "s1", "marketing", "invalid_action", "2026-01-01", source="web", event_id="e1"
        )  # type: ignore[arg-type]
    assert exc.value.code == "invalid_purpose"

    # Calendar date validation for policy_version
    with pytest.raises(ConsentError) as exc_cal:
        ledger.record("s1", "marketing", "grant", "2026-02-30", source="web", event_id="e1")
    assert exc_cal.value.code == "invalid_policy_version"

    # Source validation (non-ascii or invalid len)
    with pytest.raises(ConsentError) as exc_src:
        ledger.record("s1", "marketing", "grant", "2026-01-01", source="café", event_id="e1")
    assert exc_src.value.code == "invalid_source"

    with pytest.raises(ConsentError) as exc_src_empty:
        ledger.record("s1", "marketing", "grant", "2026-01-01", source="", event_id="e1")
    assert exc_src_empty.value.code == "invalid_source"

    with pytest.raises(ConsentError) as exc_src_long:
        ledger.record("s1", "marketing", "grant", "2026-01-01", source="a" * 65, event_id="e1")
    assert exc_src_long.value.code == "invalid_source"

    # Event ID validation
    with pytest.raises(ConsentError) as exc_eid:
        ledger.record(
            "s1", "marketing", "grant", "2026-01-01", source="web", event_id="invalid event!"
        )
    assert exc_eid.value.code == "invalid_event_id"

    # Clock exception
    def failing_clock() -> datetime:
        raise RuntimeError("hardware clock failure")

    ledger_failing_clock = ConsentLedger(clock=failing_clock)
    with pytest.raises(ConsentError) as exc_clk:
        ledger_failing_clock.record(
            "s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1"
        )
    assert exc_clk.value.code == "invalid_clock"

    # Withdraw without earlier grant
    ledger_withdraw_first = ConsentLedger(clock=lambda: t0)
    ledger_withdraw_first.record(
        "s1", "marketing", "withdraw", "2026-01-01", source="web", event_id="e1"
    )
    st = ledger_withdraw_first.status("s1", "marketing")
    assert st.state == "withdrawn"

    # Status with invalid timezone in 'at'
    with pytest.raises(ConsentError) as exc_at:
        ledger.status("s1", "marketing", at=datetime(2026, 11, 6, 12, 0, 0))
    assert exc_at.value.code == "invalid_clock"

    # Microseconds in export
    t_micro = datetime(2026, 11, 6, 10, 0, 0, 123456, tzinfo=timezone.utc)
    ledger_micro = ConsentLedger(clock=lambda: t_micro)
    ledger_micro.record("s2", "terms", "grant", "2026-01-01", source="cli", event_id="e100")
    exp = ledger_micro.export("s2")
    parsed = json.loads(exp)
    assert parsed["events"][0]["recorded_at"] == "2026-11-06T10:00:00.123456Z"

    # Same timestamp two events (seq orders)
    t_fixed = datetime(2026, 11, 6, 10, 0, 0, tzinfo=timezone.utc)
    ledger_seq = ConsentLedger(clock=lambda: t_fixed)
    e_g = ledger_seq.record("s1", "marketing", "grant", "2026-01-01", source="web", event_id="e1")
    e_w = ledger_seq.record(
        "s1", "marketing", "withdraw", "2026-01-01", source="web", event_id="e2"
    )
    assert e_g.seq < e_w.seq
    assert ledger_seq.status("s1", "marketing").state == "withdrawn"

    # on_event callback throwing should not break record
    def crashing_callback(evt: LedgerEvent) -> None:
        raise ValueError("boom")

    ledger_crash_cb = ConsentLedger(clock=lambda: t_fixed, on_event=crashing_callback)
    ev = ledger_crash_cb.record(
        "s1", "marketing", "grant", "2026-01-01", source="web", event_id="e3"
    )
    assert ev.event_id == "e3"

    # InMemoryEventStore bad max_events
    with pytest.raises(ValueError):
        InMemoryEventStore(max_events=0)
