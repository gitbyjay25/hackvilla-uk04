import requests
import uuid
import time


base = 'http://127.0.0.1:8013'
email = f'sysarch_{uuid.uuid4().hex[:8]}@nex.dev'
pwd = 'TestPass123!'
s = requests.Session()

r = s.post(base + '/auth/signup', json={'email': email, 'password': pwd, 'full_name': 'Sys Arch'}, timeout=60)
print('signup', r.status_code)
r.raise_for_status()
tok = r.json().get('access_token')
h = {'Authorization': f'Bearer {tok}'}

r = s.get(base + '/api/v1/system-architecture/github/install-url', headers=h, timeout=60)
print('install_url', r.status_code)
r.raise_for_status()

r = s.post(base + '/api/v1/system-architecture/repositories/connect', headers=h, json={
    'owner': 'local',
    'repo_name': 'Nexarch-Server-API',
    'default_branch': 'main',
    'is_private': True,
    'is_monorepo': True,
    'local_repo_path': 'C:/Users/Modelix/Documents/GitHub/Nexarch/Server/api'
}, timeout=120)
print('connect', r.status_code)
r.raise_for_status()
repo_id = r.json().get('repository_id')

r = s.post(base + f'/api/v1/system-architecture/repositories/{repo_id}/snapshot', headers=h, json={'use_default_branch': True}, timeout=180)
print('snapshot', r.status_code)
r.raise_for_status()
snap = r.json().get('snapshot_id')

r = s.post(base + f'/api/v1/system-architecture/repositories/{repo_id}/analyze', headers=h, json={
    'snapshot_id': snap,
    'mode': 'sync',
    'cost_weight': 30,
    'scalability_weight': 35,
    'performance_weight': 35
}, timeout=240)
print('analyze', r.status_code)
r.raise_for_status()
data = r.json()
print('doc', data.get('architecture_document_id'))
var_ids = data.get('variant_ids', [])
print('variants', len(var_ids))

if var_ids:
    vid = var_ids[0]
    r = s.post(base + '/api/v1/alpha-code/plan-deeply', headers=h, json={'architecture_variant_id': vid}, timeout=120)
    print('plan', r.status_code)
    r.raise_for_status()
    plan_id = r.json().get('deep_plan_report_id')

    r = s.post(base + '/api/v1/alpha-code/runs', headers=h, json={
        'architecture_variant_id': vid,
        'deep_plan_report_id': plan_id
    }, timeout=120)
    print('run', r.status_code)
    r.raise_for_status()
    run_id = r.json().get('run_id')
    print('run_id', run_id)

    status = 'in_progress'
    for _ in range(20):
        time.sleep(3)
        r = s.get(base + f'/api/v1/alpha-code/runs/{run_id}', headers=h, timeout=60)
        r.raise_for_status()
        status = r.json().get('status')
        print('run_status', r.status_code, status)
        if status in ('completed', 'failed'):
            break

    if status == 'completed':
        r = s.get(base + f'/api/v1/alpha-code/runs/{run_id}/download', headers=h, timeout=120)
        print('download', r.status_code)
        r.raise_for_status()
