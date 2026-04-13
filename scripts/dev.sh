#!/bin/bash
# QUAN Recovery - Development Environment Launcher
# Starts both backend and frontend with one command

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "======================================"
echo "  QUAN Recovery - Development Server"
echo "======================================"
echo -e "${NC}"

# Check if running from project root
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Parse arguments
SEED_DATA=false
RESET_DB=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --seed)
            SEED_DATA=true
            shift
            ;;
        --reset)
            RESET_DB=true
            SEED_DATA=true
            shift
            ;;
        --help)
            echo "Usage: ./scripts/dev.sh [options]"
            echo ""
            echo "Options:"
            echo "  --seed    Seed the database with test data"
            echo "  --reset   Reset database and seed with fresh data"
            echo "  --help    Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed.${NC}"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is required but not installed.${NC}"
    exit 1
fi

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}npm is required but not installed.${NC}"
    exit 1
fi

echo -e "${GREEN}All dependencies found!${NC}"

# Install Python dependencies if needed
if [ ! -d ".venv" ] && [ ! -f "quan/__pycache__" ]; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -e ".[dev]" --quiet
fi

# Initialize database
echo -e "${YELLOW}Initializing database...${NC}"
python3 -c "from quan.database import init_db_sync; init_db_sync()"
echo -e "${GREEN}Database initialized!${NC}"

# Seed data if requested
if [ "$RESET_DB" = true ]; then
    echo -e "${YELLOW}Resetting and seeding database...${NC}"
    python3 scripts/seed_data.py --reset --count 1000
elif [ "$SEED_DATA" = true ]; then
    echo -e "${YELLOW}Seeding database with test data...${NC}"
    python3 scripts/seed_data.py --count 1000
fi

# Install frontend dependencies if needed
if [ ! -d "dashboard/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    cd dashboard && npm install --silent && cd ..
fi

# Create .env file for frontend if it doesn't exist
if [ ! -f "dashboard/.env.local" ]; then
    echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > dashboard/.env.local
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill $API_PID 2>/dev/null || true
    kill $DASHBOARD_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start API server
echo -e "${BLUE}Starting API server on http://localhost:8000${NC}"
python3 -m uvicorn quan.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# Wait a bit for API to start
sleep 2

# Start dashboard
echo -e "${BLUE}Starting dashboard on http://localhost:3000${NC}"
cd dashboard && npm run dev &
DASHBOARD_PID=$!
cd ..

echo ""
echo -e "${GREEN}======================================"
echo "  Development servers are running!"
echo "======================================"
echo ""
echo "  API:       http://localhost:8000"
echo "  Dashboard: http://localhost:3000"
echo "  API Docs:  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all servers"
echo -e "======================================${NC}"
echo ""

# Wait for processes
wait $API_PID $DASHBOARD_PID
