<#
.SYNOPSIS
    AI Market Intelligence - Quickstart script for Windows.

.DESCRIPTION
    Handles first-time setup and subsequent runs:
      1. Checks Python 3.10+ is available
      2. Creates and activates a virtual environment
      3. Installs / updates dependencies
      4. Copies .env.example to .env (if missing) and prompts for keys
      5. Initialises the SQLite database
      6. Offers to run a test report or launch the Streamlit dashboard

.PARAMETER Test
    Run the daily report pipeline once immediately, then exit.

.PARAMETER Dashboard
    Launch the Streamlit dashboard (default action).

.PARAMETER Scheduler
    Start the background scheduler (runs daily at 08:00).

.EXAMPLE
    .\start.ps1                  # launch dashboard (default)
    .\start.ps1 -Test            # run one report immediately
    .\start.ps1 -Scheduler       # start the 08:00 scheduler
#>

[CmdletBinding(DefaultParameterSetName = "Dashboard")]
param(
    [Parameter(ParameterSetName = "Test")]
    [switch]$Test,

    [Parameter(ParameterSetName = "Scheduler")]
    [switch]$Scheduler
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# -- Resolve project root (same folder as this script) ---------------------
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $ProjectRoot

function Write-Step  { param([string]$msg) Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$msg) Write-Host "   $msg" -ForegroundColor Green }
function Write-Warn  { param([string]$msg) Write-Host "   $msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$msg) Write-Host "   $msg" -ForegroundColor Red }

try {

# --------------------------------------------------------------------------
# 1. Locate Python 3.10+
# --------------------------------------------------------------------------
Write-Step "Checking Python installation..."

$PythonCmd = $null

# Try common names in order of preference
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                $PythonCmd = $candidate
                break
            }
        }
    } catch {
        # candidate not found, try next
    }
}

# On Windows the py launcher can target a specific version
if (-not $PythonCmd) {
    try {
        $ver = & py -3.10 --version 2>&1
        if ($ver -match "Python 3\.\d+") {
            $PythonCmd = "py -3.10"
        }
    } catch {}
}

if (-not $PythonCmd) {
    Write-Err "Python 3.10 or later is required but was not found."
    Write-Err "Install from https://www.python.org/downloads/ and make sure it is on your PATH."
    exit 1
}

$PythonVersion = & $PythonCmd --version 2>&1
Write-Ok "Found $PythonVersion (command: $PythonCmd)"

# --------------------------------------------------------------------------
# 2. Virtual environment
# --------------------------------------------------------------------------
Write-Step "Setting up virtual environment..."

$VenvDir  = Join-Path $ProjectRoot "venv"
$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"

if (-not (Test-Path $VenvDir)) {
    Write-Warn "Creating virtual environment in .\venv ..."
    & $PythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Failed to create virtual environment."
        exit 1
    }
    Write-Ok "Virtual environment created."
} else {
    Write-Ok "Virtual environment already exists."
}

# Activate
if (-not (Test-Path $Activate)) {
    Write-Err "Could not find $Activate -- venv may be corrupted. Delete .\venv and re-run."
    exit 1
}
. $Activate
Write-Ok "Virtual environment activated."

# --------------------------------------------------------------------------
# 3. Install / update dependencies
# --------------------------------------------------------------------------
Write-Step "Installing dependencies (this may take a few minutes on first run)..."

python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
python -m pip install -r requirements.txt --quiet 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Err "pip install failed. Check the output above."
    exit 1
}
Write-Ok "All dependencies installed."

# --------------------------------------------------------------------------
# 4. Environment file (.env)
# --------------------------------------------------------------------------
Write-Step "Checking environment configuration..."

$EnvFile    = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Warn ".env created from .env.example -- you need to fill in your API keys."
    } else {
        # Create a minimal .env from scratch
        @(
            "ANTHROPIC_API_KEY=",
            "NEWSAPI_KEY=",
            "GMAIL_EMAIL=",
            "GMAIL_APP_PASSWORD=",
            "FRED_API_KEY="
        ) | Set-Content $EnvFile
        Write-Warn ".env created with empty keys -- you need to fill in your API keys."
    }
}

# Check which keys are filled in
$MissingKeys  = @()
$OptionalKeys = @("FRED_API_KEY", "GMAIL_EMAIL", "GMAIL_APP_PASSWORD")

foreach ($line in (Get-Content $EnvFile)) {
    if ($line -match "^\s*([A-Z_]+)\s*=\s*$") {
        $key = $Matches[1]
        if ($key -notin $OptionalKeys) {
            $MissingKeys += $key
        }
    }
}

if ($MissingKeys.Count -gt 0) {
    Write-Warn "The following required keys are empty in .env:"
    foreach ($k in $MissingKeys) {
        Write-Warn "  - $k"
    }
    Write-Host ""

    # Interactive prompt for each missing key
    $Updated = $false
    foreach ($k in $MissingKeys) {
        $value = Read-Host "   Enter value for $k (or press Enter to skip)"
        if ($value) {
            $content = Get-Content $EnvFile -Raw
            $content = $content -replace "(?m)^(\s*${k}\s*=).*$", "`$1$value"
            Set-Content $EnvFile $content -NoNewline
            $Updated = $true
        }
    }
    if ($Updated) {
        Write-Ok "Updated .env with provided values."
    } else {
        Write-Warn "Some keys are still empty. The pipeline will skip those data sources."
    }
} else {
    Write-Ok ".env is configured."
}

# --------------------------------------------------------------------------
# 5. Create required directories
# --------------------------------------------------------------------------
Write-Step "Ensuring directories exist..."

foreach ($dir in @("reports", "logs")) {
    $path = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Ok "Created $dir/"
    }
}
Write-Ok "Directories ready."

# --------------------------------------------------------------------------
# 6. Initialise database
# --------------------------------------------------------------------------
Write-Step "Initialising database..."

python -c "from src.database_handler import init_database; init_database()" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Err "Database initialisation failed."
    exit 1
}
Write-Ok "Database ready (market_data.db)."

# --------------------------------------------------------------------------
# 7. Launch
# --------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   AI Market Intelligence -- Ready!         " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if ($Test) {
    Write-Step "Running test report..."
    python -m src.main --test
}
elseif ($Scheduler) {
    Write-Step "Starting daily scheduler (08:00 AM)..."
    Write-Host "   Press Ctrl+C to stop." -ForegroundColor Yellow
    python -m src.main
}
else {
    # Default: launch Streamlit dashboard
    Write-Step "Launching Streamlit dashboard..."
    Write-Host "   Dashboard will open at http://localhost:8501" -ForegroundColor Green
    Write-Host "   Press Ctrl+C to stop." -ForegroundColor Yellow
    Write-Host ""
    streamlit run app.py
}

} # end try
catch {
    Write-Err ("An unexpected error occurred: " + $_.Exception.Message)
    exit 1
}
finally {
    Pop-Location
}
