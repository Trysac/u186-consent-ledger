# consent-ledger

[![PyPI version](https://img.shields.io/pypi/v/trysac-consent-ledger)](https://pypi.org/project/trysac-consent-ledger/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-consent-ledger)](LICENSE)
[![CI](https://github.com/Trysac/u186-consent-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u186-consent-ledger/actions/workflows/ci.yml)

Append-only consent records per subject and purpose with policy versions, point-in-time status, stale consent detection, idempotent events and JSON export

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-consent-ledger
# or
uv add trysac-consent-ledger
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import consent_ledger

# normalize() trims surrounding whitespace and lower-cases the text.
print(consent_ledger.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    consent_ledger.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
