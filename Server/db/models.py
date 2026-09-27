from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Index, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from db.base import Base


class Tenant(Base):
    """Tenant/Organization table"""
    __tablename__ = "tenants"
    
    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    max_spans_per_day = Column(Integer, default=1000000)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    api_keys = relationship("APIKey", back_populates="tenant")
    spans = relationship("Span", back_populates="tenant")
    projects = relationship("Project", back_populates="tenant")


class User(Base):
    """User table"""
    __tablename__ = "users"
    
    id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    pending_signup = Column(Boolean, default=False)
    
    # OAuth fields
    auth_provider = Column(String(50), default="local")  # "local" or "google"
    google_id = Column(String(255), nullable=True, unique=True)
    picture = Column(String(512), nullable=True)

    # Optional profile fields
    phone_number = Column(String(32), nullable=True)
    linkedin_url = Column(String(512), nullable=True)
    bio = Column(Text, nullable=True)
    
    # Password reset fields
    password_reset_token = Column(String(512), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    
    # OTP fields
    signup_otp = Column(String(10), nullable=True)
    signup_otp_expires = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="users")


class APIKey(Base):
    """API Key table"""
    __tablename__ = "api_keys"
    
    key = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="api_keys")


class Project(Base):
    """Tenant-scoped observable project."""
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    sdk_service_name = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="projects")
    spans = relationship("Span", back_populates="project")


class Span(Base):
    __tablename__ = "spans"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=True, index=True)
    trace_id = Column(String(64), nullable=False, index=True)
    span_id = Column(String(64), nullable=False, index=True)
    parent_span_id = Column(String(64), nullable=True, index=True)
    service_name = Column(String(255), nullable=False, index=True)
    operation = Column(String(255), nullable=False)
    kind = Column(String(32), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    latency_ms = Column(Float, nullable=False)
    status_code = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    downstream = Column(String(255), nullable=True)
    attributes_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="spans")
    project = relationship("Project", back_populates="spans")
    
    __table_args__ = (
        Index('idx_tenant_trace', 'tenant_id', 'trace_id'),
        Index('idx_tenant_service', 'tenant_id', 'service_name', 'start_time'),
        Index('idx_tenant_time', 'tenant_id', 'start_time'),
        Index('idx_tenant_project_time', 'tenant_id', 'project_id', 'start_time'),
    )


class ArchitectureSnapshot(Base):
    __tablename__ = "architecture_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    snapshot_time = Column(DateTime, default=datetime.utcnow, index=True)
    nodes = Column(Text, nullable=False)  # JSON
    edges = Column(Text, nullable=False)  # JSON
    metrics = Column(Text, nullable=False)  # JSON
    issues = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)


class ArchitectureDiscovery(Base):
    """SDK auto-discovery data"""
    __tablename__ = "architecture_discoveries"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=True, index=True)
    project_name = Column(String(255), nullable=True, index=True)
    service_name = Column(String(255), nullable=False, index=True)
    service_type = Column(String(64), nullable=False)
    version = Column(String(64), nullable=True)
    endpoints = Column(Text, nullable=False)  # JSON array of discovered endpoints
    databases = Column(Text, nullable=False)  # JSON array of database connections
    external_services = Column(Text, nullable=False)  # JSON array of external dependencies
    middleware = Column(Text, nullable=True)  # JSON array of middleware
    dependencies = Column(Text, nullable=True)  # JSON dict of service dependencies
    architecture_patterns = Column(Text, nullable=True)  # JSON dict of patterns
    discovered_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_tenant_service_discovery', 'tenant_id', 'service_name', 'discovered_at'),
    )


class GitHubInstallation(Base):
    """GitHub App installations mapped to tenant accounts."""
    __tablename__ = "github_installations"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    github_installation_id = Column(String(64), nullable=False, index=True)
    account_login = Column(String(255), nullable=False)
    account_type = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_gh_install_tenant_installation", "tenant_id", "github_installation_id"),
    )


class ConnectedRepository(Base):
    """Repositories connected by a tenant through GitHub App."""
    __tablename__ = "connected_repositories"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    installation_id = Column(String(64), ForeignKey("github_installations.id"), nullable=True, index=True)
    owner = Column(String(255), nullable=False)
    repo_name = Column(String(255), nullable=False)
    full_name = Column(String(512), nullable=False, index=True)
    default_branch = Column(String(255), nullable=False, default="main")
    is_private = Column(Boolean, default=True)
    is_monorepo = Column(Boolean, default=True)
    remote_url = Column(Text, nullable=True)
    local_repo_path = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_repo_tenant_fullname", "tenant_id", "full_name"),
    )


class RepoSnapshot(Base):
    """Immutable repository snapshot metadata."""
    __tablename__ = "repo_snapshots"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    repository_id = Column(String(64), ForeignKey("connected_repositories.id"), nullable=False, index=True)
    branch = Column(String(255), nullable=False)
    commit_sha = Column(String(128), nullable=True)
    snapshot_path = Column(Text, nullable=False)
    snapshot_size_bytes = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="created")
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ArchitectureDocument(Base):
    """Generated architecture documents (markdown + json)."""
    __tablename__ = "architecture_documents_v2"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    repository_id = Column(String(64), ForeignKey("connected_repositories.id"), nullable=False, index=True)
    snapshot_id = Column(String(64), ForeignKey("repo_snapshots.id"), nullable=False, index=True)
    unique_key = Column(String(128), nullable=False, index=True)
    markdown_path = Column(Text, nullable=False)
    json_path = Column(Text, nullable=False)
    runtime_enriched = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ArchitectureVariant(Base):
    """Generated architecture alternatives from optimization controls."""
    __tablename__ = "architecture_variants"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    architecture_document_id = Column(String(64), ForeignKey("architecture_documents_v2.id"), nullable=False, index=True)
    variant_index = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    weights_json = Column(Text, nullable=False)
    variant_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeepPlanReport(Base):
    """Detailed technical plan artifacts generated before alpha code."""
    __tablename__ = "deep_plan_reports"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    architecture_variant_id = Column(String(64), ForeignKey("architecture_variants.id"), nullable=False, index=True)
    markdown_path = Column(Text, nullable=False)
    json_path = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlphaCodeRun(Base):
    """Alpha code generation jobs and downloadable artifact metadata."""
    __tablename__ = "alpha_code_runs"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    repository_id = Column(String(64), ForeignKey("connected_repositories.id"), nullable=False, index=True)
    snapshot_id = Column(String(64), ForeignKey("repo_snapshots.id"), nullable=False, index=True)
    architecture_variant_id = Column(String(64), ForeignKey("architecture_variants.id"), nullable=False, index=True)
    deep_plan_report_id = Column(String(64), ForeignKey("deep_plan_reports.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending")
    workspace_path = Column(Text, nullable=False)
    zip_path = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlphaSandboxSession(Base):
    """Interactive sandbox sessions created from completed alpha runs."""
    __tablename__ = "alpha_sandbox_sessions"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    repository_id = Column(String(64), ForeignKey("connected_repositories.id"), nullable=False, index=True)
    alpha_run_id = Column(String(64), ForeignKey("alpha_code_runs.id"), nullable=False, index=True)
    workspace_path = Column(Text, nullable=False)
    persistent_root = Column(Text, nullable=False)
    uploaded_tests_path = Column(Text, nullable=False)
    stack_type = Column(String(64), nullable=False, default="unknown")
    status = Column(String(32), nullable=False, default="running")
    last_activity_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_alpha_sandbox_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("idx_alpha_sandbox_tenant_repo_created", "tenant_id", "repository_id", "created_at"),
    )


class AlphaSandboxExecution(Base):
    """Command/test/autofix execution logs for sandbox sessions."""
    __tablename__ = "alpha_sandbox_executions"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    session_id = Column(String(64), ForeignKey("alpha_sandbox_sessions.id"), nullable=False, index=True)
    action_type = Column(String(32), nullable=False)
    command_text = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="completed")
    stdout_text = Column(Text, nullable=True)
    stderr_text = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_alpha_sandbox_exec_tenant_session_created", "tenant_id", "session_id", "created_at"),
    )


class ArchitectureVariantReport(Base):
    """Deep workflow reports generated on demand for architecture variants."""
    __tablename__ = "architecture_variant_reports"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    architecture_variant_id = Column(String(64), ForeignKey("architecture_variants.id"), nullable=False, index=True)
    architecture_document_id = Column(String(64), ForeignKey("architecture_documents_v2.id"), nullable=False, index=True)
    repository_id = Column(String(64), ForeignKey("connected_repositories.id"), nullable=False, index=True)
    snapshot_id = Column(String(64), ForeignKey("repo_snapshots.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending")
    report_markdown_path = Column(Text, nullable=True)
    report_pdf_path = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_variant_reports_tenant_variant_created", "tenant_id", "architecture_variant_id", "created_at"),
    )


class HourlyAnalytics(Base):
    """Continuous hourly rollups for project/service analytics."""
    __tablename__ = "hourly_analytics"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=True, index=True)
    service_name = Column(String(255), nullable=False, index=True)
    hour_bucket = Column(DateTime, nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    total_latency_ms = Column(Float, nullable=False, default=0.0)
    max_latency_ms = Column(Float, nullable=False, default=0.0)
    min_latency_ms = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_hourly_tenant_project_service_bucket", "tenant_id", "project_id", "service_name", "hour_bucket"),
    )


class DailyAnalytics(Base):
    """Long-horizon daily rollups for analytics retention."""
    __tablename__ = "daily_analytics"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=True, index=True)
    service_name = Column(String(255), nullable=False, index=True)
    day_bucket = Column(DateTime, nullable=False, index=True)
    request_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    total_latency_ms = Column(Float, nullable=False, default=0.0)
    max_latency_ms = Column(Float, nullable=False, default=0.0)
    min_latency_ms = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_daily_tenant_project_service_bucket", "tenant_id", "project_id", "service_name", "day_bucket"),
    )


class ProjectAIReport(Base):
    """AI-generated project health report (scheduled + on-demand)."""
    __tablename__ = "project_ai_reports"

    id = Column(String(64), primary_key=True, index=True)
    tenant_id = Column(String(64), ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False, index=True)
    report_date = Column(DateTime, nullable=False, index=True)
    report_json = Column(Text, nullable=False)
    markdown = Column(Text, nullable=True)
    generated_by = Column(String(32), nullable=False, default="scheduled")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_report_tenant_project_date", "tenant_id", "project_id", "report_date"),
    )
