# SparksBM - Quick Start Guide

## One-Command Startup

### Linux / Mac (Recommended)
```bash
./systemStart.sh
```

### Windows (No WSL Required!)
Option 1: Using Batch Script (Easiest)
```cmd
systemStart.bat
```

Option 2: Using PowerShell
```powershell
.\systemStart.ps1
```

Option 3: Using Git Bash
```bash
./systemStart.sh
```

Option 4: Using WSL (if you prefer)
```bash
wsl
./systemStart.sh
```

---

## Requirements

### All Platforms
- Docker (for PostgreSQL, Keycloak, RabbitMQ)
- Node.js (for frontend)
- Java 21 JDK (for ISMS backend)
- Python 3 (for NotebookLLM API)

### Windows
- No WSL required! Scripts work natively
- PowerShell (comes with Windows) OR Command Prompt

---

## What Gets Started

- ISMS Platform
  - Frontend: http://localhost:3001
  - Backend: http://localhost:8070
  - Keycloak: http://localhost:8080

- NotebookLLM
  - Frontend: http://localhost:3002
  - API: http://localhost:8000

---

## Database Setup

Automatic! No manual setup needed.

- PostgreSQL starts via Docker
- Databases created automatically
- All credentials pre-configured

---

## Troubleshooting

### Linux/Mac
- Make script executable: `chmod +x systemStart.sh`
- Check Docker: `docker ps`
- Check logs: `tail -f /tmp/sparksbm-isms.log`

### Windows
- Check Docker Desktop is running
- All dependencies checked automatically by scripts
- Check logs in %TEMP% folder

---

## Notes

- Linux is recommended - Most powerful and native support
- Mac works great - Same bash scripts
- Windows works natively - No WSL required
