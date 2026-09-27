#!/bin/bash
# Nexarch Server Startup Script for Linux/Mac

echo "🚀 Starting Nexarch Server..."
echo ""

# Check if in correct directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the Server directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt --quiet

# Check if database exists, create if not
if [ ! -f "nexarch.db" ]; then
    echo "🗄️  Initializing database..."
    python -c "from db.base import init_db; init_db(); print('✓ Database initialized')"
fi

# Start server
echo ""
echo "✅ Starting Nexarch Server on http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo "🔧 Health Check: http://localhost:8000/api/v1/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python main.py
