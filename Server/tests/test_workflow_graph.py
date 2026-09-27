"""Quick test for the new workflow architecture graph endpoint"""
import requests
import time

BASE_URL = "http://localhost:8000"

# Create tenant with unique email
timestamp = int(time.time())
print("Creating tenant...")
r = requests.post(f'{BASE_URL}/api/v1/admin/tenants', json={
    'name': f'TestGraph{timestamp}',
    'admin_email': f'testgraph{timestamp}@example.com'
})
if r.status_code != 200:
    print(f"Error creating tenant: {r.text}")
    exit(1)
data = r.json()
api_key = data['api_key']
tenant_id = data['id']
print(f'Created tenant with API key: {api_key[:20]}...')

# Generate some sample data first
print("Generating sample data...")
r_demo = requests.post(f'{BASE_URL}/demo/generate-sample-data?count=20', 
                       headers={'X-API-Key': api_key})
print(f'Sample data generation status: {r_demo.status_code}')

# Test the new endpoint
print("Testing /api/v1/workflows/architecture/graph...")
r2 = requests.get(f'{BASE_URL}/api/v1/workflows/architecture/graph', 
                  headers={'X-API-Key': api_key})
print(f'Status: {r2.status_code}')

if r2.status_code == 200:
    result = r2.json()
    current = result.get('current_architecture', {})
    variants = result.get('generated_workflows', [])
    
    print(f'\n=== ENDPOINT TEST SUCCESSFUL ===')
    print(f'current_architecture.workflow_id: {current.get("workflow_id")}')
    print(f'current_architecture.trigger: {current.get("trigger")}')
    print(f'current_architecture.nodes count: {len(current.get("nodes", []))}')
    print(f'current_architecture.edges count: {len(current.get("edges", []))}')
    print(f'current_architecture.tech_stack: {current.get("tech_stack")}')
    print(f'generated_workflows count: {len(variants)}')
    
    for i, variant in enumerate(variants):
        print(f'\n  Variant {i+1}: {variant.get("workflow_id")}')
        print(f'    Description: {variant.get("description", "")[:60]}...')
        print(f'    Nodes: {len(variant.get("nodes", []))}')
else:
    print(f'Error: {r2.text}')
