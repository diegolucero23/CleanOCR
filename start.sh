#!/bin/bash

# CleanOCR Seamless Launcher (Mac/Linux)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}CleanOCR Launcher${NC}"
echo "--------------------------------"

# 1. Check Docker
echo -n "[1/4] Checking Docker status... "
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}FAILED${NC}"
    echo ""
    echo -e "${RED}[ERROR] Docker is not running.${NC}"
    echo "Please open Docker Desktop (or start the docker daemon) and try again."
    read -p "Press Enter to exit..."
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# 2. Check .env
echo -n "[2/4] Checking configuration... "
if [ ! -f .env ]; then
    echo -e "${YELLOW}MISSING${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo ""
        echo -e "${YELLOW}[SETUP] First Run Configuration${NC}"
        echo "We have created a '.env' file for you."
        echo "ACTION REQUIRED:"
        echo "1. Open the file '.env' in your text editor."
        echo "2. Paste your Google API Key."
        echo "3. Run this script again."
        exit 1
    else
        echo -e "${RED}[ERROR] .env.example not found!${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}FOUND${NC}"

# 3. Launch
echo "[3/4] Launching Containers..."
docker-compose up -d --build
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Docker Compose failed.${NC}"
    exit 1
fi

# 4. Wait and Open
echo "[4/4] Waiting for API..."
until curl -s http://localhost:8000/docs > /dev/null; do
    echo -n "."
    sleep 2
done

# 4.5 Start Frontend
echo ""
echo "[5/5] Starting Frontend Server..."
cd frontend && npm install && npm run dev &
cd ..

echo ""
echo -e "${GREEN}🚀 CleanOCR is Ready!${NC}"
echo "Opening browser..."

# Cross-platform open
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:5173
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:5173 2>/dev/null || echo "Please open http://localhost:5173"
fi

echo ""
echo "Press [ENTER] to stop the server and exit."
read
echo "Stopping..."
docker-compose down
