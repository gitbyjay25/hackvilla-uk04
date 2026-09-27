# Nexarch SDK - Python

Runtime architecture intelligence SDK for FastAPI applications.

## Installation

```bash
pip install nexarch-sdk
```

## Quick Start

```python
from fastapi import FastAPI
from nexarch import NexarchSDK

app = FastAPI(title="My API")

sdk = NexarchSDK(
    api_key="your_api_key_here",
    environment="production",
    service_name="orders-api",
    project_name="checkout-platform",
    http_endpoint="https://api.modelix.world",
)
sdk.init(app)
```

## What Gets Captured

- Incoming HTTP spans with latency and status code
- Unhandled errors with trace context
- Downstream dependency hints (HTTP/database)
- Architecture discovery snapshots (service endpoints, dependencies)

## Data Export Model

- Telemetry is exported remotely to Nexarch ingest APIs.
- Internal `/__nexarch/*` telemetry endpoints are no longer injected.
- Local JSON telemetry logging is no longer part of the SDK runtime path.

## Configuration

```python
sdk = NexarchSDK(
    api_key="your_api_key",               # required
    environment="production",             # optional
    service_name="payments-api",          # optional
    project_name="checkout-platform",     # optional, defaults to service_name
    http_endpoint="https://api.modelix.world",  # optional (or NEXARCH_HTTP_ENDPOINT)
    sampling_rate=1.0,                     # optional: 0.0 - 1.0
    enable_auto_discovery=True,            # optional
    enable_db_instrumentation=True,        # optional
)
```

## Notes

- `project_name` is sent with spans and discovery payloads for project-level analytics.
- Heartbeats are sent to `/api/v1/sdk/heartbeat`.
- Spans are sent to `/api/v1/ingest/spans` or `/api/v1/ingest/batch`.

## Security & Privacy

- No source code upload.
- Request/response bodies are not captured by default.
- Sensitive headers are sanitized.

## Development

```bash
pip install -e .
pytest
```
