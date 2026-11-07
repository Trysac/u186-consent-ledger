"""Behavior tests for the public API of consent_ledger."""

from __future__ import annotations

import pytest

import consent_ledger


def test_normalize_trims_and_lowercases() -> None:
    assert consent_ledger.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        consent_ledger.normalize(value)


def test_version_is_semver() -> None:
    parts = consent_ledger.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
