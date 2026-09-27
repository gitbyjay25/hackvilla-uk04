# Nexarch API Documentation

Complete API reference for all FastAPI endpoints with Next.js integration examples.

**Base URL:** `http://localhost:8000` (Development)  
**Authentication:** API Key via `X-API-Key` header  
**Content-Type:** `application/json`

---

## Table of Contents

1. [Authentication](#authentication)
2. [Health & System Endpoints](#health--system-endpoints)
3. [Data Ingestion Endpoints](#data-ingestion-endpoints)
4. [Architecture Discovery Endpoints](#architecture-discovery-endpoints)
5. [Dashboard Endpoints](#dashboard-endpoints)
6. [AI-Powered Design Endpoints](#ai-powered-design-endpoints)
7. [Workflow Generation Endpoints](#workflow-generation-endpoints)
8. [Admin & Tenant Management](#admin--tenant-management)
9. [Cache Management Endpoints](#cache-management-endpoints)
10. [Next.js Integration Guide](#nextjs-integration-guide)

---

## Authentication

**Authentication Method:** Google OAuth 2.0 Only

All authentication is handled via Google OAuth. Users must sign in with their Google account to access the platform.

### Google OAuth Flow

#### 1. Get Google Authorization URL
```http
GET /auth/google
```

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

**Next.js Example:**
```typescript
// pages/login.tsx
export default function Login() {
  const handleGoogleLogin = async () => {
    const response = await fetch('http://localhost:8000/auth/google');
    const { auth_url } = await response.json();
    
    // Redirect user to Google
    window.location.href = auth_url;
  };

  return (
    <button onClick={handleGoogleLogin}>
      Sign in with Google
    </button>
  );
}
```

#### 2. Google OAuth Callback
```http
GET /auth/google/callback?code={authorization_code}
```

This endpoint is called automatically by Google after user authorization. It:
- Exchanges the code for user information
- Creates or retrieves the user account
- Redirects to frontend with access token in URL hash

**Redirect URL:** `https://modelix.world/auth/callback#access_token={token}&token_type=bearer`

#### 3. Alternative: Direct Token Exchange
```http
POST /auth/google/signin
```

**Request Body:**
```json
{
  "code": "google_authorization_code",
  "state": "optional_state_parameter"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "picture": "https://...",
    "auth_provider": "google",
    "is_active": true,
    "is_verified": true
  }
}
```

**Next.js Example:**
```typescript
// Handle callback with authorization code
async function handleGoogleCallback(code: string) {
  const response = await fetch('http://localhost:8000/auth/google/signin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  
  const { access_token, user } = await response.json();
  
  // Store token
  localStorage.setItem('access_token', access_token);
  
  // Redirect to dashboard
  router.push('/dashboard');
}
```

#### 4. Get Current User
```http
GET /auth/me
```

**Headers:**
```
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": "user-uuid",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "user",
  "created_at": "2026-01-17T00:00:00.000Z"
}
```

#### 5. Check Google OAuth Configuration Status
```http
GET /auth/google/status
```

**Response:**
```json
{
  "configured": true,
  "has_client_id": true,
  "has_client_secret": true,
  "has_redirect_uri": true,
  "redirect_uri": "https://api.modelix.world/auth/google/callback",
  "message": "Google OAuth is properly configured"
}
```

#### 6. Logout
```http
POST /auth/logout
```

**Response:**
```json
{
  "message": "Logged out successfully. Please remove the token from client storage."
}
```

**Note:** Since JWT tokens are stateless, logout is handled client-side by removing the token.

### API Client with Authentication

```typescript
// lib/api-client.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = {
  async request(endpoint: string, options: RequestInit = {}) {
    const token = localStorage.getItem('access_token');
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...options.headers,
      },
    });
    
    if (response.status === 401) {
      // Redirect to login
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    
    return response.json();
  },
};
```

### Environment Setup

```env
# .env.local (Next.js Frontend)
NEXT_PUBLIC_API_URL=https://api.modelix.world
NEXT_PUBLIC_FRONTEND_URL=https://modelix.world

# .env (FastAPI Backend)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://api.modelix.world/auth/google/callback
JWT_SECRET_KEY=your-secret-key-change-in-production
```

---

## Health & System Endpoints

### 1. Root Endpoint
```http
GET /
```

**Response:**
```json
{
  "service": "Nexarch",
  "version": "1.0.0",
  "status": "running",
  "features": {
    "multi_tenant": true,
    "rate_limiting": true,
    "caching": true,
    "authentication": "API Key"
  }
}
```

**Next.js:**
```typescript
// pages/api/health.ts
import { apiClient } from '@/lib/api-client';

export default async function handler(req, res) {
  const data = await apiClient.request('/');
  res.status(200).json(data);
}

// React Component
const { data } = useSWR('/', () => apiClient.request('/'));
```

### 2. Basic Health Check
```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-16T10:30:00.000Z"
}
```

### 3. Detailed Health Check
```http
GET /api/v1/health/detailed
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-16T10:30:00.000Z",
  "version": "1.0.0",
  "python_version": "3.11.0",
  "components": {
    "database": "healthy",
    "ai_client": "configured",
    "multi_tenant": "enabled",
    "caching": "enabled",
    "ai_generation": "enabled"
  },
  "features": {
    "auto_discovery": true,
    "ai_architecture_design": true,
    "dashboard": true,
    "multi_tenancy": true
  }
}
```

**Next.js:**
```typescript
// components/HealthStatus.tsx
import useSWR from 'swr';

export const HealthStatus = () => {
  const { data, error } = useSWR('/api/v1/health/detailed', 
    () => apiClient.request('/api/v1/health/detailed')
  );

  if (error) return <div>Error loading health status</div>;
  if (!data) return <div>Loading...</div>;

  return (
    <div className="health-status">
      <h2>System Status: {data.status}</h2>
      <div>Version: {data.version}</div>
      <div>Database: {data.components.database}</div>
      <div>AI Client: {data.components.ai_client}</div>
    </div>
  );
};
```

### 4. System Information
```http
GET /api/v1/system/info
```

**Response:**
```json
{
  "app_name": "Nexarch",
  "version": "1.0.0",
  "environment": "production",
  "features": {
    "multi_tenancy": true,
    "ai_generation": true,
    "caching": true,
    "auto_discovery": true,
    "dashboard": true,
    "mcp_server": true
  },
  "endpoints": {
    "ingest": "/api/v1/ingest/spans",
    "dashboard": "/api/v1/dashboard/*",
    "ai_design": "/api/v1/ai-design/*",
    "admin": "/api/v1/admin/*",
    "health": "/api/v1/health"
  }
}
```

### 5. System Statistics
```http
GET /api/v1/system/stats
```
**Auth Required:** Yes

**Response:**
```json
{
  "tenant_id": "uuid-here",
  "spans": {
    "total": 10000,
    "last_hour": 150,
    "last_day": 2400,
    "with_errors": 50,
    "error_rate": 0.5
  },
  "services": {
    "unique_count": 8
  },
  "traces": {
    "unique_count": 1500
  },
  "timestamp": "2026-01-16T10:30:00.000Z"
}
```

---

## Data Ingestion Endpoints

### 1. Ingest Single Span
```http
POST /api/v1/ingest
```

**Request Body:**
```json
{
  "trace_id": "trace-123",
  "span_id": "span-456",
  "parent_span_id": null,
  "service_name": "api-gateway",
  "operation": "GET /users",
  "kind": "server",
  "start_time": "2026-01-16T10:30:00.000Z",
  "end_time": "2026-01-16T10:30:00.100Z",
  "latency_ms": 100,
  "status_code": 200,
  "error": null,
  "downstream": ["user-service"]
}
```

**Response:**
```json
{
  "status": "accepted",
  "span_id": "span-456"
}
```

**Next.js:**
```typescript
// lib/telemetry.ts
export async function sendTelemetry(spanData: SpanData) {
  return apiClient.request('/api/v1/ingest', {
    method: 'POST',
    body: JSON.stringify(spanData),
  });
}

// Usage in API route
export default async function handler(req, res) {
  const startTime = Date.now();
  
  try {
    // Your API logic
    const result = await processRequest(req);
    
    // Send telemetry
    await sendTelemetry({
      trace_id: req.headers['x-trace-id'] || generateTraceId(),
      span_id: generateSpanId(),
      service_name: 'nextjs-api',
      operation: `${req.method} ${req.url}`,
      kind: 'server',
      start_time: new Date(startTime).toISOString(),
      end_time: new Date().toISOString(),
      latency_ms: Date.now() - startTime,
      status_code: 200,
      error: null,
      downstream: [],
    });
    
    res.status(200).json(result);
  } catch (error) {
    // Send error telemetry
    await sendTelemetry({
      // ... similar to above but with error: error.message
    });
    res.status(500).json({ error: 'Internal error' });
  }
}
```

### 2. Batch Ingest
```http
POST /api/v1/ingest/batch
```

**Request Body:**
```json
[
  {
    "trace_id": "trace-123",
    "span_id": "span-456",
    // ... span fields
  },
  {
    "trace_id": "trace-124",
    "span_id": "span-457",
    // ... span fields
  }
]
```

**Response:**
```json
{
  "status": "accepted",
  "count": 2,
  "failed": 0
}
```

### 3. Ingestion Statistics
```http
GET /api/v1/ingest/stats
```

**Response:**
```json
{
  "total_spans": 10000,
  "unique_services": 8,
  "unique_traces": 1500
}
```

---

## Architecture Discovery Endpoints

### 1. Submit Architecture Discovery
```http
POST /api/v1/ingest/architecture-discovery
```

**Request Body:**
```json
{
  "service_name": "api-gateway",
  "service_type": "fastapi",
  "version": "1.0.0",
  "endpoints": [
    {
      "path": "/api/users",
      "method": "GET",
      "handler": "get_users"
    }
  ],
  "databases": [
    {
      "type": "postgresql",
      "host": "localhost",
      "database": "myapp"
    }
  ],
  "external_services": ["stripe.com", "sendgrid.com"],
  "middleware": ["cors", "auth"],
  "dependencies": {
    "production": ["fastapi", "sqlalchemy"]
  },
  "architecture_patterns": {
    "pattern": "microservices",
    "message_broker": "redis"
  },
  "discovered_at": "2026-01-16T10:30:00.000Z"
}
```

**Response:**
```json
{
  "status": "accepted",
  "service": "api-gateway",
  "endpoints_discovered": 1,
  "databases_discovered": 1,
  "external_services_discovered": 2,
  "message": "Architecture discovery data saved successfully"
}
```

### 2. Get Architecture Discoveries
```http
GET /api/v1/ingest/architecture-discoveries
```

**Response:**
```json
{
  "total": 3,
  "discoveries": [
    {
      "id": 1,
      "service_name": "api-gateway",
      "service_type": "fastapi",
      "version": "1.0.0",
      "endpoints": [...],
      "databases": [...],
      "external_services": [...],
      "middleware": [...],
      "architecture_patterns": {...},
      "discovered_at": "2026-01-16T10:30:00.000Z",
      "updated_at": "2026-01-16T10:35:00.000Z"
    }
  ]
}
```

**Next.js:**
```typescript
// pages/architecture/discoveries.tsx
export default function ArchitectureDiscoveries() {
  const { data } = useSWR(
    '/api/v1/ingest/architecture-discoveries',
    () => apiClient.request('/api/v1/ingest/architecture-discoveries')
  );

  return (
    <div>
      <h1>Architecture Discoveries ({data?.total || 0})</h1>
      {data?.discoveries.map((discovery) => (
        <div key={discovery.id} className="discovery-card">
          <h3>{discovery.service_name}</h3>
          <p>Type: {discovery.service_type}</p>
          <p>Version: {discovery.version}</p>
          <p>Endpoints: {discovery.endpoints.length}</p>
          <p>Databases: {discovery.databases.length}</p>
        </div>
      ))}
    </div>
  );
}
```

---

## Dashboard Endpoints

### 1. Dashboard Overview
```http
GET /api/v1/dashboard/overview
```

**Response:**
```json
{
  "total_services": 8,
  "total_requests": 150000,
  "avg_latency_ms": 245.5,
  "error_rate": 0.02,
  "health_score": 85,
  "critical_issues": 1,
  "warnings": 3,
  "architecture_complexity": 3.5,
  "active_incidents": 1,
  "uptime_percentage": 99.8,
  "last_updated": "2026-01-16T10:30:00.000Z"
}
```

**Next.js:**
```typescript
// components/Dashboard/Overview.tsx
import useSWR from 'swr';

export const DashboardOverview = () => {
  const { data, error } = useSWR(
    '/api/v1/dashboard/overview',
    () => apiClient.request('/api/v1/dashboard/overview'),
    { refreshInterval: 30000 } // Refresh every 30s
  );

  if (error) return <ErrorDisplay error={error} />;
  if (!data) return <LoadingSpinner />;

  return (
    <div className="dashboard-grid">
      <MetricCard 
        title="Total Services" 
        value={data.total_services} 
        icon="🔧"
      />
      <MetricCard 
        title="Total Requests" 
        value={data.total_requests.toLocaleString()} 
        icon="📊"
      />
      <MetricCard 
        title="Avg Latency" 
        value={`${data.avg_latency_ms}ms`}
        status={data.avg_latency_ms > 500 ? 'warning' : 'good'}
        icon="⚡"
      />
      <MetricCard 
        title="Error Rate" 
        value={`${(data.error_rate * 100).toFixed(2)}%`}
        status={data.error_rate > 0.05 ? 'critical' : 'good'}
        icon="🚨"
      />
      <MetricCard 
        title="Health Score" 
        value={data.health_score}
        status={data.health_score >= 80 ? 'good' : 'warning'}
        icon="❤️"
      />
      <MetricCard 
        title="Uptime" 
        value={`${data.uptime_percentage}%`}
        icon="⏱️"
      />
    </div>
  );
};
```

### 2. Architecture Map
```http
GET /api/v1/dashboard/architecture-map
```

**Response:**
```json
{
  "nodes": [
    {
      "id": "api-gateway",
      "type": "api",
      "metrics": {
        "call_count": 5000,
        "avg_latency_ms": 150,
        "error_rate": 0.01
      },
      "position": { "x": 0, "y": 0 }
    }
  ],
  "edges": [
    {
      "source": "api-gateway",
      "target": "user-service",
      "call_count": 2000,
      "avg_latency_ms": 50,
      "error_rate": 0.005
    }
  ],
  "graph_stats": {
    "total_nodes": 8,
    "total_edges": 12,
    "is_dag": true,
    "avg_degree": 3.0
  },
  "bottlenecks": ["payment-service"],
  "critical_paths": [["api-gateway", "user-service", "database"]]
}
```

**Next.js with React Flow:**
```typescript
// components/ArchitectureMap.tsx
import ReactFlow, { Node, Edge } from 'reactflow';
import 'reactflow/dist/style.css';
import useSWR from 'swr';

export const ArchitectureMap = () => {
  const { data } = useSWR(
    '/api/v1/dashboard/architecture-map',
    () => apiClient.request('/api/v1/dashboard/architecture-map')
  );

  if (!data) return <LoadingSpinner />;

  const nodes: Node[] = data.nodes.map((node) => ({
    id: node.id,
    type: 'default',
    data: { 
      label: node.id,
      metrics: node.metrics,
    },
    position: node.position,
    style: {
      background: node.metrics.error_rate > 0.05 ? '#ff6b6b' : '#4ecdc4',
      color: 'white',
      padding: 10,
      borderRadius: 5,
    },
  }));

  const edges: Edge[] = data.edges.map((edge, idx) => ({
    id: `e${idx}`,
    source: edge.source,
    target: edge.target,
    label: `${edge.call_count} calls`,
    animated: edge.error_rate > 0.05,
    style: { stroke: edge.error_rate > 0.05 ? '#ff6b6b' : '#4ecdc4' },
  }));

  return (
    <div style={{ height: '600px' }}>
      <ReactFlow nodes={nodes} edges={edges} fitView />
      <div className="graph-stats">
        <p>Total Services: {data.graph_stats.total_nodes}</p>
        <p>Total Dependencies: {data.graph_stats.total_edges}</p>
        <p>Bottlenecks: {data.bottlenecks.join(', ')}</p>
      </div>
    </div>
  );
};
```

### 3. Get Services List
```http
GET /api/v1/dashboard/services
```

**Response:**
```json
[
  {
    "name": "api-gateway",
    "type": "api",
    "request_count": 5000,
    "avg_latency_ms": 150,
    "error_rate": 0.01,
    "dependencies": ["user-service", "order-service"],
    "dependents": [],
    "health_status": "healthy",
    "last_seen": "2026-01-16T10:30:00.000Z"
  }
]
```

### 4. Get Service Metrics
```http
GET /api/v1/dashboard/services/{service_name}/metrics
```

**Response:**
```json
{
  "call_count": 5000,
  "avg_latency_ms": 150,
  "error_rate": 0.01,
  "p50_latency_ms": 100,
  "p95_latency_ms": 300,
  "p99_latency_ms": 500
}
```

### 5. Get Trends
```http
GET /api/v1/dashboard/trends?hours=24
```

**Query Parameters:**
- `hours`: Time window (1-168) - default: 24

**Response:**
```json
{
  "latency": [
    { "timestamp": "2026-01-16T09:00:00.000Z", "value": 150.5 },
    { "timestamp": "2026-01-16T10:00:00.000Z", "value": 145.2 }
  ],
  "error_rate": [
    { "timestamp": "2026-01-16T09:00:00.000Z", "value": 0.012 },
    { "timestamp": "2026-01-16T10:00:00.000Z", "value": 0.015 }
  ],
  "volume": [
    { "timestamp": "2026-01-16T09:00:00.000Z", "value": 1500 },
    { "timestamp": "2026-01-16T10:00:00.000Z", "value": 1650 }
  ],
  "period_hours": 24
}
```

**Next.js with Chart.js:**
```typescript
// components/TrendsChart.tsx
import { Line } from 'react-chartjs-2';
import useSWR from 'swr';

export const TrendsChart = ({ hours = 24 }) => {
  const { data } = useSWR(
    `/api/v1/dashboard/trends?hours=${hours}`,
    () => apiClient.request(`/api/v1/dashboard/trends?hours=${hours}`)
  );

  if (!data) return <LoadingSpinner />;

  const chartData = {
    labels: data.latency.map(d => new Date(d.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'Latency (ms)',
        data: data.latency.map(d => d.value),
        borderColor: 'rgb(75, 192, 192)',
        tension: 0.1,
      },
    ],
  };

  return <Line data={chartData} />;
};
```

### 6. Get AI Insights
```http
GET /api/v1/dashboard/insights
```

**Response:**
```json
{
  "insights": [
    {
      "type": "alert",
      "severity": "high",
      "title": "High Error Rate Detected",
      "description": "Error rate is 5.2%, above the 5% threshold",
      "recommendation": "Review recent deployments and check service logs",
      "confidence": 0.95
    }
  ],
  "anomalies": [],
  "recommendations": [
    "Enable Redis caching to improve response times",
    "Implement circuit breakers for external API calls",
    "Add database read replicas to distribute load"
  ]
}
```

### 7. Get System Health
```http
GET /api/v1/dashboard/health
```

**Response:**
```json
{
  "overall_health": 85,
  "categories": {
    "performance": {
      "score": 85,
      "status": "good",
      "metrics": { "avg_latency_ms": 245.5 }
    },
    "reliability": {
      "score": 90,
      "status": "good",
      "metrics": { "error_rate": 0.02 }
    },
    "architecture": {
      "score": 80,
      "status": "good",
      "metrics": { "critical_issues": 1, "total_issues": 4 }
    },
    "scalability": {
      "score": 85,
      "status": "good",
      "metrics": { "bottlenecks": 1, "has_cycles": false }
    }
  },
  "timestamp": "2026-01-16T10:30:00.000Z"
}
```

### 8. Get Bottlenecks
```http
GET /api/v1/dashboard/bottlenecks
```

**Response:**
```json
{
  "bottlenecks": ["payment-service", "database"],
  "critical_paths": [
    ["api-gateway", "user-service", "database"],
    ["api-gateway", "payment-service", "stripe-api"]
  ],
  "cycles": [],
  "recommendations": [
    "Service 'payment-service' is a bottleneck - consider adding redundancy",
    "Service 'database' is a bottleneck - consider adding redundancy"
  ]
}
```

### 9. Generate Workflow Alternatives
```http
GET /api/v1/dashboard/workflows?goal=optimize_performance
```

**Query Parameters:**
- `goal`: optimize_performance | reduce_cost | improve_reliability

**Response:**
```json
{
  "ai_workflows": [
    {
      "name": "Add Caching Layer",
      "description": "Introduce Redis caching to reduce database load",
      "steps": ["Deploy Redis", "Update services", "Monitor"],
      "estimated_effort": "2 weeks",
      "impact": "high"
    }
  ],
  "langgraph_workflow": {
    "name": "Performance Optimization",
    "complexity_score": 6.5,
    "risk_score": 3.2,
    "proposed_changes": [...]
  },
  "goal": "optimize_performance",
  "architecture_summary": {
    "total_services": 8,
    "total_dependencies": 12,
    "critical_issues": 1
  },
  "generated_at": "2026-01-16T10:30:00.000Z"
}
```

### 10. Get AI Architecture Recommendations
```http
GET /api/v1/dashboard/recommendations
```

**Response:**
```json
{
  "recommendations": {
    "architecture_type": "microservices",
    "patterns": ["circuit-breaker", "rate-limiting", "caching"],
    "optimizations": [
      "Add Redis caching layer",
      "Implement async processing for long-running tasks",
      "Add database connection pooling"
    ],
    "migrations": [],
    "risk_assessment": "medium",
    "estimated_effort": "2-3 months",
    "priority": "medium"
  },
  "current_state": {
    "services": 8,
    "dependencies": 12,
    "critical_issues": 1,
    "architecture_type": "microservices"
  },
  "generated_at": "2026-01-16T10:30:00.000Z"
}
```

---

## AI-Powered Design Endpoints

### 1. Design New Architecture
```http
POST /api/v1/ai-design/design-new
```

**Request Body:**
```json
{
  "business_domain": "food delivery",
  "expected_scale": "1M orders/day",
  "key_features": ["real-time tracking", "payment processing", "rider matching"],
  "performance_requirements": {
    "max_latency_ms": 100,
    "availability": "99.99%"
  },
  "constraints": {
    "budget": "medium",
    "timeline": "6 months",
    "team_size": 10
  },
  "existing_tech_stack": ["python", "react", "postgresql"],
  "compliance_requirements": ["PCI-DSS", "GDPR"],
  "num_alternatives": 3
}
```

**Response:**
```json
[
  {
    "name": "Microservices Architecture",
    "description": "Event-driven microservices with async messaging",
    "services": [
      {
        "name": "order-service",
        "responsibility": "Handle order creation and tracking",
        "tech_stack": ["python", "fastapi", "postgresql"]
      }
    ],
    "databases": [
      {
        "type": "postgresql",
        "purpose": "transactional data",
        "estimated_size": "500GB"
      }
    ],
    "deployment": {
      "strategy": "kubernetes",
      "regions": ["us-east", "eu-west"],
      "auto_scaling": true
    },
    "estimated_cost": "$5000-8000/month",
    "implementation_roadmap": [
      {
        "phase": "Phase 1",
        "duration": "2 months",
        "deliverables": ["Core services", "API gateway"]
      }
    ],
    "pros": ["High scalability", "Independent deployment"],
    "cons": ["Complex operations", "Eventual consistency"],
    "risk_level": "medium"
  }
]
```

**Next.js:**
```typescript
// pages/ai-design/new.tsx
export default function NewDesign() {
  const [loading, setLoading] = useState(false);
  const [designs, setDesigns] = useState([]);

  const handleSubmit = async (formData) => {
    setLoading(true);
    try {
      const result = await apiClient.request('/api/v1/ai-design/design-new', {
        method: 'POST',
        body: JSON.stringify(formData),
      });
      setDesigns(result);
    } catch (error) {
      console.error('Design failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>AI Architecture Designer</h1>
      <DesignForm onSubmit={handleSubmit} />
      {loading && <LoadingSpinner />}
      {designs.map((design, idx) => (
        <DesignCard key={idx} design={design} />
      ))}
    </div>
  );
}
```

### 2. Decompose Monolith
```http
POST /api/v1/ai-design/decompose-monolith
```

**Request Body:**
```json
{
  "monolith_description": "E-commerce platform with 200K LOC, handles users, products, orders, payments",
  "business_capabilities": ["user management", "catalog", "ordering", "payment", "shipping"]
}
```

**Response:**
```json
{
  "microservices": [
    {
      "name": "user-service",
      "bounded_context": "User Management",
      "responsibilities": ["Authentication", "Profile management"],
      "data_ownership": ["users table", "sessions table"],
      "apis": [
        {
          "endpoint": "POST /users",
          "description": "Create user"
        }
      ]
    }
  ],
  "migration_order": [
    {
      "priority": 1,
      "service": "user-service",
      "reason": "Low coupling, high cohesion",
      "estimated_effort": "3 weeks"
    }
  ],
  "data_strategy": {
    "approach": "database-per-service",
    "migration_pattern": "strangler-fig"
  }
}
```

### 3. Design Event-Driven Architecture
```http
POST /api/v1/ai-design/event-driven-design
```

**Request Body:**
```json
{
  "use_cases": [
    "User places order",
    "Payment is processed",
    "Inventory is updated",
    "Notifications are sent"
  ],
  "data_flows": [
    {
      "from": "order-service",
      "to": "payment-service",
      "description": "order details"
    }
  ]
}
```

**Response:**
```json
{
  "domain_events": [
    {
      "name": "OrderPlaced",
      "payload": { "order_id": "string", "user_id": "string", "items": "array" },
      "producers": ["order-service"],
      "consumers": ["payment-service", "inventory-service"]
    }
  ],
  "event_streams": [
    {
      "name": "orders-stream",
      "technology": "kafka",
      "partitions": 10,
      "retention": "7 days"
    }
  ],
  "cqrs_pattern": {
    "command_services": ["order-service"],
    "query_services": ["order-query-service"],
    "event_store": "postgresql"
  },
  "sagas": [
    {
      "name": "OrderFulfillmentSaga",
      "steps": [
        { "service": "order-service", "action": "create_order" },
        { "service": "payment-service", "action": "process_payment" },
        { "service": "inventory-service", "action": "reserve_items" }
      ],
      "compensation": "rollback on failure"
    }
  ]
}
```

### 4. Optimize Existing Architecture
```http
POST /api/v1/ai-design/optimize-architecture
```

**Request Body:**
```json
{
  "pain_points": [
    "Database bottleneck at 1000 QPS",
    "API response time > 500ms",
    "Frequent 503 errors during peak"
  ],
  "optimization_goals": [
    "Reduce latency to <100ms",
    "Scale to 10000 QPS",
    "99.99% availability"
  ]
}
```

**Response:**
```json
{
  "optimizations": [
    {
      "priority": "high",
      "action": "Add Redis caching layer",
      "impact": "Reduce database load by 70%",
      "effort": "1 week",
      "risk": "low",
      "implementation_steps": [
        "Deploy Redis cluster",
        "Update services to use cache",
        "Monitor cache hit rate"
      ]
    }
  ],
  "expected_outcomes": {
    "latency_reduction": "60%",
    "throughput_increase": "10x",
    "availability_improvement": "99.9% → 99.99%"
  },
  "risk_assessment": {
    "overall_risk": "medium",
    "mitigation_strategies": ["Phased rollout", "Feature flags", "Rollback plan"]
  }
}
```

### 5. Get Design Templates
```http
GET /api/v1/ai-design/design-templates
```

**Response:**
```json
{
  "templates": [
    {
      "name": "Microservices E-Commerce",
      "domain": "e-commerce",
      "scale": "1M users",
      "features": ["product catalog", "cart", "checkout", "payments", "shipping"],
      "architecture_type": "microservices",
      "estimated_cost": "$2000-5000/month"
    }
  ]
}
```

---

## Workflow Generation Endpoints

### 1. Get Generated Workflows
```http
GET /api/v1/workflows/generated
```

**Response:**
```json
{
  "workflows": [
    {
      "name": "Add Caching Strategy",
      "description": "Implement Redis caching to improve performance",
      "complexity_score": 5.5,
      "risk_score": 2.0,
      "estimated_time": "2 weeks",
      "proposed_changes": [
        {
          "type": "infrastructure",
          "description": "Deploy Redis cluster",
          "impact": "high"
        }
      ]
    }
  ],
  "generated_at": "2026-01-16T10:30:00.000Z"
}
```

### 2. Get Workflow Comparison
```http
GET /api/v1/workflows/comparison
```

**Response:**
```json
{
  "workflows": [...],
  "recommendation": "Add Caching Strategy is recommended for balanced risk/complexity",
  "comparison_matrix": {
    "complexity": {
      "Add Caching Strategy": 5.5,
      "Decompose Services": 8.0
    },
    "risk": {
      "Add Caching Strategy": 2.0,
      "Decompose Services": 4.5
    },
    "changes": {
      "Add Caching Strategy": 3,
      "Decompose Services": 7
    }
  }
}
```

### 3. Get Workflow Architecture Graph
```http
GET /api/v1/workflows/architecture/graph
```

**Response:**
```json
{
  "current_architecture": {
    "nodes": [...],
    "edges": [...],
    "metadata": {
      "total_services": 8,
      "total_traces": 1500
    }
  },
  "generated_workflows": [
    {
      "workflow_name": "Performance Optimized Path",
      "description": "Optimized for low latency",
      "nodes": [...],
      "edges": [...],
      "changes_from_current": [
        "Added Redis cache",
        "Removed direct DB calls"
      ]
    }
  ]
}
```

---

## Architecture Endpoints

### 1. Get Current Architecture
```http
GET /api/v1/architecture/current
```

**Response:**
```json
{
  "nodes": [
    {
      "id": "api-gateway",
      "type": "api",
      "metrics": {
        "call_count": 5000,
        "avg_latency_ms": 150,
        "error_rate": 0.01
      }
    }
  ],
  "edges": [
    {
      "source": "api-gateway",
      "target": "user-service",
      "call_count": 2000,
      "avg_latency_ms": 50,
      "error_rate": 0.005
    }
  ],
  "metrics_summary": {
    "total_spans": 150000,
    "avg_latency_ms": 245.5,
    "error_rate": 0.02,
    "total_services": 8
  }
}
```

### 2. Get Detected Issues
```http
GET /api/v1/architecture/issues
```

**Response:**
```json
{
  "issues": [
    {
      "type": "performance",
      "severity": "high",
      "service": "payment-service",
      "description": "High latency detected (avg 850ms)",
      "recommendation": "Add caching or optimize database queries",
      "affected_operations": ["POST /payments"],
      "detected_at": "2026-01-16T10:30:00.000Z"
    }
  ],
  "total_count": 4
}
```

---

## Admin & Tenant Management

### 1. Create Tenant (No Auth Required)
```http
POST /api/v1/admin/tenants
```

**Request Body:**
```json
{
  "name": "My Company",
  "admin_email": "admin@mycompany.com"
}
```

**Response:**
```json
{
  "id": "uuid-here",
  "name": "My Company",
  "api_key": "nex_abc123...",
  "admin_email": "admin@mycompany.com",
  "created_at": "2026-01-16T10:30:00.000Z"
}
```

**Next.js:**
```typescript
// pages/signup.tsx
export default function Signup() {
  const handleSignup = async (email: string, companyName: string) => {
    const response = await fetch('http://localhost:8000/api/v1/admin/tenants', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: companyName,
        admin_email: email,
      }),
    });
    
    const data = await response.json();
    
    // Store API key securely
    localStorage.setItem('api_key', data.api_key);
    localStorage.setItem('tenant_id', data.id);
    
    // Redirect to dashboard
    router.push('/dashboard');
  };

  return <SignupForm onSubmit={handleSignup} />;
}
```

### 2. List All Tenants
```http
GET /api/v1/admin/tenants
```

**Response:**
```json
[
  {
    "id": "uuid-1",
    "name": "Company A",
    "is_active": true,
    "created_at": "2026-01-15T10:00:00.000Z"
  }
]
```

### 3. Get Tenant Details
```http
GET /api/v1/admin/tenants/{tenant_id}
```

**Response:**
```json
{
  "id": "uuid-1",
  "name": "Company A",
  "is_active": true,
  "created_at": "2026-01-15T10:00:00.000Z",
  "user_count": 5,
  "api_key_count": 2
}
```

---

## Cache Management Endpoints

### 1. Get Cache Statistics
```http
GET /api/v1/cache/stats
```

**Response:**
```json
{
  "tenant_id": "uuid-here",
  "backend_type": "redis",
  "hits": 1500,
  "misses": 200,
  "hit_rate": 0.88,
  "total_keys": 45,
  "memory_used_mb": 15.2
}
```

### 2. Invalidate Tenant Cache
```http
DELETE /api/v1/cache/invalidate
```

**Response:**
```json
{
  "status": "success",
  "message": "All cache invalidated for tenant uuid-here",
  "tenant_id": "uuid-here"
}
```

### 3. Invalidate Operation Cache
```http
DELETE /api/v1/cache/invalidate/{operation}
```

**Example:** `DELETE /api/v1/cache/invalidate/dashboard_overview`

**Response:**
```json
{
  "status": "success",
  "message": "Cache invalidated for operation: dashboard_overview",
  "tenant_id": "uuid-here",
  "operation": "dashboard_overview"
}
```

### 4. Warm Cache
```http
POST /api/v1/cache/warm/{operation}
```

**Example:** `POST /api/v1/cache/warm/dashboard_overview`

**Response:**
```json
{
  "status": "success",
  "message": "Cache warmed for operation: dashboard_overview",
  "operation": "dashboard_overview"
}
```

---

## Next.js Integration Guide

### Complete Integration Example

#### 1. Environment Setup
```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=nex_your_api_key_here
```

#### 2. API Client Setup
```typescript
// lib/api-client.ts
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

export class NexarchClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string = API_BASE_URL, apiKey: string = API_KEY || '') {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || response.statusText);
    }

    return response.json();
  }

  // Dashboard methods
  async getDashboardOverview() {
    return this.request('/api/v1/dashboard/overview');
  }

  async getArchitectureMap() {
    return this.request('/api/v1/dashboard/architecture-map');
  }

  async getServices() {
    return this.request('/api/v1/dashboard/services');
  }

  async getTrends(hours: number = 24) {
    return this.request(`/api/v1/dashboard/trends?hours=${hours}`);
  }

  async getInsights() {
    return this.request('/api/v1/dashboard/insights');
  }

  // Ingestion methods
  async ingestSpan(span: any) {
    return this.request('/api/v1/ingest', {
      method: 'POST',
      body: JSON.stringify(span),
    });
  }

  async ingestBatch(spans: any[]) {
    return this.request('/api/v1/ingest/batch', {
      method: 'POST',
      body: JSON.stringify(spans),
    });
  }

  // AI Design methods
  async designNewArchitecture(requirements: any) {
    return this.request('/api/v1/ai-design/design-new', {
      method: 'POST',
      body: JSON.stringify(requirements),
    });
  }

  async optimizeArchitecture(request: any) {
    return this.request('/api/v1/ai-design/optimize-architecture', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
}

export const nexarchClient = new NexarchClient();
```

#### 3. SWR Hooks
```typescript
// hooks/useNexarch.ts
import useSWR from 'swr';
import { nexarchClient } from '@/lib/api-client';

export function useDashboardOverview() {
  return useSWR('dashboard-overview', () => nexarchClient.getDashboardOverview(), {
    refreshInterval: 30000, // Refresh every 30s
  });
}

export function useArchitectureMap() {
  return useSWR('architecture-map', () => nexarchClient.getArchitectureMap(), {
    refreshInterval: 60000, // Refresh every minute
  });
}

export function useServices() {
  return useSWR('services', () => nexarchClient.getServices());
}

export function useTrends(hours: number = 24) {
  return useSWR(['trends', hours], () => nexarchClient.getTrends(hours));
}

export function useInsights() {
  return useSWR('insights', () => nexarchClient.getInsights(), {
    refreshInterval: 120000, // Refresh every 2 minutes
  });
}
```

#### 4. Dashboard Page
```typescript
// pages/dashboard.tsx
import { useDashboardOverview, useArchitectureMap } from '@/hooks/useNexarch';
import { MetricCard } from '@/components/MetricCard';
import { ArchitectureMap } from '@/components/ArchitectureMap';

export default function Dashboard() {
  const { data: overview, error: overviewError } = useDashboardOverview();
  const { data: archMap, error: mapError } = useArchitectureMap();

  if (overviewError || mapError) {
    return <ErrorDisplay error={overviewError || mapError} />;
  }

  if (!overview || !archMap) {
    return <LoadingSpinner />;
  }

  return (
    <div className="dashboard-container">
      <h1>Architecture Dashboard</h1>
      
      <div className="metrics-grid">
        <MetricCard
          title="Total Services"
          value={overview.total_services}
          icon="🔧"
        />
        <MetricCard
          title="Health Score"
          value={overview.health_score}
          status={overview.health_score >= 80 ? 'good' : 'warning'}
          icon="❤️"
        />
        <MetricCard
          title="Error Rate"
          value={`${(overview.error_rate * 100).toFixed(2)}%`}
          status={overview.error_rate > 0.05 ? 'critical' : 'good'}
          icon="🚨"
        />
        <MetricCard
          title="Avg Latency"
          value={`${overview.avg_latency_ms}ms`}
          status={overview.avg_latency_ms > 500 ? 'warning' : 'good'}
          icon="⚡"
        />
      </div>

      <div className="architecture-section">
        <h2>Architecture Map</h2>
        <ArchitectureMap data={archMap} />
      </div>
    </div>
  );
}
```

#### 5. AI Design Page
```typescript
// pages/ai-design.tsx
import { useState } from 'react';
import { nexarchClient } from '@/lib/api-client';

export default function AIDesign() {
  const [loading, setLoading] = useState(false);
  const [designs, setDesigns] = useState([]);

  const handleDesign = async (formData: any) => {
    setLoading(true);
    try {
      const result = await nexarchClient.designNewArchitecture(formData);
      setDesigns(result);
    } catch (error) {
      console.error('Design failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-design-page">
      <h1>AI Architecture Designer</h1>
      <DesignForm onSubmit={handleDesign} />
      
      {loading && <LoadingSpinner />}
      
      <div className="designs-grid">
        {designs.map((design, idx) => (
          <DesignCard key={idx} design={design} />
        ))}
      </div>
    </div>
  );
}
```

#### 6. Automatic Telemetry Middleware
```typescript
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { nexarchClient } from '@/lib/api-client';

export async function middleware(request: NextRequest) {
  const startTime = Date.now();

  const response = NextResponse.next();

  // Send telemetry after response
  response.headers.set('x-trace-id', generateTraceId());
  
  // Send async (don't wait)
  sendTelemetry({
    trace_id: response.headers.get('x-trace-id'),
    span_id: generateSpanId(),
    service_name: 'nextjs-app',
    operation: `${request.method} ${request.nextUrl.pathname}`,
    kind: 'server',
    start_time: new Date(startTime).toISOString(),
    end_time: new Date().toISOString(),
    latency_ms: Date.now() - startTime,
    status_code: response.status,
    error: null,
    downstream: [],
  });

  return response;
}

async function sendTelemetry(data: any) {
  try {
    await nexarchClient.ingestSpan(data);
  } catch (error) {
    console.error('Failed to send telemetry:', error);
  }
}
```

---

## Error Handling

All endpoints follow consistent error format:

```json
{
  "detail": "Error message here"
}
```

**HTTP Status Codes:**
- `200`: Success
- `202`: Accepted (async processing)
- `400`: Bad Request
- `401`: Unauthorized
- `404`: Not Found
- `500`: Internal Server Error
- `503`: Service Unavailable

**Next.js Error Handling:**
```typescript
try {
  const data = await nexarchClient.getDashboardOverview();
} catch (error) {
  if (error.message.includes('401')) {
    // Redirect to login
    router.push('/login');
  } else {
    // Show error toast
    toast.error('Failed to load dashboard');
  }
}
```

---

## Rate Limiting

The API implements rate limiting:
- Default: 100 requests per minute per tenant
- Headers returned:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`

**Next.js Handling:**
```typescript
const response = await fetch(url, options);

if (response.status === 429) {
  const resetTime = response.headers.get('X-RateLimit-Reset');
  console.log(`Rate limited. Resets at: ${resetTime}`);
}
```

---

## Caching

Endpoints that support caching:
- `/api/v1/dashboard/overview` - 2 minutes
- `/api/v1/dashboard/architecture-map` - 5 minutes
- `/api/v1/architecture/current` - 5 minutes
- `/api/v1/workflows/generated` - 10 minutes
- `/api/v1/dashboard/insights` - 5 minutes

Use cache invalidation endpoints to force refresh.

---

## WebSocket Support (Future)

Coming soon: Real-time updates via WebSocket for:
- Live dashboard metrics
- Real-time architecture changes
- Alert notifications

---

## API Versioning

Current version: `v1`  
All endpoints use `/api/v1/` prefix

Future versions will use `/api/v2/`, etc., with backward compatibility.

---

## Support & Documentation

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

---

## Quick Start Checklist

1. ✅ **Setup Google OAuth:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project or select existing
   - Enable Google+ API
   - Create OAuth 2.0 Client ID credentials
   - Add authorized redirect URIs:
     - `https://api.modelix.world/auth/google/callback` (production)
     - `http://localhost:8000/auth/google/callback` (development)
   - Copy Client ID and Client Secret

2. ✅ **Configure Backend:**
   - Set environment variables in `.env`:
     ```env
     GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
     GOOGLE_CLIENT_SECRET=your-client-secret
     GOOGLE_REDIRECT_URI=https://api.modelix.world/auth/google/callback
     JWT_SECRET_KEY=your-secret-key-change-in-production
     ```

3. ✅ **Configure Frontend:**
   - Set environment variables in `.env.local`:
     ```env
     NEXT_PUBLIC_API_URL=https://api.modelix.world
     NEXT_PUBLIC_FRONTEND_URL=https://modelix.world
     ```

4. ✅ **Test Authentication:**
   - Check OAuth status: `GET /auth/google/status`
   - Test Google login flow: `GET /auth/google`
   - Verify token validation: `GET /auth/me` (with Bearer token)

5. ✅ **Create Tenant:** `POST /api/v1/admin/tenants`
6. ✅ **Save API key from response**
7. ✅ **Set API key in Next.js `.env.local`**
8. ✅ **Install API client:** Copy `lib/api-client.ts`
9. ✅ **Test connection:** `GET /api/v1/health`
10. ✅ **Start ingesting telemetry data:** `POST /api/v1/ingest`
11. ✅ **View dashboard:** `GET /api/v1/dashboard/overview`
12. ✅ **Explore architecture:** `GET /api/v1/dashboard/architecture-map`
13. ✅ **Get AI insights:** `GET /api/v1/dashboard/insights`
14. ✅ **Design with AI:** `POST /api/v1/ai-design/design-new`

---

**End of Documentation**
