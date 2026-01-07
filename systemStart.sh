#!/bin/bash
#═══════════════════════════════════════════════════════════════════════════════
#  SparksBM - Complete System Startup (One Command)
#  Uses existing configuration - no setup needed
#═══════════════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
ORANGE='\033[0;33m'
NC='\033[0m'

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo -e "${ORANGE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${ORANGE}║${NC}           ${ORANGE}⚡ SparksBM${NC} - Starting Complete System              ${ORANGE}║${NC}"
echo -e "${ORANGE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

#───────────────────────────────────────────────────────────────────────────────
# Check Dependencies
#───────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}[1/5]${NC} Checking dependencies..."

MISSING_DEPS=0

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗${NC} Docker not found"
    echo -e "${YELLOW}   Install: https://www.docker.com/products/docker-desktop${NC}"
    MISSING_DEPS=1
else
    echo -e "${GREEN}✓${NC} Docker"
fi

if ! command -v node &> /dev/null; then
    echo -e "${RED}✗${NC} Node.js not found"
    echo -e "${YELLOW}   Install: https://nodejs.org/${NC}"
    MISSING_DEPS=1
else
    echo -e "${GREEN}✓${NC} Node.js"
fi

if ! command -v java &> /dev/null; then
    echo -e "${RED}✗${NC} Java not found"
    echo -e "${YELLOW}   Install Java 21 JDK: https://adoptium.net/${NC}"
    MISSING_DEPS=1
else
    echo -e "${GREEN}✓${NC} Java"
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python3 not found"
    echo -e "${YELLOW}   Install: https://www.python.org/downloads/${NC}"
    MISSING_DEPS=1
else
    echo -e "${GREEN}✓${NC} Python3"
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo ""
    echo -e "${RED}Please install missing dependencies before continuing.${NC}"
    exit 1
fi

echo ""

#───────────────────────────────────────────────────────────────────────────────
# Start ISMS Platform (uses existing config)
#───────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}[2/5]${NC} Starting ISMS Platform..."
cd "$SCRIPT_DIR/SparksbmISMS"
chmod +x start-sparksbm.sh 2>/dev/null || true
./start-sparksbm.sh > /tmp/sparksbm-isms.log 2>&1 &
ISMS_PID=$!
echo -e "${GREEN}✓${NC} ISMS Platform starting..."
echo ""

#───────────────────────────────────────────────────────────────────────────────
# Start NotebookLLM (uses existing config)
#───────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}[3/5]${NC} Starting NotebookLLM..."
cd "$SCRIPT_DIR/NotebookLLM"
chmod +x start.sh 2>/dev/null || true
./start.sh > /tmp/sparksbm-notebookllm.log 2>&1 &
NOTEBOOKLLM_PID=$!
echo -e "${GREEN}✓${NC} NotebookLLM starting..."
echo ""

#───────────────────────────────────────────────────────────────────────────────
# Wait and show status
#───────────────────────────────────────────────────────────────────────────────
echo -e "${BLUE}Waiting for services...${NC}"
sleep 10

echo ""
echo -e "${ORANGE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${ORANGE}║${NC}  ${GREEN}SparksBM System Starting!${NC}                                ${ORANGE}║${NC}"
echo -e "${ORANGE}╠═══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${ORANGE}║${NC}                                                               ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  ${BLUE}ISMS Platform:${NC}                                                ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}    🌐 Frontend:    ${GREEN}http://localhost:3001${NC}                      ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}    🔧 Backend:     ${GREEN}http://localhost:8070${NC}                        ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}    🔐 Keycloak:    ${GREEN}http://localhost:8080${NC}                        ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}                                                               ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}  ${BLUE}NotebookLLM:${NC}                                                 ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}    🌐 Frontend:    ${GREEN}http://localhost:3002${NC}                      ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}    🔧 API:         ${GREEN}http://localhost:8000${NC}                        ${ORANGE}║${NC}"
echo -e "${ORANGE}║${NC}                                                               ${ORANGE}║${NC}"
echo -e "${ORANGE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Services are starting in background...${NC}"
echo -e "${YELLOW}Check logs: tail -f /tmp/sparksbm-isms.log${NC}"
echo -e "${YELLOW}Check logs: tail -f /tmp/sparksbm-notebookllm.log${NC}"
echo ""
echo -e "${YELLOW}Press ${RED}Ctrl+C${YELLOW} to stop all services${NC}"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Stopping all services...${NC}"
    
    # Stop NotebookLLM
    pkill -f "NotebookLLM.*start.sh" 2>/dev/null || true
    pkill -f "uvicorn.*api.main:app" 2>/dev/null || true
    pkill -f "nuxi dev.*NotebookLLM" 2>/dev/null || true
    
    # Stop ISMS
    pkill -f "SparksbmISMS.*start-sparksbm.sh" 2>/dev/null || true
    pkill -f "gradlew.*bootRun" 2>/dev/null || true
    pkill -f "veo-rest" 2>/dev/null || true
    pkill -f "nuxi dev.*verinice-veo-web" 2>/dev/null || true
    
    # Stop Docker
    cd "$SCRIPT_DIR/SparksbmISMS/keycloak" 2>/dev/null && \
        docker compose down 2>/dev/null || docker-compose down 2>/dev/null || true
    
    echo -e "${GREEN}✓${NC} All services stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep running
wait
