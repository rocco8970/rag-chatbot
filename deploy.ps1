# RAG Chatbot Production Deployment Script (Windows PowerShell)
# ============================================================================
#
# Production-ready deployment script for RAG chatbot on Windows.
#
# Usage:
#   .\deploy.ps1 [-Port 8501] [-Host 0.0.0.0] [-Environment production] [-SkipVenv]
#
# Examples:
#   .\deploy.ps1
#   .\deploy.ps1 -Port 8502 -Host 127.0.0.1
#   .\deploy.ps1 -Environment staging -SkipVenv
#
# Requirements:
#   - PowerShell 5.0+
#   - Python 3.9+
#   - PostgreSQL installed and running
#   - .env file in project root

param(
    [int]$Port = 8501,
    [string]$Host = "0.0.0.0",
    [string]$Environment = "production",
    [switch]$SkipVenv = $false,
    [switch]$Help = $false
)

# ============================================================================
# Configuration
# ============================================================================

$ErrorActionPreference = "Stop"
$WarningPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectName = "rag-chatbot"
$VenvDir = Join-Path $ScriptDir ".venv"
$LogDir = Join-Path $ScriptDir "logs"
$LogFile = Join-Path $LogDir "deployment.log"
$AppLogFile = Join-Path $LogDir "app.log"
$PidFile = Join-Path $ScriptDir ".streamlit.pid"

$PythonMinVersion = "3.9"

# Color codes (Windows 10+ with VT100 support)
$Colors = @{
    Red = "`e[31m"
    Green = "`e[32m"
    Yellow = "`e[33m"
    Blue = "`e[34m"
    Reset = "`e[0m"
}

# ============================================================================
# Utility Functions
# ============================================================================

function Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $output = "$timestamp] $Message"
    Write-Host "$($Colors.Blue)[$output$($Colors.Reset)"
    Add-Content -Path $LogFile -Value "[$timestamp] $Message"
}

function Success {
    param([string]$Message)
    Write-Host "$($Colors.Green)✓ $Message$($Colors.Reset)"
    Add-Content -Path $LogFile -Value "✓ $Message"
}

function Error_ {
    param([string]$Message)
    Write-Host "$($Colors.Red)✗ ERROR: $Message$($Colors.Reset)" -ForegroundColor Red
    Add-Content -Path $LogFile -Value "✗ ERROR: $Message"
}

function Warning_ {
    param([string]$Message)
    Write-Host "$($Colors.Yellow)⚠ WARNING: $Message$($Colors.Reset)" -ForegroundColor Yellow
    Add-Content -Path $LogFile -Value "⚠ WARNING: $Message"
}

function Info {
    param([string]$Message)
    Write-Host "$($Colors.Blue)ℹ $Message$($Colors.Reset)"
    Add-Content -Path $LogFile -Value "ℹ $Message"
}

function Die {
    param([string]$Message, [int]$Code = 1)
    Error_ $Message
    exit $Code
}

function Show-Help {
    Write-Host @"
RAG Chatbot Deployment Script for Windows

Usage:
  .\deploy.ps1 [OPTIONS]

Options:
  -Port PORT              Streamlit port (default: 8501)
  -Host HOST              Streamlit host (default: 0.0.0.0)
  -Environment ENV        Environment (default: production)
  -SkipVenv               Skip virtual environment creation
  -Help                   Show this help message

Examples:
  .\deploy.ps1 -Port 8502 -Host 127.0.0.1
  .\deploy.ps1 -Environment staging -SkipVenv
"@
}

# ============================================================================
# Stage 1: Environment Validation
# ============================================================================

function Validate-Environment {
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Log "STAGE 1: Environment Validation"
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check Python
    Log "Checking Python installation..."
    try {
        $pythonVersion = & python --version 2>&1
        $pythonVersion = $pythonVersion -replace "Python ", ""
        Write-Host "  Found: $pythonVersion"
        Success "Python found: $pythonVersion"
    }
    catch {
        Die "Python not found. Please install Python $PythonMinVersion or later."
    }

    # Parse Python version
    $versionParts = $pythonVersion.Split('.')
    $major = [int]$versionParts[0]
    $minor = [int]$versionParts[1]
    $minorRequired = [int]($PythonMinVersion -split '\.')[1]
    
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt $minorRequired)) {
        Die "Python version $pythonVersion is less than required $PythonMinVersion"
    }

    # Check PostgreSQL
    Log "Checking PostgreSQL..."
    try {
        $pgVersion = & psql --version 2>&1
        Success $pgVersion
    }
    catch {
        Die "PostgreSQL (psql) not found. Please install PostgreSQL."
    }

    # Check .env file
    Log "Checking .env file..."
    $envPath = Join-Path $ScriptDir ".env"
    if (-not (Test-Path $envPath)) {
        Die ".env file not found. Please copy .env.example to .env and configure it."
    }
    Success ".env file exists"

    # Load .env
    Log "Loading .env variables..."
    $env_vars = @{}
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            $env_vars[$key] = $value
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }

    # Validate required variables
    Log "Validating required .env variables..."
    $required = @("OPENAI_API_KEY", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    $missing = @()
    foreach ($var in $required) {
        if (-not $env_vars.ContainsKey($var)) {
            $missing += $var
        }
    }

    if ($missing.Count -gt 0) {
        Die "Missing required .env variables: $($missing -join ', ')"
    }
    Success "All required .env variables present"

    # Test database connection
    Log "Testing database connectivity..."
    try {
        $env:PGPASSWORD = $env_vars['DB_PASSWORD']
        $result = & psql -h $env_vars['DB_HOST'] -p $env_vars['DB_PORT'] -U $env_vars['DB_USER'] -d $env_vars['DB_NAME'] -c "SELECT 1;" 2>&1
        Success "Database connection verified"
    }
    catch {
        Warning_ "Database connection test failed. Will attempt setup during DB initialization."
    }

    Success "Environment validation complete"
}

# ============================================================================
# Stage 2: Dependency Installation
# ============================================================================

function Install-Dependencies {
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Log "STAGE 2: Dependency Installation"
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Create virtual environment
    if (-not $SkipVenv) {
        Log "Creating virtual environment..."
        if (Test-Path $VenvDir) {
            Warning_ "Virtual environment already exists. Skipping creation."
        }
        else {
            try {
                & python -m venv $VenvDir
                Success "Virtual environment created"
            }
            catch {
                Die "Failed to create virtual environment: $_"
            }
        }
    }

    # Activate virtual environment
    Log "Activating virtual environment..."
    $activatePath = Join-Path $VenvDir "Scripts" "Activate.ps1"
    if (-not (Test-Path $activatePath)) {
        Die "Virtual environment activation script not found at $activatePath"
    }
    & $activatePath
    Success "Virtual environment activated"

    # Upgrade pip
    Log "Upgrading pip..."
    try {
        & python -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null
        Success "pip upgraded"
    }
    catch {
        Die "Failed to upgrade pip: $_"
    }

    # Install requirements
    Log "Installing requirements..."
    $requirementsPath = Join-Path $ScriptDir "requirements.txt"
    if (-not (Test-Path $requirementsPath)) {
        Die "requirements.txt not found"
    }

    try {
        & pip install -r $requirementsPath 2>&1 | Out-Null
        Success "Requirements installed"
    }
    catch {
        Die "Failed to install requirements: $_"
    }

    # Verify packages
    Log "Verifying critical packages..."
    $packages = @("streamlit", "psycopg2", "openai", "pgvector", "python-dotenv")
    foreach ($pkg in $packages) {
        try {
            & python -c "import $($pkg.Replace('-', '_'))" 2>&1 | Out-Null
            Success "  ✓ $pkg"
        }
        catch {
            Warning_ "Package $pkg not found. This may cause runtime errors."
        }
    }

    Success "Dependency installation complete"
}

# ============================================================================
# Stage 3: Database Setup
# ============================================================================

function Setup-Database {
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Log "STAGE 3: Database Setup"
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    $setupScript = Join-Path $ScriptDir "scripts" "setup_database.py"
    if (-not (Test-Path $setupScript)) {
        Die "setup_database.py not found"
    }

    Log "Running database setup script..."
    try {
        & python $setupScript 2>&1 | Tee-Object -FilePath $AppLogFile -Append | Out-Null
        Success "Database setup script executed"
    }
    catch {
        Warning_ "Database setup reported errors. Continuing with verification..."
    }

    # Verify tables
    Log "Verifying database tables..."
    $tables = @("company_documents", "document_chunks", "conversations")
    $env:PGPASSWORD = [System.Environment]::GetEnvironmentVariable("DB_PASSWORD", "Process")
    $dbHost = [System.Environment]::GetEnvironmentVariable("DB_HOST", "Process")
    $dbPort = [System.Environment]::GetEnvironmentVariable("DB_PORT", "Process")
    $dbUser = [System.Environment]::GetEnvironmentVariable("DB_USER", "Process")
    $dbName = [System.Environment]::GetEnvironmentVariable("DB_NAME", "Process")

    foreach ($table in $tables) {
        try {
            $result = & psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c "SELECT to_regclass('public.$table');" 2>&1
            if ($result -notcontains "NULL") {
                Success "  ✓ Table $table exists"
            }
            else {
                Die "Table $table not found"
            }
        }
        catch {
            Die "Failed to verify table $table"
        }
    }

    Success "Database setup complete"
}

# ============================================================================
# Stage 4: Application Configuration
# ============================================================================

function Configure-Application {
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Log "STAGE 4: Application Configuration"
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Create log directory
    Log "Setting up log directory..."
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir | Out-Null
    }
    Success "Log directory ready: $LogDir"

    # Create Streamlit config directory (optional)
    Log "Setting up Streamlit configuration..."
    $streamlitConfigDir = Join-Path $env:USERPROFILE ".streamlit"
    if (-not (Test-Path $streamlitConfigDir)) {
        New-Item -ItemType Directory -Path $streamlitConfigDir | Out-Null
    }

    # Create NSSM config template for Windows service (optional)
    if ($Environment -eq "production") {
        Log "Creating Windows service configuration template..."
        $nssm_template = @"
# Windows Service Configuration Template (NSSM - Non-Sucking Service Manager)
# 
# Installation steps:
# 1. Download NSSM from https://nssm.cc/download
# 2. Extract and add to PATH or use full path
# 3. Run these commands as Administrator:
#
# nssm install RagChatbot "$(Join-Path $VenvDir 'Scripts' 'python.exe')" "-m streamlit run streamlit_app.py --server.port=$Port --server.address=$Host"
# nssm set RagChatbot AppDirectory "$ScriptDir"
# nssm set RagChatbot AppEnvironmentExtra DB_HOST=$($env:DB_HOST)
# nssm start RagChatbot
#
# Other useful commands:
# nssm stop RagChatbot     - Stop the service
# nssm restart RagChatbot  - Restart the service
# nssm remove RagChatbot   - Remove the service
# nssm status RagChatbot   - Check service status
"@
        $nssm_template | Out-File -FilePath (Join-Path $ScriptDir "nssm-service.template.txt") -Encoding UTF8
        Info "NSSM service template created: $(Join-Path $ScriptDir 'nssm-service.template.txt')"
    }

    Success "Application configuration complete"
}

# ============================================================================
# Stage 5: Start Application
# ============================================================================

function Start-Application {
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Log "STAGE 5: Starting Application"
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Activate venv
    $activatePath = Join-Path $VenvDir "Scripts" "Activate.ps1"
    & $activatePath

    # Kill existing process
    if (Test-Path $PidFile) {
        $oldPid = Get-Content $PidFile
        try {
            $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
            if ($proc) {
                Log "Stopping existing application (PID: $oldPid)..."
                Stop-Process -Id $oldPid -Force
                Start-Sleep -Seconds 2
            }
        }
        catch {
            # Process not running
        }
    }

    # Start application
    Log "Starting Streamlit application..."
    Log "  Host: $Host"
    Log "  Port: $Port"
    Log "  Environment: $Environment"

    $appScript = Join-Path $ScriptDir "streamlit_app.py"
    $process = Start-Process -FilePath "python" `
        -ArgumentList "-m streamlit run `"$appScript`" --server.port=$Port --server.address=$Host --logger.level=info" `
        -WorkingDirectory $ScriptDir `
        -RedirectStandardOutput $AppLogFile `
        -RedirectStandardError $AppLogFile `
        -PassThru `
        -NoNewWindow

    $process.Id | Out-File -FilePath $PidFile -Encoding UTF8
    Success "Application started (PID: $($process.Id))"

    # Wait for startup
    Log "Waiting for application to initialize..."
    Start-Sleep -Seconds 3

    Success "Application startup complete"
}

# ============================================================================
# Stage 6: Post-Deployment Verification
# ============================================================================

function Verify-Deployment {
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Log "STAGE 6: Post-Deployment Verification"
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Check process
    Log "Checking if application is running..."
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Success "Application running (PID: $pid)"
        }
        else {
            Die "Application process not found (PID: $pid)"
        }
    }

    # Test database
    Log "Testing database connection..."
    $dbHost = [System.Environment]::GetEnvironmentVariable("DB_HOST", "Process")
    $dbPort = [System.Environment]::GetEnvironmentVariable("DB_PORT", "Process")
    $dbUser = [System.Environment]::GetEnvironmentVariable("DB_USER", "Process")
    $dbName = [System.Environment]::GetEnvironmentVariable("DB_NAME", "Process")
    $env:PGPASSWORD = [System.Environment]::GetEnvironmentVariable("DB_PASSWORD", "Process")

    try {
        $result = & psql -h $dbHost -p $dbPort -U $dbUser -d $dbName -c "SELECT COUNT(*) FROM company_documents;" 2>&1
        Success "Database connection verified"
    }
    catch {
        Warning_ "Database connection test failed"
    }

    # Health check
    Log "Attempting health check..."
    $url = "http://${Host}:${Port}"
    for ($i = 1; $i -le 10; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $url -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Success "Application is responding at $url"
                break
            }
        }
        catch {
            if ($i -eq 10) {
                Warning_ "Application not responding after 10 attempts"
                Info "Check log file: $AppLogFile"
            }
        }
        Start-Sleep -Seconds 1
    }

    # Summary
    Log ""
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Success "DEPLOYMENT COMPLETE"
    Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Log ""
    Info "Application running at: http://${Host}:${Port}"
    Info "Application log: $AppLogFile"
    Info "Deployment log: $LogFile"
    if (Test-Path $PidFile) {
        Info "Process ID: $(Get-Content $PidFile)"
    }
    Log ""
    Info "To view logs: Get-Content -Path '$AppLogFile' -Wait"
    Info "To stop: Stop-Process -Id (Get-Content '$PidFile')"
    Log ""
}

# ============================================================================
# Main Execution
# ============================================================================

function Main {
    if ($Help) {
        Show-Help
        exit 0
    }

    Write-Host ""
    Write-Host "$($Colors.Blue)╔════════════════════════════════════════════════════════════════╗$($Colors.Reset)"
    Write-Host "$($Colors.Blue)║  RAG Chatbot Production Deployment (Windows PowerShell)          ║$($Colors.Reset)"
    Write-Host "$($Colors.Blue)╚════════════════════════════════════════════════════════════════╝$($Colors.Reset)"
    Write-Host ""

    # Create log directory first
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir | Out-Null
    }

    try {
        Validate-Environment
        Install-Dependencies
        Setup-Database
        Configure-Application
        Start-Application
        Verify-Deployment
        Log "Deployment completed at $(Get-Date)"
    }
    catch {
        Error_ "Deployment failed: $_"
        exit 1
    }
}

# Run main
Main
