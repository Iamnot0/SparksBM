# SparksBM - Complete System Startup (Windows PowerShell - No WSL)
# Uses existing configuration - no setup needed

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║           ⚡ SparksBM - Starting Complete System              ║" -ForegroundColor Yellow
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check dependencies
Write-Host "[1/5] Checking dependencies..." -ForegroundColor Cyan
$missing = @()
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { $missing += "Docker" }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { $missing += "Node.js" }
if (-not (Get-Command java -ErrorAction SilentlyContinue)) { $missing += "Java" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $missing += "Python" }

if ($missing.Count -gt 0) {
    Write-Host "✗ Missing: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Please install missing dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "✓ All dependencies OK" -ForegroundColor Green
Write-Host ""

# Start Docker
Write-Host "[2/5] Starting Docker services..." -ForegroundColor Cyan
Set-Location "$ScriptDir\SparksbmISMS\keycloak"
docker compose up -d
Set-Location $ScriptDir
Write-Host "✓ Docker services starting..." -ForegroundColor Green
Write-Host ""

# Start ISMS Backend
Write-Host "[3/5] Starting ISMS Backend..." -ForegroundColor Cyan
Set-Location "$ScriptDir\SparksbmISMS\verinice-veo"
Start-Process -FilePath ".\gradlew.bat" -ArgumentList "veo-rest:bootRun", "-PspringProfiles=local" -WindowStyle Hidden
Set-Location $ScriptDir
Write-Host "✓ ISMS Backend starting..." -ForegroundColor Green
Write-Host ""

# Start ISMS Frontend
Write-Host "[4/5] Starting ISMS Frontend..." -ForegroundColor Cyan
Set-Location "$ScriptDir\SparksbmISMS\verinice-veo-web"
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WindowStyle Hidden
Set-Location $ScriptDir
Write-Host "✓ ISMS Frontend starting..." -ForegroundColor Green
Write-Host ""

# Start NotebookLLM
Write-Host "[5/5] Starting NotebookLLM..." -ForegroundColor Cyan
Set-Location "$ScriptDir\NotebookLLM\api"
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--port", "8000" -WindowStyle Hidden
Set-Location "$ScriptDir\NotebookLLM\frontend"
$env:PORT = "3002"
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WindowStyle Hidden
Set-Location $ScriptDir
Write-Host "✓ NotebookLLM starting..." -ForegroundColor Green
Write-Host ""

Write-Host "Waiting 15 seconds for services..." -ForegroundColor Cyan
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║  SparksBM System Starting!                                   ║" -ForegroundColor Yellow
Write-Host "╠═══════════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "║  ISMS Platform:                                               ║" -ForegroundColor Yellow
Write-Host "║    🌐 Frontend:    http://localhost:3001                     ║" -ForegroundColor Yellow
Write-Host "║    🔧 Backend:     http://localhost:8070                     ║" -ForegroundColor Yellow
Write-Host "║    🔐 Keycloak:    http://localhost:8080                     ║" -ForegroundColor Yellow
Write-Host "║  NotebookLLM:                                                  ║" -ForegroundColor Yellow
Write-Host "║    🌐 Frontend:    http://localhost:3002                     ║" -ForegroundColor Yellow
Write-Host "║    🔧 API:         http://localhost:8000                     ║" -ForegroundColor Yellow
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
