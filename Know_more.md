# Know More: Complete Nexarch Code Structure Guide

Last updated: 2026-04-03

## 1) What this repository is

Nexarch is an architecture-intelligence platform with 3 major codebases in one repo:

1. Backend platform (`Server/`): FastAPI APIs, auth, telemetry analysis, architecture generation, alpha-code pipeline, streaming, MCP tools.
2. Frontend app (`frontend/`): Next.js app for dashboard, system-architecture graph, alpha-code runs, auth/profile/admin/API-key management.
3. SDK package (`nexarch-sdk/`): Python runtime instrumentation SDK that captures HTTP/DB telemetry and exports it.

There are also root-level demo apps and smoke tests to validate full end-to-end flows.


## 2) End-to-end system flow (what happens in production)

### Flow A: Runtime telemetry
1. A customer app installs `nexarch-sdk` and initializes `NexarchSDK`.
2. SDK middleware and patches capture inbound requests and outbound HTTP/DB spans.
3. SDK exports telemetry (local JSON and/or HTTP batch export) to backend ingest endpoints.
4. Backend stores spans in DB by tenant.
5. Services build dependency graph, compute metrics, detect issues, and generate recommendations/workflows.

Why this exists:
- You do not need source-code access in the platform to understand runtime behavior.

### Flow B: Dashboard analytics
1. Frontend calls dashboard APIs.
2. Backend composes graph + metrics + issues + trends + AI insights.
3. Cache layer serves repeated requests fast.
4. WebSocket stream pushes live updates (Pathway where supported; DB polling fallback otherwise).

Why this exists:
- Architecture observability must feel real-time, not static snapshots.

### Flow C: System architecture generation from repository
1. User connects GitHub App installation and repository.
2. Backend snapshots repo (local path or remote clone/archive), performs static analysis, fuses runtime signals.
3. Backend writes architecture docs (`architecture_<key>.md/.json`) and a 2D graph JSON.
4. Backend generates 3 architecture variants (GPT-5 path with fallback templates).

Why this exists:
- Runtime-only and static-only each miss context; fusion gives better architecture decisions.

### Flow D: Alpha-code pipeline
1. User selects variant and runs `plan-deeply`.
2. Backend writes deep plan artifacts.
3. User starts alpha run.
4. Backend copies immutable snapshot into isolated workspace, runs parallel planning pipeline, executes transforms, runs tests, builds artifact zip.
5. Run status and downloadable ZIP are exposed by APIs and surfaced in frontend.

Why this exists:
- Architecture recommendations are useful, but teams need implementation artifacts, not just diagrams.


## 3) Top-level repository structure

## Root files and folders

- `README.md`
  - Kind: Product + onboarding documentation.
  - Does: Explains platform vision, workflow, and usage.
  - Why: Gives business/technical context to new contributors.

- `API_DOCUMENTATION.md`
  - Kind: API reference.
  - Does: Documents auth flow and endpoint contracts.
  - Why: Frontend/client integration baseline.

- `API_KEY_GUIDE.md`
  - Kind: Integration/security guide.
  - Does: Shows API key generation/use and security practices.
  - Why: SDK and external clients need operational guidance.

- `sys_arch.md`
  - Kind: Architecture expansion blueprint.
  - Does: Records planned system-architecture/alpha-code design decisions.
  - Why: Product and engineering alignment artifact.

- `start.py`
  - Kind: Multi-server launcher script.
  - Does: Spawns FastAPI and MCP servers in separate PowerShell consoles; status checks.
  - Why: Faster local startup for full stack dev.

- `start_mcp.py`
  - Kind: MCP launcher script.
  - Does: Loads env, starts FastMCP with stdio/SSE/HTTP transport modes.
  - Why: Enables Claude/Desktop or web-client MCP workflows.

- `blog_generator_backend.py`
  - Kind: Demo FastAPI application.
  - Does: Runs blog-generation endpoints using Azure OpenAI fallback logic, instrumented by SDK.
  - Why: Deterministic smoke target for SDK + backend flow testing.

- `blog_generator_telemetry.json`, `sdk_smoke_telemetry.json`, `blog_generator_telemetry.json`
  - Kind: Generated telemetry artifacts.
  - Does: Store captured events from local smoke/demo runs.
  - Why: Local verification and debugging.

- `test_blog_generator_backend.py`
  - Kind: Smoke test script.
  - Does: Validates demo backend endpoints and SDK internal telemetry endpoints.
  - Why: Ensures demo/backend basic health before deeper integration tests.

- `test_blog_to_nexarch_flow.py`
  - Kind: End-to-end integration script.
  - Does: Authenticates to Nexarch backend, generates API key, starts demo backend, emits telemetry, verifies backend insights endpoints.
  - Why: Validates full external customer journey.

- `test_sdk_smoke.py`
  - Kind: SDK smoke test script.
  - Does: Initializes SDK in FastAPI test app and verifies telemetry/logging behavior.
  - Why: Quick confidence check for packaged SDK behavior.

- `notes`
  - Kind: Local note file.
  - Does: Currently whitespace/empty.
  - Why: Scratchpad placeholder.

- `frontend/`
  - Kind: Next.js frontend app.
  - Why: User-facing product UI.

- `Server/`
  - Kind: Backend platform.
  - Why: Core APIs, analysis, auth, data, generation, streaming.

- `nexarch-sdk/`
  - Kind: Python SDK package.
  - Why: Runtime telemetry capture inside customer services.


## 4) Backend deep map (`Server/`)

### 4.1 Entry and app wiring

- `Server/main.py`
  - Kind: FastAPI app entrypoint and lifecycle wiring.
  - Does:
    - Initializes logging, cache, DB, migrations.
    - Starts streaming pipeline + fallback if Pathway unavailable.
    - Registers all API routers and WebSocket router.
    - Enforces production safety for default JWT secret.
  - Why: Single composition root for all backend concerns.

- `Server/start.sh`, `Server/start.ps1`
  - Kind: Startup helpers.
  - Does: Convenience scripts to run backend in shell-specific environments.
  - Why: Better local operational ergonomics.

- `Server/pytest.ini`
  - Kind: Pytest config.
  - Does: Declares integration marker.
  - Why: Separates live-API tests from unit/smoke tests.


### 4.2 API layer (`Server/api/`)

- `Server/api/health.py`
  - Kind: Health and heartbeat endpoints.
  - Does: Basic/detailed health, k8s-ready probes, SDK heartbeat ingestion.
  - Why: Operations visibility and liveness/readiness compatibility.

- `Server/api/auth.py`
  - Kind: Authentication controller.
  - Does: Email/password signup/login, Google OAuth URLs/callback/signin, profile update, token debug/status.
  - Why: Multi-channel user auth for frontend and user management.

- `Server/api/api_keys.py`
  - Kind: User API key management endpoints.
  - Does: Create/list/revoke tenant API keys.
  - Why: SDK and machine clients authenticate via `X-API-Key`.

- `Server/api/admin.py`
  - Kind: Admin-only tenant management.
  - Does: Create/update/list/deactivate tenants and tenant API key management.
  - Why: Multi-tenant lifecycle control.

- `Server/api/cache_api.py`
  - Kind: Cache operations endpoints.
  - Does: Stats, invalidate (tenant/operation), warm-on-next-request, health/info.
  - Why: Operational control over performance layer.

- `Server/api/system.py`
  - Kind: System information and stats.
  - Does: Capabilities, tenant/system stats, endpoint discovery metadata.
  - Why: Platform observability and diagnostics for users/admins.

- `Server/api/dashboard.py`
  - Kind: Aggregator router.
  - Does: Mounts overview/trends/insights subrouters under `/api/v1/dashboard`.
  - Why: Keeps dashboard API structure modular.

- `Server/api/dashboard_overview.py`
  - Kind: Dashboard analytics endpoints.
  - Does: Overview, architecture map, services, health scoring, dependencies, bottlenecks.
  - Why: Main operational surface for architecture health and topology.

- `Server/api/dashboard_trends.py`
  - Kind: Time-series endpoints.
  - Does: Hourly bucketed latency/error/volume trends and trace timeline alias.
  - Why: Trend analysis is distinct from snapshots.

- `Server/api/dashboard_insights.py`
  - Kind: AI + recommendation endpoints.
  - Does: Insights, architecture recommendations, workflow alternatives.
  - Why: Converts raw telemetry into action-oriented decisions.

- `Server/api/system_architecture.py`
  - Kind: Repository analysis and variant generation APIs.
  - Does:
    - GitHub install/repo connect/snapshot management.
    - Static + runtime fused architecture documents.
    - 2D graph JSON generation.
    - Sync/async variant generation with mode heuristics.
  - Why: Product core for architecture redesign from real repos.

- `Server/api/alpha_code.py`
  - Kind: Alpha-code orchestration APIs.
  - Does: Deep planning, run creation/list/status, artifact download.
  - Why: Bridges architecture planning to executable deliverables.


### 4.3 Core infrastructure (`Server/core/`)

- `Server/core/config.py`
  - Kind: Central settings model.
  - Does: Reads env for app, DB, Redis, AI, OAuth, GitHub App, SMTP, thresholds, CORS, feature flags.
  - Why: Strong configuration control and environment portability.

- `Server/core/cache.py`
  - Kind: Unified cache manager.
  - Does: Redis backend with in-memory fallback, tenant-keyed cache namespace, invalidation/stats.
  - Why: Performance and resilience even if Redis unavailable.

- `Server/core/rate_limit.py`
  - Kind: Middleware rate limiter.
  - Does: In-memory per-tenant request windows.
  - Why: Simple abuse protection baseline.

- `Server/core/security.py`
  - Kind: JWT/password utilities.
  - Does: Access tokens, verification, password hashing (argon2), reset token helpers.
  - Why: Core auth security primitives.

- `Server/core/auth.py`
  - Kind: API key auth dependency.
  - Does: Validates `X-API-Key`, resolves tenant context, checks active tenant, updates key usage timestamp.
  - Why: SDK and machine request authorization path.

- `Server/core/optional_auth.py`
  - Kind: Optional auth helper.
  - Does: Attempts API-key auth and returns `None` on failure/no key.
  - Why: Endpoints that can run with or without auth context.

- `Server/core/ai_client.py`
  - Kind: AI abstraction client.
  - Does: Gemini-first then Azure fallback, architecture recommendations, workflow generation, decision explainers, dashboard insights.
  - Why: Centralized AI behavior with fallback strategy.

- `Server/core/logging.py`
  - Kind: Logging setup.
  - Does: Configures format/levels and mutes noisy libraries.
  - Why: Consistent diagnostics across modules.


### 4.4 Data layer (`Server/db/`, `Server/models/`, `Server/Schemas/`, `Server/crud/`, `Server/dependencies/`)

- `Server/db/base.py`
  - Kind: SQLAlchemy setup and migration helpers.
  - Does: Engine/session/base creation plus SQLite compatibility column migrations.
  - Why: Stable persistence across evolving schema.

- `Server/db/models.py`
  - Kind: ORM models.
  - Does: Defines tenants/users/api keys/spans plus architecture-doc, variant, deep-plan, alpha-run entities and GitHub integration entities.
  - Why: Single source of truth for persisted platform state.

- `Server/models/span.py`, `node.py`, `edge.py`, `issue.py`, `workflow.py`, `workflow_graph.py`, `user.py`
  - Kind: Domain Pydantic models.
  - Does: In-memory API/service entities for telemetry graph, issues, workflows, workflow visual graphs, user/tenant abstractions.
  - Why: Strongly typed contracts between service and API layers.

- `Server/Schemas/ingest.py`, `architecture.py`, `workflow.py`, `token.py`, `user.py`
  - Kind: Request/response schemas.
  - Does: Validates incoming payloads and response structures.
  - Why: Input integrity and OpenAPI consistency.

- `Server/crud/user.py`
  - Kind: User persistence helpers.
  - Does: User lookup/create flows including Google-user upsert and tenant bootstrap.
  - Why: Keeps route logic thin and data logic reusable.

- `Server/dependencies/auth.py`
  - Kind: FastAPI dependencies.
  - Does: Resolves user and tenant from JWT/API key and supports mixed auth mode.
  - Why: Shared auth policy across endpoints.


### 4.5 Service layer (`Server/services/`)

- `Server/services/ingest_service.py`
  - Kind: Telemetry persistence service.
  - Does: Stores spans (single or batched) in DB.
  - Why: Encapsulates ingestion write path.

- `Server/services/graph_service.py`
  - Kind: Graph builder service.
  - Does: Builds node/edge models and NetworkX graph from spans.
  - Why: Canonical topology construction for all downstream analyses.

- `Server/services/metrics_service.py`
  - Kind: Aggregation service.
  - Does: Node/edge/global SQL aggregate metrics.
  - Why: Efficient analytics without full-table Python scans.

- `Server/services/issue_detector.py`
  - Kind: Issue detection orchestrator.
  - Does: Runs deterministic rules and optional AI enhancement.
  - Why: Combines precision and heuristic intelligence.

- `Server/services/workflow_generator.py`
  - Kind: Workflow generation orchestrator.
  - Does: LangGraph base workflows + optional AI alternatives.
  - Why: Produces practical architecture change options.

- `Server/services/workflow_graph_service.py`
  - Kind: Graph presentation service.
  - Does: Builds current workflow graph + generated variants formatted for visual frontend usage.
  - Why: Read-only graph products for UX-centric architecture exploration.

- `Server/services/ai_architecture_designer.py`
  - Kind: High-level architecture design service.
  - Does: New architecture generation, decomposition, event-driven design, optimization strategies.
  - Why: Expands beyond reactive troubleshooting to proactive design.

- `Server/services/github_app_service.py`
  - Kind: GitHub App integration service.
  - Does: JWT signing, installation token exchange, repo listing, metadata fetch.
  - Why: Secure repo connectivity for static analysis.

- `Server/services/notification_service.py`
  - Kind: Email notification utility.
  - Does: SMTP notifications for alpha run completion/failure with auth-fail suppression.
  - Why: Async run lifecycle needs user alerts.


### 4.6 Reasoning layer (`Server/reasoning/`)

- `Server/reasoning/rules.py`
  - Kind: Deterministic rule engine.
  - Does: Detects high latency, deep chain, high error, fan-out, SPOF issues.
  - Why: Transparent baseline analysis independent of LLMs.

- `Server/reasoning/graph_analysis.py`
  - Kind: Graph algorithm utility.
  - Does: Critical paths, centrality/bottlenecks, cycles, DAG checks.
  - Why: Structural risk/performance interpretation.

- `Server/reasoning/langgraph_pipeline.py`
  - Kind: Non-linear reasoning pipeline.
  - Does: Issue detection/classification + parallel generation of minimal/performance/cost workflows with fan-in finalize.
  - Why: Structured multi-strategy decision making.

- `Server/reasoning/alpha_codegen_pipeline.py`
  - Kind: Alpha generation planning pipeline.
  - Does: Inventory/dependency/risk/step synthesis + quality gates.
  - Why: Guarantees planning rigor before code artifact generation.


### 4.7 Streaming layer (`Server/streaming/`)

- `Server/streaming/pipeline.py`
  - Kind: Real-time stream orchestrator.
  - Does: Runs Pathway pipeline thread when available; exposes push/status APIs.
  - Why: Low-latency telemetry-to-UI signal path.

- `Server/streaming/websocket.py`
  - Kind: WebSocket manager and `/api/v1/stream/live` endpoint.
  - Does: Manages per-tenant socket connections, queued thread-safe broadcasts.
  - Why: Real-time dashboard updates and issue alerts.

- `Server/streaming/polling_fallback.py`
  - Kind: Windows/no-Pathway fallback broadcaster.
  - Does: Polls DB periodically and broadcasts computed metrics.
  - Why: Cross-platform real-time behavior parity.

- `Server/streaming/connectors.py`
  - Kind: Pathway connectors and Redis output writer.
  - Does: Accepts span pushes and writes metric snapshots to Redis.
  - Why: Decouple stream ingestion/output mechanics from pipeline logic.

- `Server/streaming/transforms/graph_builder.py`
  - Kind: Pathway transform.
  - Does: Builds node and edge tables from stream.
  - Why: Incremental graph state for real-time operations.

- `Server/streaming/transforms/metrics.py`
  - Kind: Pathway transform.
  - Does: Sliding-window metrics (5m/1h/24h).
  - Why: Multi-scale trend and alert support.

- `Server/streaming/transforms/issue_rules.py`
  - Kind: Pathway transform.
  - Does: Reactive issue detection from streaming windows.
  - Why: Immediate alerting from live telemetry.


### 4.8 MCP integration (`Server/mcp_server/`)

- `Server/mcp_server/server.py`
  - Kind: FastMCP server definition.
  - Does: Registers MCP tools (`get_current_architecture`, `get_detected_issues`, workflows, comparisons, explanations, graph analysis).
  - Why: AI-agent tooling interface over backend capabilities.

- `Server/mcp_server/tools.py`
  - Kind: MCP tool implementations.
  - Does: Thin service wrappers with tenant scoping, ranking logic, insights/recommendations.
  - Why: Reusable machine interface without duplicating business logic.


### 4.9 Utilities (`Server/utils/`)

- `Server/utils/google_oauth.py`
  - Kind: OAuth client helper.
  - Does: Authorization URL generation, code exchange, user-info fetch.
  - Why: Keeps OAuth protocol details isolated from route handlers.

- `Server/utils/redis_client.py`
  - Kind: Cache helper (legacy-style utility).
  - Does: Attempts cache key delete through cache manager.
  - Why: Utility convenience; appears partially stale against current cache API.

- `Server/utils/ai_client.py`
  - Kind: Separate/legacy AI utility.
  - Does: Gemini/Azure client fallback and domain-specific prompt execution.
  - Why: Legacy or separate experiment path; backend mainly uses `core/ai_client.py`.


### 4.10 Tests (`Server/test_*.py`, `Server/tests/*.py`)

Coverage themes:

- Auth and config checks:
  - `Server/test_auth.py`, `Server/test_config.py`

- End-to-end and integration:
  - `Server/tests/test_e2e.py`, `test_e2e_complete.py`, `test_integration_suite.py`, `test_comprehensive.py`, `test_complete_implementation.py`

- System architecture + alpha pipeline:
  - `Server/tests/test_system_arch_alpha_integration.py`, `_sysarch_alpha_smoke.py`, `_endpoint_smoke.py`

- MCP and LangChain checks:
  - `Server/tests/test_mcp.py`, `test_mcp_server.py`, `test_langchain.py`

- Redis and scalability:
  - `Server/tests/test_redis.py`, `test_redis_quick.py`, `test_azure_redis.py`, `test_scalability.py`

- Workflow graph endpoint:
  - `Server/tests/test_workflow_graph.py`

Why this suite exists:
- The platform has many integration seams (auth, DB, cache, AI, streaming, repo analysis), so validation is broad and integration-heavy.


## 5) SDK deep map (`nexarch-sdk/`)

### 5.1 Package metadata and entry

- `nexarch-sdk/pyproject.toml`, `setup.py`, `MANIFEST.in`
  - Kind: Packaging/build metadata.
  - Why: Publish/install SDK as a Python distribution.

- `nexarch-sdk/nexarch/__init__.py`
  - Kind: Public package API.
  - Does: Exposes `NexarchSDK`, middleware, models, discovery types.
  - Why: Clean import surface for users.


### 5.2 SDK runtime core

- `nexarch-sdk/nexarch/client.py`
  - Kind: SDK orchestrator class.
  - Does: Configures logger/exporter/queue, patches HTTP+DB instrumentation, injects middleware/router, sends periodic heartbeat.
  - Why: One object to bootstrap all SDK behavior.

- `nexarch-sdk/nexarch/middleware.py`
  - Kind: Request interception middleware.
  - Does: Creates server spans, captures errors, tracks downstream deps and latency breakdown, emits telemetry and optional auto-discovery records.
  - Why: Central point for inbound request observability.

- `nexarch-sdk/nexarch/router.py`
  - Kind: Internal debug endpoints.
  - Does: Health, telemetry retrieval, stats, clear, error/span subsets.
  - Why: Local debugging and smoke verification.

- `nexarch-sdk/nexarch/queue.py`
  - Kind: Async-safe background queue.
  - Does: Buffered enqueue + batch export + flush/shutdown.
  - Why: Avoids synchronous export latency in request path.

- `nexarch-sdk/nexarch/loggers.py`
  - Kind: Local JSON logger.
  - Does: Thread-safe append/get/clear for local telemetry logs.
  - Why: Offline/local-first observability option.

- `nexarch-sdk/nexarch/models.py`
  - Kind: SDK event dataclasses.
  - Does: Span/error/metric payload structures.
  - Why: Structured serialization contracts.

- `nexarch-sdk/nexarch/utils.py`
  - Kind: Utilities.
  - Does: Header sanitization, path patterning, byte formatting, endpoint traceability filter.
  - Why: Reusable safety and normalization helpers.


### 5.3 Tracing internals (`nexarch-sdk/nexarch/tracing/`)

- `context.py`: contextvars propagation and downstream latency accumulation.
- `span.py`: span model and finish/latency computation.
- `sampler.py`: probabilistic sampling decisions.
- `__init__.py`: re-exports tracing primitives.

Why:
- Distributed tracing requires context propagation and controllable overhead.


### 5.4 Instrumentation patches (`nexarch-sdk/nexarch/instrumentation/`)

- `requests_patch.py`
  - Does: Monkey-patches `requests` to create client spans.

- `httpx_patch.py`
  - Does: Monkey-patches sync/async `httpx` clients for client spans.

- `db_patch.py`
  - Does: Instruments SQLAlchemy, Redis, and PyMongo operations; sanitizes SQL literals.

- `__init__.py`
  - Does: Aggregates patch functions.

Why:
- Captures downstream dependencies automatically with minimal user code changes.


### 5.5 Exporters (`nexarch-sdk/nexarch/exporters/`)

- `base.py`
  - Kind: Abstract exporter contract.

- `http.py`
  - Kind: HTTP exporter.
  - Does: Batch sends, retry/backoff, dead-letter queue.

- `local_json.py`
  - Kind: Local file exporter.
  - Does: Appends telemetry into JSON log file.

- `__init__.py`
  - Kind: Export re-exports.

Why:
- Supports both online backend export and offline local capture.


### 5.6 Auto-discovery (`nexarch-sdk/nexarch/auto_discovery.py`)

- Kind: Runtime architecture introspection.
- Does: Endpoint, DB, dependency, middleware pattern detection plus traffic/dependency analyzers.
- Why: Adds architectural metadata beyond raw span timing.


### 5.7 SDK tests

- `nexarch-sdk/tests/test_sdk.py`
  - Kind: Basic SDK unit tests.
  - Does: Validates initialization, FastAPI injection, sampling clamp behavior.
  - Why: Guards package fundamentals.


## 6) Frontend deep map (`frontend/`)

### 6.1 App framework and config

- `frontend/package.json`
  - Kind: Node package manifest.
  - Does: Next dev/build/start scripts and dependencies (`next`, `react`, `@xyflow/react`, etc.).
  - Why: Frontend runtime/build setup.

- `frontend/next.config.js`
  - Kind: Next config.
  - Does: strict mode, standalone output, compression, turbopack root.
  - Why: Production and local build behavior.

- `frontend/jsconfig.json`
  - Kind: JS tooling config.
  - Does: alias `@/*` and include/exclude patterns.
  - Why: Cleaner imports and editor support.

- `frontend/src/app/globals.css`
  - Kind: Global design system.
  - Does: Defines retro-future visual tokens/components/layout styles.
  - Why: Unified look and behavior across pages.


### 6.2 App routes (`frontend/src/app/`)

- `layout.js`
  - Kind: Root layout.
  - Does: global fonts, metadata, wraps app in `AuthProvider`.
  - Why: common shell and auth context.

- `page.js`
  - Kind: Landing page composition.
  - Does: assembles `Navbar`, `Hero`, `Features`, `CTASection`, `Footer`.
  - Why: marketing entry experience.

- `login/page.js`, `signup/page.js`, `auth/callback/page.js`
  - Kind: Auth UX routes.
  - Does: email/password and Google OAuth flow handling and callback token/code processing.
  - Why: secure account onboarding and sign-in.

- `dashboard/page.js`, `dashboard/loading.js`
  - Kind: Main operations dashboard.
  - Does: loads overview/services/trends/insights/recommendations, displays health cards and analytics.
  - Why: core product visibility panel.

- `system-architecture/page.js`
  - Kind: Architecture graph and variant UX.
  - Does: graph normalization/layout, variant impact graph construction, interactive rendering via React Flow.
  - Why: visual decision support for architecture redesign.

- `alpha-code/page.js`
  - Kind: Alpha run control panel.
  - Does: triggers deep plan and runs, lists run status, handles secure artifact download via proxy route.
  - Why: user-facing execution lifecycle control.

- `api-keys/page.js`
  - Kind: API key management page.
  - Does: wraps `ApiKeyManager` and auth gating.
  - Why: key lifecycle for SDK authentication.

- `profile/page.js`
  - Kind: Account + GitHub linking page.
  - Does: profile updates and GitHub installation linking/refresh.
  - Why: personal settings and repo integration setup.

- `settings/page.js`
  - Kind: operational settings page.
  - Does: cache stats/actions and demo-data utilities.
  - Why: environment tuning and admin-like maintenance.

- `admin/page.js`
  - Kind: tenant admin panel.
  - Does: tenant CRUD and plan/status/settings UI.
  - Why: multi-tenant management UI.

- `api/alpha-code/runs/[runId]/download/route.js`
  - Kind: Next.js server route proxy.
  - Does: forwards authenticated artifact download from backend and streams ZIP response.
  - Why: secure browser-friendly download flow.


### 6.3 Frontend lib (`frontend/src/lib/`)

- `auth-context.js`
  - Kind: React auth state provider.
  - Does: login/signup/logout/checkAuth, profile updates, state persistence behavior.
  - Why: shared client-side auth state across app.

- `api-client.js`
  - Kind: API facade.
  - Does: backward-compatible `NexarchClient` that re-exports modular API domains.
  - Why: migration-safe API access layer.

- `stream-client.js`
  - Kind: Realtime hook.
  - Does: WebSocket connect/reconnect/heartbeat and live metrics/issues state.
  - Why: live UX updates in components.

- `api/auth.js`
  - Kind: auth API module.
  - Does: token storage + base request wrapper + auth endpoints.
  - Why: low-level auth request abstraction.

- `api/dashboard.js`
  - Kind: dashboard API module.
  - Does: dashboard endpoint calls.
  - Why: route-level API grouping.

- `api/admin.js`
  - Kind: system/admin/cache/API-key API module.
  - Does: health/system/admin/cache/api-key calls.
  - Why: operational/admin call surface.

- `api/system-architecture.js`
  - Kind: system-architecture API module.
  - Does: GitHub install/link, repo connect/snapshot/analyze, variants/documents/graph calls.
  - Why: repository-driven architecture feature integration.

- `api/alpha-code.js`
  - Kind: alpha-code API module.
  - Does: deep plan/run/list/get/download helpers with proxy fallback.
  - Why: complete alpha run lifecycle actions.


### 6.4 Components (`frontend/src/components/`)

- `Navbar.js`: auth-aware navigation and logout.
- `Hero.js`: landing hero section.
- `Features.js`: feature grid content.
- `CTASection.js`: call-to-action block.
- `Footer.js`: site footer.
- `ApiKeyManager.js`: full API-key CRUD UI (create/copy/revoke/instructions).
- `LiveStreamBadge.js`: realtime stream status pill.
- `Skeleton.js`: reusable loading skeleton components.
- `ErrorBoundary.js`: per-section render failure isolation.

Why:
- Keeps page files focused on composition and business flow instead of view primitives.


## 7) Known architectural patterns in this codebase

1. Router thinness:
- Most heavy logic is delegated to services/reasoning modules.

2. Multi-tenant scoping:
- `tenant_id` consistently carried through auth, DB, cache, and API operations.

3. Deterministic + AI hybrid:
- Rule engines and graph algorithms provide stable baselines.
- AI layers add optimization/recommendation richness.

4. Async mode gating:
- Expensive variant/alpha flows support sync/async mode with heuristics.

5. Cross-platform streaming fallback:
- Pathway pipeline where available; DB polling fallback (important for Windows).

6. Isolation-first alpha execution:
- Immutable snapshot source, copied workspace execution, artifact-only output.


## 8) Important design rationale (the "why" behind major modules)

1. Why both static and runtime architecture analysis:
- Runtime shows truth of execution paths.
- Static shows latent structure/dependencies and missing runtime coverage.

2. Why architecture variants are exactly 3:
- Product decision to keep decision space understandable (cost/scalability/performance axes).

3. Why alpha-code run produces many report artifacts:
- Auditability and reproducibility for generated code changes.

4. Why SDK has local JSON and HTTP exporters:
- Works in disconnected/dev contexts and production SaaS contexts.

5. Why frontend has API proxy route for alpha ZIP:
- Browser-friendly secure download without exposing token in URL unnecessarily.


## 9) Practical dependency map by purpose

1. Platform/API runtime:
- FastAPI, SQLAlchemy, NetworkX, Pydantic, LangGraph, FastMCP, Redis client.

2. AI integration:
- Azure OpenAI via LangChain wrappers, optional Gemini fallback.

3. Frontend:
- Next.js, React, React Flow (`@xyflow/react`), Lucide icons.

4. SDK instrumentation:
- FastAPI/Starlette middleware model, `requests`, `httpx`, SQLAlchemy/Redis/PyMongo patch points.


## 10) Quick orientation for contributors

If you need to change...

1. API behavior: start in `Server/api/*`, then corresponding `Server/services/*`.
2. Metrics/graph logic: `Server/services/graph_service.py`, `Server/services/metrics_service.py`, `Server/reasoning/*`.
3. Auth/security: `Server/api/auth.py`, `Server/core/security.py`, `Server/dependencies/auth.py`.
4. Repo analysis/variants: `Server/api/system_architecture.py` (+ GitHub service).
5. Alpha generation: `Server/api/alpha_code.py`, `Server/reasoning/alpha_codegen_pipeline.py`.
6. Realtime streaming: `Server/streaming/*` and frontend `src/lib/stream-client.js`.
7. SDK capture/export: `nexarch-sdk/nexarch/client.py`, `middleware.py`, `instrumentation/*`, `exporters/*`.
8. Frontend dashboard pages: `frontend/src/app/dashboard/page.js` and `frontend/src/lib/api/dashboard.js`.
9. System architecture UI graph: `frontend/src/app/system-architecture/page.js`.


## 11) Mismatch notes to keep in mind

1. Some docs mention endpoints and SDK variants not fully aligned with current code paths.
2. `Server/utils/ai_client.py` appears legacy relative to `Server/core/ai_client.py` and should be treated carefully.
3. `Server/utils/redis_client.py` uses an async call pattern that may not match current cache manager API.
4. `frontend/src/app/signup/page.js` references `Chrome` icon but imports `Globe` instead; this likely causes a runtime UI error unless fixed.


## 12) Final summary

This repository is a full-stack architecture intelligence platform, not just an API service.
Its strongest design characteristics are:

1. Runtime observability + static repository intelligence fusion.
2. Tenant-aware architecture analytics and recommendation generation.
3. Deep planning and alpha-code artifact pipeline from architecture variants.
4. A separately distributable SDK that auto-captures operational telemetry.
5. A Next.js UI that exposes all major product workflows (auth, dashboards, architecture redesign, alpha execution).

If you want, I can generate a second document that is even more literal and machine-like: a strict file inventory table with one row per source file (`path`, `language`, `kind`, `inputs`, `outputs`, `depends_on`, `used_by`).
