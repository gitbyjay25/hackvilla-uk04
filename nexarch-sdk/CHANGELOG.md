# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-04-03

### Changed
- Packaging-only patch release to publish a new PyPI filename after 0.2.0 filename reuse lock.

## [0.3.0] - 2026-03-01

### Added
- Downstream ms tracking via `ContextVar` — `add_downstream_ms()` / `get_downstream_ms()` in `nexarch.tracing`
- `db_patch.py`: SQLAlchemy, Redis, and MongoDB patches now record downstream latency into tracing context
- `requests_patch.py`: Records `latency_ms` and `http_latency` in span data; reports downstream ms to context
- `httpx_patch.py`: Records `latency_ms` and `http_latency` for both sync and async HTTP calls

### Fixed
- `middleware.py`: `downstream_ms` now correctly reads from tracing context instead of `span_tags`
- `exporters/http.py`: Wrapped `resp.json()` in `try/except ValueError` to prevent `JSONDecodeError` from bypassing DLQ
- `db_patch.py`: Added idempotency guards (`_redis_is_patched`, `_pymongo_is_patched`) — patching is now safe to call multiple times
- `tracing/context.py`: `set_trace_context` and `clear_trace_context` now reset the downstream ms accumulator

## [0.2.0] - 2026-01-17

### Changed
- Reorganized package structure from `SDK/python` to `nexarch-sdk/nexarch`
- Improved import path: now use `from nexarch import NexarchSDK`
- Updated package configuration in pyproject.toml

### Fixed
- Fixed incomplete README path in pyproject.toml
- Added thread-safe lock for architecture discovery
- Fixed potential KeyError when accessing span tags
- Added input validation for sampling_rate
- Improved error handling in database instrumentation
- Added better exception handling in loggers
- Fixed potential datetime parsing errors in span finish method

### Added
- Added LICENSE file (MIT)
- Added setup.py for better compatibility
- Added MANIFEST.in for package distribution
- Added py.typed marker for PEP 561 compliance
- Added comprehensive .gitignore
- Added CONTRIBUTING.md
- Added this CHANGELOG.md

## [0.1.0] - 2026-01-10

### Added
- Initial release of Nexarch SDK
- FastAPI middleware for automatic instrumentation
- Architecture auto-discovery
- Database instrumentation (SQLAlchemy, MongoDB, Redis)
- HTTP client instrumentation (requests, httpx)
- Local JSON logging
- HTTP export to backend
- Distributed tracing support
- Telemetry endpoints
