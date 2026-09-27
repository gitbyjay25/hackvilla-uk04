import os, json, sqlite3, requests
from pathlib import Path
from datetime import datetime
from jose import jwt

BASE = "http://127.0.0.1:8000"
root = Path(r"C:/Users/Modelix/Documents/GitHub/Nexarch")
server = root / "Server"
env_path = server / ".env"

def parse_env(path):
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k,v = line.split("=",1)
        data[k.strip()] = v.strip()
    return data

env = parse_env(env_path)
admin_key = env.get("ADMIN_SECRET_KEY", "")
jwt_secret = env.get("JWT_SECRET_KEY", "")

def req(method, path, **kw):
    timeout = kw.pop("timeout", 60)
    try:
        r = requests.request(method, BASE + path, timeout=timeout, **kw)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"

results = []

def check(name, method, path, expected=(200,), **kw):
    code, text = req(method, path, **kw)
    ok = code in expected
    results.append((name, ok, code, path, text[:180]))
    return code, text

# Public
check("health", "GET", "/api/v1/health")
check("health_detailed", "GET", "/api/v1/health/detailed")
check("system_info", "GET", "/api/v1/system/info")
check("system_capabilities", "GET", "/api/v1/system/capabilities")
check("openapi", "GET", "/openapi.json")

# Admin create tenant
tenant_name = f"Endpoint Smoke {datetime.utcnow().strftime('%H%M%S')}"
code, text = check(
    "admin_create_tenant", "POST", "/api/v1/admin/tenants", expected=(200,),
    headers={"X-Admin-Key": admin_key},
    json={"name": tenant_name, "admin_email": f"smoke_{datetime.utcnow().strftime('%H%M%S')}@nexarch.dev"}
)
api_key = None
tenant_id = None
if code == 200:
    data = json.loads(text)
    api_key = data.get("api_key")
    tenant_id = data.get("id")

# API key endpoints
if api_key:
    h = {"X-API-Key": api_key}
    check("ingest_stats", "GET", "/api/v1/ingest/stats", headers=h)
    check("architecture_current", "GET", "/api/v1/architecture/current", headers=h)
    check("architecture_issues", "GET", "/api/v1/architecture/issues", headers=h)
    check("workflows_generated", "GET", "/api/v1/workflows/generated", headers=h)
    check("workflows_comparison", "GET", "/api/v1/workflows/comparison", headers=h)
    check("workflow_graph", "GET", "/api/v1/workflows/architecture/graph", headers=h)

    # discovery endpoints
    discovery = {
        "service_name": "smoke-service",
        "service_type": "fastapi",
        "version": "1.0.0",
        "endpoints": [{"path": "/health", "methods": ["GET"]}],
        "databases": [],
        "external_services": [],
        "middleware": [],
        "dependencies": {},
        "architecture_patterns": {},
        "discovered_at": datetime.utcnow().isoformat()
    }
    check("ingest_arch_discovery", "POST", "/api/v1/ingest/architecture-discovery", expected=(202,), headers=h, json=discovery)
    check("get_arch_discoveries", "GET", "/api/v1/ingest/architecture-discoveries", headers=h)

# Build JWT for tenant user by reading sqlite (local smoke only)
if tenant_id and jwt_secret:
    db_path = server / "nexarch.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1", (tenant_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            user_id = row[0]
            token = jwt.encode({"sub": user_id}, jwt_secret, algorithm="HS256")
            jh = {"Authorization": f"Bearer {token}"}
            check("dashboard_overview", "GET", "/api/v1/dashboard/overview", headers=jh)
            check("dashboard_map", "GET", "/api/v1/dashboard/architecture-map", headers=jh)
            check("dashboard_services", "GET", "/api/v1/dashboard/services", headers=jh)
            check("dashboard_health", "GET", "/api/v1/dashboard/health", headers=jh)
            check("dashboard_trends", "GET", "/api/v1/dashboard/trends", headers=jh)
            check("system_stats", "GET", "/api/v1/system/stats", headers=jh)

passed = sum(1 for _,ok,_,_,_ in results if ok)
failed = len(results) - passed
print(f"TOTAL={len(results)} PASS={passed} FAIL={failed}")
for name, ok, code, path, preview in results:
    status = "PASS" if ok else "FAIL"
    print(f"{status:4} {code:3} {path:45} {name}")
    if not ok:
        print(f"      {preview}")
