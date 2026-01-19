#!/bin/bash

# Quick Start Script: Test Redis + /assist Endpoint Locally
# This script sets up Redis, installs dependencies, and runs tests

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Redis + /assist Endpoint Quick Start${NC}"
echo -e "${BLUE}============================================${NC}\n"

# Step 1: Check if Docker is installed
echo -e "${YELLOW}Step 1: Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first:${NC}"
    echo -e "${RED}   https://docs.docker.com/get-docker/${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker found${NC}\n"

# Step 2: Start Redis container
echo -e "${YELLOW}Step 2: Starting Redis container...${NC}"
if docker ps | grep -q redis-copilot; then
    echo -e "${GREEN}✅ Redis already running${NC}"
else
    docker run -d --name redis-copilot -p 6379:6379 redis:7-alpine
    echo -e "${GREEN}✅ Redis started on port 6379${NC}"
fi

# Test Redis connection
sleep 2
if docker exec redis-copilot redis-cli ping | grep -q PONG; then
    echo -e "${GREEN}✅ Redis responding to PING${NC}\n"
else
    echo -e "${RED}❌ Redis not responding${NC}"
    exit 1
fi

# Step 3: Install Python dependencies
echo -e "${YELLOW}Step 3: Installing Python dependencies...${NC}"
cd backend
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}✅ Dependencies installed${NC}\n"

# Step 4: Check .env file
echo -e "${YELLOW}Step 4: Checking .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Copying from .env.example...${NC}"
    cp .env.example .env
    echo -e "${RED}⚠️  IMPORTANT: Edit backend/.env and set OPENAI_API_KEY${NC}"
    echo -e "${RED}⚠️  Then run this script again.${NC}"
    exit 1
fi

# Check if OPENAI_API_KEY is set
if grep -q "OPENAI_API_KEY=sk-" .env; then
    echo -e "${GREEN}✅ .env file configured${NC}\n"
else
    echo -e "${RED}❌ OPENAI_API_KEY not set in .env file${NC}"
    echo -e "${RED}   Edit backend/.env and set your OpenAI API key${NC}"
    exit 1
fi

# Step 5: Start backend server in background
echo -e "${YELLOW}Step 5: Starting FastAPI backend...${NC}"
uvicorn main:app --reload --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
BACKEND_PID=$!

echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
echo -e "${BLUE}   Waiting for backend to be ready...${NC}"

# Wait for backend to start
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend ready${NC}\n"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Backend failed to start${NC}"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Step 6: Run tests
echo -e "${YELLOW}Step 6: Running tests...${NC}\n"
python test_redis_assist.py

TEST_RESULT=$?

# Cleanup
echo -e "\n${YELLOW}Cleanup: Stopping backend...${NC}"
kill $BACKEND_PID 2>/dev/null || true
echo -e "${GREEN}✅ Backend stopped${NC}\n"

# Summary
echo -e "${BLUE}============================================${NC}"
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed! Ready for deployment.${NC}"
    echo -e "${BLUE}============================================${NC}\n"
    echo -e "${GREEN}Next steps:${NC}"
    echo -e "  1. Deploy Redis on Railway (see RAILWAY_REDIS_DEPLOYMENT.md)"
    echo -e "  2. Set REDIS_URL environment variable in Railway"
    echo -e "  3. Deploy backend to Railway"
    echo -e "  4. Test /assist endpoint with: curl https://your-app.railway.app/api/assist/health"
else
    echo -e "${RED}❌ Some tests failed. Check output above.${NC}"
    echo -e "${BLUE}============================================${NC}\n"
    echo -e "${YELLOW}Troubleshooting:${NC}"
    echo -e "  - Check backend logs: tail -f backend/logs/*.log"
    echo -e "  - Check Redis: docker logs redis-copilot"
    echo -e "  - Verify .env: cat backend/.env"
fi

echo -e "\n${BLUE}To stop Redis:${NC} docker stop redis-copilot"
echo -e "${BLUE}To remove Redis:${NC} docker rm redis-copilot\n"

exit $TEST_RESULT
