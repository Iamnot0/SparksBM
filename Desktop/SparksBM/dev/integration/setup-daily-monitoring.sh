#!/bin/bash
# Setup Daily Monitoring - Automated Test Scheduling
# 
# This script sets up automated daily monitoring using cron.
# It creates log directories, sets up cron jobs, and tests the configuration.
#
# Usage:
#   chmod +x dev/integration/setup-daily-monitoring.sh
#   ./dev/integration/setup-daily-monitoring.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/clay/Desktop/SparksBM"
LOG_DIR="$PROJECT_DIR/dev/logs/monitoring"
REPORT_DIR="$PROJECT_DIR/dev/reports"
MONITOR_SCRIPT="$PROJECT_DIR/dev/integration/dailyMonitor.py"

echo ""
echo "========================================================================"
echo "  Daily Monitoring Setup - SparksBM System"
echo "========================================================================"
echo ""

# 1. Check if running as user (not root)
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}❌ Please run as regular user, not root${NC}"
    echo "   Usage: ./setup-daily-monitoring.sh"
    exit 1
fi

echo -e "${BLUE}[1/6]${NC} Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3 found:${NC} $(python3 --version)"

# Check requests library
if ! python3 -c "import requests" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  requests library not found, installing...${NC}"
    pip3 install requests
fi
echo -e "${GREEN}✅ Python dependencies OK${NC}"

# 2. Create directories
echo ""
echo -e "${BLUE}[2/6]${NC} Creating log directories..."

mkdir -p "$LOG_DIR"
mkdir -p "$REPORT_DIR"

echo -e "${GREEN}✅ Created:${NC}"
echo "   - $LOG_DIR"
echo "   - $REPORT_DIR"

# 3. Make script executable
echo ""
echo -e "${BLUE}[3/6]${NC} Setting script permissions..."

chmod +x "$MONITOR_SCRIPT"
echo -e "${GREEN}✅ Made dailyMonitor.py executable${NC}"

# 4. Test the monitoring script
echo ""
echo -e "${BLUE}[4/6]${NC} Testing monitoring script..."
echo ""

if python3 "$MONITOR_SCRIPT" 2>&1 | head -20; then
    echo ""
    echo -e "${GREEN}✅ Monitoring script test successful${NC}"
else
    echo ""
    echo -e "${RED}❌ Monitoring script test failed${NC}"
    echo "   Please check if all services are running:"
    echo "   - NotebookLLM API (port 8000)"
    echo "   - SparksBM Backend (port 8070)"
    echo "   - Keycloak (port 8080)"
    exit 1
fi

# 5. Setup cron jobs
echo ""
echo -e "${BLUE}[5/6]${NC} Setting up automated scheduling..."

# Backup existing crontab
crontab -l > /tmp/crontab.backup 2>/dev/null || true

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "dailyMonitor.py"; then
    echo -e "${YELLOW}⚠️  Cron job already exists, skipping...${NC}"
else
    # Add cron job
    (crontab -l 2>/dev/null; echo "") | crontab -
    (crontab -l 2>/dev/null; echo "# SparksBM Daily Monitoring - Added $(date)") | crontab -
    (crontab -l 2>/dev/null; echo "0 9 * * * cd $PROJECT_DIR && python3 dev/integration/dailyMonitor.py >> $LOG_DIR/daily_\$(date +\\%Y\\%m\\%d).log 2>&1") | crontab -
    
    echo -e "${GREEN}✅ Added cron job:${NC}"
    echo "   Schedule: Every day at 9:00 AM"
    echo "   Log: $LOG_DIR/daily_YYYYMMDD.log"
fi

# 6. Display cron jobs
echo ""
echo -e "${BLUE}[6/6]${NC} Current cron schedule:"
echo ""
crontab -l | grep -A 1 "SparksBM" || echo "No SparksBM cron jobs found"

# Summary
echo ""
echo "========================================================================"
echo "  Setup Complete!"
echo "========================================================================"
echo ""
echo -e "${GREEN}✅ Daily monitoring is now configured${NC}"
echo ""
echo "Configuration:"
echo "  - Schedule: Every day at 9:00 AM"
echo "  - Log Directory: $LOG_DIR"
echo "  - Report Directory: $REPORT_DIR"
echo ""
echo "Manual Commands:"
echo ""
echo "  Run monitoring now:"
echo "    ${BLUE}python3 dev/integration/dailyMonitor.py${NC}"
echo ""
echo "  Run with write operations (creates test objects):"
echo "    ${BLUE}python3 dev/integration/dailyMonitor.py --write${NC}"
echo ""
echo "  View latest log:"
echo "    ${BLUE}tail -100 $LOG_DIR/daily_\$(date +%Y%m%d).log${NC}"
echo ""
echo "  View all logs:"
echo "    ${BLUE}ls -lh $LOG_DIR/${NC}"
echo ""
echo "  Edit cron schedule:"
echo "    ${BLUE}crontab -e${NC}"
echo ""
echo "  Remove monitoring cron job:"
echo "    ${BLUE}crontab -e${NC} (then delete the SparksBM lines)"
echo ""
echo "  Restore crontab backup:"
echo "    ${BLUE}crontab /tmp/crontab.backup${NC}"
echo ""
echo "========================================================================"
echo ""
