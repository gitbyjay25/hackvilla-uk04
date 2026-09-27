# Nexarch System Architecture Expansion Plan

## 1. Objective
Build a production-grade capability in Nexarch that combines:
- Runtime telemetry from SDK
- Mandatory static repository analysis from connected GitHub repositories
- AI-driven architecture documentation and optimization
- Alpha code generation with deep planning gates
- Downloadable alpha output package (zip)

This plan is aligned to your confirmed constraints and is intended as the implementation blueprint.

## 2. Confirmed Product Decisions

### 2.1 Repository Integration
- Integration method: GitHub App (installation-based)
- Private repositories: allowed
- Repo shape target: monorepos first

### 2.2 Analysis and Documentation
- Architecture document output: Markdown + JSON
- Naming convention: architecture_{unique_key}
- System architecture preference: fuse runtime telemetry and static repo analysis
- Runtime telemetry usage: preferred when available
- Static repo analysis usage: mandatory always

### 2.3 Optimization Controls
- Architecture objective sliders: cost, scalability, performance
- Weight behavior: auto-normalize to 100%
- Default weights:
  - cost = 30
  - scalability = 35
  - performance = 35

### 2.4 AI Generation
- Model family: Azure OpenAI GPT-5
- Output variants: 3 alternative architectures
- Selection input: normalized weights + architecture context document + runtime graph

### 2.5 Alpha Code Delivery
- "Plan Deeply" must run first and produce full technical report before code generation
- "Make Alpha Codebase" rewrites copied full codebase deeply based on selected architecture
- Must run tests and quality checks as part of generation pipeline
- Delivery type: zip only

### 2.6 Notifications
- Email transport: SMTP
- .env must include dummy SMTP variables for replacement

## 3. Target User Journey

### 3.1 Connect and Analyze
1. User opens project in Nexarch.
2. User installs GitHub App for selected org/repo.
3. User selects monorepo and branch.
4. Nexarch creates immutable repo snapshot record.
5. Static analysis pipeline runs and creates architecture_{unique_key}.md + .json.
6. Runtime telemetry (if present) is fused into architecture view.

### 3.2 System-Architecture Experience
1. User opens new System-Architecture page.
2. Current architecture graph shown (fused static + runtime).
3. User adjusts sliders (cost/scalability/performance).
4. User clicks Generate 3 Architectures.
5. Three architecture options displayed with graph + tradeoffs + expected impacts.
6. Each option provides:
   - Plan Deeply
   - Make Alpha Codebase

### 3.3 Planning and Code Generation
1. User clicks Plan Deeply.
2. System generates deep technical report artifact.
3. User reviews report and confirms.
4. User clicks Make Alpha Codebase.
5. System copies repo snapshot into tenant project workspace and rewrites code.
6. System runs test suite and quality checks.
7. Status shown on Alpha-Code page (pending/progress/completed/failed).
8. On completion, user receives email and can download zip.

## 4. High-Level Architecture

### 4.1 New Logical Services
1. github_app_service
- GitHub App auth, installation token exchange, repository listing, webhook verification.

2. repo_snapshot_service
- Clone/fetch repository snapshot by install token.
- Monorepo-aware path map and metadata extraction.

3. static_analysis_service
- Language/framework detection
- Dependency extraction
- DB schema detection
- API surface extraction
- Architecture pattern extraction

4. architecture_doc_service
- Builds architecture_{unique_key}.md and architecture_{unique_key}.json
- Versioned and immutable by snapshot id

5. architecture_fusion_service
- Fuses static architecture model with runtime telemetry graph
- Produces confidence-annotated unified graph

6. architecture_optimizer_service
- Accepts fused context + slider weights
- Generates 3 architecture variants via GPT-5
- Applies strict schema validation + rule checks

7. deep_plan_service
- Produces technical report for selected variant
- Includes migration, dependencies, folder strategy, rollout and risks

8. alpha_codegen_service
- Copies snapshot into workspace
- Applies architecture-driven transformation plan
- Runs tests/lint/build
- Produces zip artifact

9. notification_service
- Sends completion/failure emails via SMTP

### 4.2 New Async Job Workers
- github_sync_job
- static_analysis_job
- architecture_doc_job
- architecture_generation_job
- deep_plan_job
- alpha_codegen_job
- notification_job

All long-running work must be asynchronous and resumable.

## 5. Data Model Plan (Server DB)

### 5.1 Tables to Add
1. github_installations
- id, tenant_id, github_installation_id, account_login, created_at, updated_at

2. connected_repositories
- id, tenant_id, installation_id, owner, repo_name, default_branch, private, active

3. repo_snapshots
- id, tenant_id, repository_id, commit_sha, branch, snapshot_path, created_at, status

4. architecture_documents
- id, tenant_id, repository_id, snapshot_id, unique_key, markdown_path, json_path, created_at

5. architecture_variants
- id, tenant_id, architecture_doc_id, variant_index, weights_json, variant_json, created_at

6. deep_plan_reports
- id, tenant_id, architecture_variant_id, report_markdown_path, report_json_path, created_at

7. alpha_codegen_runs
- id, tenant_id, repository_id, snapshot_id, architecture_variant_id, status,
  workspace_path, zip_path, test_summary_json, started_at, ended_at, error_message

8. alpha_codegen_logs
- id, run_id, ts, level, message

9. email_notifications
- id, tenant_id, run_id, recipient_email, type, status, sent_at, error_message

### 5.2 Tenancy and Isolation
- Every table row scoped by tenant_id.
- Filesystem workspace root must be tenant-scoped and run-scoped.

## 6. Filesystem Workspace Layout

Workspace root convention:
- storage/{tenant_id}/{project_id}/{run_id}/

Contents:
- snapshot/
- architecture_docs/
  - architecture_{unique_key}.md
  - architecture_{unique_key}.json
- deep_plan/
  - deep_plan_{variant_id}.md
  - deep_plan_{variant_id}.json
- alpha_code/
  - full rewritten codebase
- artifacts/
  - alpha_code_{run_id}.zip
- logs/
  - run.log

## 7. API Surface Plan

### 7.1 GitHub App and Repository APIs
- POST /api/v1/github/app/install-url
- GET /api/v1/github/installations
- GET /api/v1/github/repositories
- POST /api/v1/github/repositories/connect
- POST /api/v1/github/repositories/{id}/snapshot

### 7.2 Architecture Doc and Fusion APIs
- POST /api/v1/system-architecture/{repo_id}/analyze
- GET /api/v1/system-architecture/{repo_id}/current
- GET /api/v1/system-architecture/{repo_id}/documents
- GET /api/v1/system-architecture/documents/{doc_id}

### 7.3 Variant Generation APIs
- POST /api/v1/system-architecture/{repo_id}/generate-variants
  - input: cost, scalability, performance
  - auto-normalize in backend
- GET /api/v1/system-architecture/variants/{variant_id}
- GET /api/v1/system-architecture/{repo_id}/variants

### 7.4 Deep Plan + Alpha Code APIs
- POST /api/v1/system-architecture/variants/{variant_id}/plan-deeply
- GET /api/v1/system-architecture/deep-plans/{plan_id}
- POST /api/v1/alpha-code/runs
- GET /api/v1/alpha-code/runs
- GET /api/v1/alpha-code/runs/{run_id}
- GET /api/v1/alpha-code/runs/{run_id}/logs
- GET /api/v1/alpha-code/runs/{run_id}/download

## 8. Slider and Weight Strategy

### 8.1 Input Contract
- cost, scalability, performance accepted as float [0..100]
- if all zeros, defaults applied (30/35/35)

### 8.2 Normalization
- normalized_weight = weight / sum(weights)
- values stored in both raw and normalized form for traceability

### 8.3 Safety Rules
- enforce minimum epsilon to avoid zero-division
- retain user raw intent in metadata

## 9. Architecture Document Specification

### 9.1 Markdown Sections (architecture_{unique_key}.md)
1. Executive Summary
2. Monorepo Layout Overview
3. Service Boundaries and Runtime Mapping
4. API Inventory
5. Database Structure and Data Ownership
6. Dependency and Library Inventory
7. Infrastructure and External Integrations
8. Critical Paths and Bottlenecks
9. Reliability and Security Findings
10. Known Gaps and Confidence Notes

### 9.2 JSON Schema (architecture_{unique_key}.json)
Top-level keys:
- metadata
- repository
- services
- apis
- databases
- dependencies
- runtime_graph
- static_graph
- fused_graph
- bottlenecks
- risks
- opportunities
- confidence

## 10. Variant Generation Specification

Each of 3 variants must include:
- variant_id
- title
- target_profile (cost/scalability/performance)
- architecture_graph (nodes/edges)
- major_changes
- migration_plan_summary
- expected_metrics
  - cost_delta
  - scalability_delta
  - latency_delta
  - reliability_delta
- complexity_score
- risk_score
- assumptions
- rejection_conditions

Validation gates before storing:
- strict Pydantic schema validation
- graph consistency checks
- forbidden operations checks

## 11. Plan Deeply Report Specification

The deep plan report must include:
1. Current vs Target Architecture Diff
2. Service-level refactoring plan
3. Database migration strategy
4. Dependency/library change matrix
5. Folder/file transformation plan
6. Test strategy and coverage plan
7. Rollback strategy
8. Incremental rollout stages
9. Cost and risk analysis
10. Acceptance criteria and done definition

Rule: Make Alpha Codebase is blocked until deep plan exists for selected variant.

## 12. Alpha Code Generation Pipeline

### 12.1 Pipeline Stages
1. Clone/copy snapshot into alpha workspace
2. Apply transformation graph by module
3. Regenerate configs and dependency manifests
4. Run static checks
5. Run test suite
6. Run build checks
7. Collect diffs and reports
8. Package zip artifact

### 12.2 Quality Gates (mandatory)
- syntax checks pass
- tests pass or are marked with explicit known-failure policy
- artifact manifest generated

### 12.3 Output
- zip artifact + summary report + run logs

## 13. Email Notification (SMTP)

### 13.1 Trigger Points
- run completed
- run failed

### 13.2 Message Contents
- project name
- run id
- status
- short summary
- download link (when completed)

## 14. Frontend Plan

### 14.1 New Page: System-Architecture
- route: /system-architecture
- sections:
  - Current fused architecture graph
  - Slider control panel
  - Generate 3 architectures
  - Variant cards with graph previews
  - Actions: Plan Deeply, Make Alpha Codebase

### 14.2 New Page: Alpha-Code
- route: /alpha-code
- run table with statuses:
  - pending
  - progress
  - completed
  - failed
- run detail drawer (logs, summary, metrics)
- download button on completed runs

### 14.3 UX Rules
- clear state machine for long-running jobs
- optimistic polling with exponential backoff
- hard error states with retry

## 15. Required .env Variables (dummy placeholders)

Add placeholders to .env (replace later):

```env
# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_CLIENT_ID=dummy_client_id
GITHUB_APP_CLIENT_SECRET=dummy_client_secret
GITHUB_APP_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nREPLACE_ME\n-----END PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=dummy_webhook_secret

# Repo and workspace
REPO_WORKSPACE_ROOT=./storage
MAX_REPO_SNAPSHOT_MB=2000
ALPHA_CODE_TIMEOUT_MINUTES=120

# Azure OpenAI GPT-5
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=dummy_azure_key
AZURE_OPENAI_DEPLOYMENT_GPT5=gpt-5
AZURE_OPENAI_API_VERSION=2024-10-21

# SMTP notifications
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=dummy_user
SMTP_PASSWORD=dummy_pass
SMTP_FROM_EMAIL=noreply@example.com
SMTP_USE_TLS=true

# App URLs for links
APP_BASE_URL=https://your-frontend.example.com
DOWNLOAD_LINK_TTL_HOURS=24
```

## 16. Security and Governance

- Encrypt GitHub and SMTP secrets at rest.
- Validate webhook signatures.
- Enforce per-tenant path isolation and no path traversal.
- Store immutable snapshot references by commit SHA.
- Keep full audit logs for generation actions.

## 17. Testing Strategy

### 17.1 Unit Tests
- weight normalization logic
- architecture doc schema validation
- variant schema validation
- plan-deeply gate enforcement

### 17.2 Integration Tests
- GitHub installation + repository listing
- snapshot -> analysis -> doc creation
- doc + telemetry fusion -> graph endpoints
- variant generation -> deep plan -> alpha run chain

### 17.3 End-to-End Tests
- full user flow from connect repo to download zip
- email notification on completion
- private monorepo scenario

### 17.4 Non-Functional Tests
- queue retry behavior
- long-run timeout handling
- large monorepo memory constraints

## 18. Rollout Plan

### Phase A (Foundation)
- GitHub App + snapshot + architecture docs

### Phase B (System-Architecture)
- fused current graph + sliders + 3 variants

### Phase C (Planning)
- Plan Deeply generation and gating

### Phase D (Alpha-Code)
- code rewrite pipeline + zip + status page

### Phase E (Notifications)
- SMTP completion/failure notifications

## 19. Implementation Guardrails

- No direct alpha generation without deep plan artifact.
- No direct edits to source snapshots; always copy to run workspace.
- Every run must be reproducible from snapshot id + variant id.

## 20. Open Questions Before Implementation

1. Confirm default slider split exactly as:
   - cost 30
   - scalability 35
   - performance 35

2. Confirm AI generation latency expectation:
   - synchronous request response (slow), or
   - async job only (recommended)

3. Confirm max monorepo size target for v1 (in GB and file count).

4. Confirm whether Alpha-Code zip should include:
   - only rewritten code, or
   - rewritten code + deep plan + test logs + diff report.

5. Confirm expected SMTP sender identity (single global sender vs tenant sender).

6. Confirm target branch strategy for snapshots:
   - default branch only, or user-selected branch per run.

Once these are confirmed, implementation can start phase by phase with migration + API + UI + tests.
