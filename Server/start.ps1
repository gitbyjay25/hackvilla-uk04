# Nexarch Server Startup Script
# Run this to start the server after installing dependencies

Write-Host "🚀 Starting Nexarch Server..." -ForegroundColor Cyan
Write-Host ""

# Check if in correct directory
if (-Not (Test-Path "main.py")) {
    Write-Host "❌ Error: Please run this script from the Server directory" -ForegroundColor Red
    exit 1
}

# Check if virtual environment exists
if (-Not (Test-Path ".venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "📥 Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

# Check if database exists, create if not
if (-Not (Test-Path "nexarch.db")) {
    Write-Host "🗄️  Initializing database..." -ForegroundColor Yellow
    python -c "from db.base import init_db; init_db(); print('✓ Database initialized')"
}

# Start server
Write-Host ""
Write-Host "✅ Starting Nexarch Server on http://localhost:8000" -ForegroundColor Green
Write-Host "📚 API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🔧 Health Check: http://localhost:8000/api/v1/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python main.py
