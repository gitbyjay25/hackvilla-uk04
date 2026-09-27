# Nexarch SDK Authentication Guide

## Getting Your API Key

1. Log in to your Nexarch account at https://app.modelix.world
2. Navigate to the **API Keys** section in the top menu
3. Click **Generate New Key**
4. Give your key a descriptive name (e.g., "Production App", "Development")
5. **Copy the key immediately** - it won't be shown again!

## Using Your API Key

### Python with requests

```python
import requests

API_KEY = "your_api_key_here"  # Replace with your actual API key
BASE_URL = "https://api.modelix.world"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Example: Get architecture overview
response = requests.get(
    f"{BASE_URL}/api/v1/architecture",
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    print(f"Services: {data.get('services_count')}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### Python with Nexarch SDK

```python
from nexarch import NexarchClient

# Initialize client with your API key
client = NexarchClient(
    api_key="your_api_key_here",
    base_url="https://api.modelix.world"
)

# Ingest telemetry data
client.ingest_spans([
    {
        "trace_id": "abc123",
        "span_id": "span001",
        "name": "api.get_user",
        "service_name": "user-service",
        "duration": 45.2,
        "timestamp": "2024-01-15T10:30:00Z"
    }
])

# Get architecture insights
architecture = client.get_architecture()
print(f"Total Services: {architecture['services_count']}")

# Get dashboard overview
dashboard = client.get_dashboard_overview()
print(f"Total Requests: {dashboard['total_requests']}")
```

### cURL

```bash
curl -X GET "https://api.modelix.world/api/v1/architecture" \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json"
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_KEY = 'your_api_key_here';
const BASE_URL = 'https://api.modelix.world';

const headers = {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
};

// Get architecture overview
axios.get(`${BASE_URL}/api/v1/architecture`, { headers })
    .then(response => {
        console.log('Services:', response.data.services_count);
    })
    .catch(error => {
        console.error('Error:', error.response?.data || error.message);
    });
```

## Security Best Practices

1. **Never commit API keys to version control**
   - Use environment variables or secret management systems
   - Add `.env` files to `.gitignore`

2. **Rotate keys regularly**
   - Generate new keys periodically
   - Revoke old keys after rotation

3. **Use separate keys for different environments**
   - Create separate keys for development, staging, and production
   - Name them clearly (e.g., "Production Backend", "Dev Testing")

4. **Monitor key usage**
   - Check the "Last Used" column in the API Keys dashboard
   - Revoke any keys that show suspicious activity

5. **Revoke compromised keys immediately**
   - If you suspect a key has been exposed, revoke it right away
   - Generate a new key for the affected service

## Environment Variables

### Python (.env file)

```bash
NEXARCH_API_KEY=your_api_key_here
NEXARCH_BASE_URL=https://api.modelix.world
```

```python
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('NEXARCH_API_KEY')
BASE_URL = os.getenv('NEXARCH_BASE_URL')
```

### Node.js (.env file)

```bash
NEXARCH_API_KEY=your_api_key_here
NEXARCH_BASE_URL=https://api.modelix.world
```

```javascript
require('dotenv').config();

const API_KEY = process.env.NEXARCH_API_KEY;
const BASE_URL = process.env.NEXARCH_BASE_URL;
```

## Available Endpoints

All endpoints require the `X-API-Key` header:

### Telemetry Ingestion
- `POST /api/v1/ingest/spans` - Ingest trace spans
- `POST /api/v1/ingest/batch` - Batch ingest multiple spans

### Architecture
- `GET /api/v1/architecture` - Get architecture overview
- `GET /api/v1/architecture/services` - List all services
- `GET /api/v1/architecture/dependencies` - Get service dependencies

### Dashboard
- `GET /api/v1/dashboard/overview` - Dashboard statistics
- `GET /api/v1/dashboard/trends` - Performance trends
- `GET /api/v1/dashboard/health` - System health metrics

### Workflows
- `GET /api/v1/workflows` - List workflows
- `POST /api/v1/workflows/analyze` - Analyze workflow patterns

## Troubleshooting

### 401 Unauthorized
- Check that your API key is correct
- Verify the key hasn't been revoked
- Ensure you're using the `X-API-Key` header

### 403 Forbidden
- Your key may not have permissions for this endpoint
- Check your tenant/account status

### 404 Not Found
- Verify the endpoint URL is correct
- Check the API version in the URL

### Rate Limiting
- API keys are subject to rate limits
- Check response headers for rate limit status
- Implement exponential backoff for retries

## Support

For help with API key management:
- Email: support@modelix.world
- Documentation: https://docs.modelix.world
- Dashboard: https://app.modelix.world/api-keys
