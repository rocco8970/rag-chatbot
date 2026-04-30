#!/bin/bash

################################################################################
# RAG Chatbot Production Deployment Script
################################################################################
# 
# Production-ready deployment script for RAG chatbot with comprehensive
# validation, error handling, and health checks.
#
# Usage:
#   ./deploy.sh [--port 8501] [--host 0.0.0.0] [--env production] [--no-venv]
#
# Examples:
#   ./deploy.sh                                    # defaults
#   ./deploy.sh --port 8502 --host 127.0.0.1      # custom port/host
#   ./deploy.sh --env staging --no-venv            # staging, skip venv
#
################################################################################

set -euo pipefail

# ==============================================================================
# Configuration & Defaults
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="rag-chatbot"
VENV_DIR="${SCRIPT_DIR}/.venv"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/deployment.log"
APP_LOG_FILE="${LOG_DIR}/app.log"
PID_FILE="${SCRIPT_DIR}/.streamlit.pid"

PORT=${PORT:-8501}
HOST=${HOST:-0.0.0.0}
ENVIRONMENT=${ENVIRONMENT:-production}
CREATE_VENV=${CREATE_VENV:-true}
PYTHON_MIN_VERSION=3.9

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==============================================================================
# Utility Functions
# ==============================================================================

log() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[${timestamp}]${NC} ${msg}" | tee -a "${LOG_FILE}"
}

success() {
    local msg="$1"
    echo -e "${GREEN}✓ ${msg}${NC}" | tee -a "${LOG_FILE}"
}

error() {
    local msg="$1"
    echo -e "${RED}✗ ERROR: ${msg}${NC}" | tee -a "${LOG_FILE}"
}

warning() {
    local msg="$1"
    echo -e "${YELLOW}⚠ WARNING: ${msg}${NC}" | tee -a "${LOG_FILE}"
}

info() {
    local msg="$1"
    echo -e "${BLUE}ℹ ${msg}${NC}" | tee -a "${LOG_FILE}"
}

die() {
    local msg="$1"
    local code=${2:-1}
    error "${msg}"
    exit "${code}"
}

# ==============================================================================
# Argument Parsing
# ==============================================================================

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --port)
                PORT="$2"
                shift 2
                ;;
            --host)
                HOST="$2"
                shift 2
                ;;
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --no-venv)
                CREATE_VENV=false
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                warning "Unknown argument: $1"
                shift
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  --port PORT          Streamlit port (default: 8501)
  --host HOST          Streamlit host (default: 0.0.0.0)
  --env ENV            Environment (default: production)
  --no-venv            Skip virtual environment creation
  --help, -h           Show this help message

Examples:
  $0 --port 8502 --host 127.0.0.1
  $0 --env staging --no-venv
EOF
}

# ==============================================================================
# Stage 1: Environment Validation
# ==============================================================================

validate_environment() {
    log "═══════════════════════════════════════════════════════════════"
    log "STAGE 1: Environment Validation"
    log "═══════════════════════════════════════════════════════════════"

    # Check Python version
    log "Checking Python version..."
    if ! command -v python3 &> /dev/null; then
        die "Python 3 not found. Please install Python ${PYTHON_MIN_VERSION}+."
    fi

    local python_version=$(python3 --version 2>&1 | awk '{print $2}')
    local major_minor=$(echo "${python_version}" | cut -d. -f1,2)
    log "Found Python: ${python_version}"

    # Simple version comparison
    if (( $(echo "${major_minor} < ${PYTHON_MIN_VERSION}" | bc -l) )); then
        die "Python version ${python_version} is less than required ${PYTHON_MIN_VERSION}."
    fi
    success "Python version check passed (${python_version})"

    # Check PostgreSQL installed
    log "Checking PostgreSQL..."
    if ! command -v psql &> /dev/null; then
        die "PostgreSQL client (psql) not found. Please install PostgreSQL."
    fi
    local pg_version=$(psql --version 2>&1 | awk '{print $3}')
    success "PostgreSQL found: ${pg_version}"

    # Check .env file
    log "Checking .env file..."
    if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
        die ".env file not found. Please copy .env.example to .env and configure it."
    fi
    success ".env file exists"

    # Validate required .env variables
    log "Validating .env variables..."
    local required_vars=("OPENAI_API_KEY" "DB_HOST" "DB_PORT" "DB_NAME" "DB_USER" "DB_PASSWORD")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "${SCRIPT_DIR}/.env"; then
            missing_vars+=("${var}")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        die "Missing required .env variables: ${missing_vars[*]}"
    fi
    success "All required .env variables present"

    # Load environment
    source "${SCRIPT_DIR}/.env"

    # Validate DB connectivity
    log "Validating database connectivity..."
    if ! PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "SELECT 1" &> /dev/null; then
        warning "Could not connect to database. Will attempt to create during setup phase."
    else
        success "Database connectivity verified"
    fi

    # Check pgvector extension availability
    log "Checking pgvector extension..."
    if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS vector;" &> /dev/null 2>&1; then
        success "pgvector extension available"
    else
        warning "pgvector extension not immediately available (will attempt during DB setup)"
    fi

    success "Environment validation complete"
}

# ==============================================================================
# Stage 2: Dependency Installation
# ==============================================================================

install_dependencies() {
    log "═══════════════════════════════════════════════════════════════"
    log "STAGE 2: Dependency Installation"
    log "═══════════════════════════════════════════════════════════════"

    # Create virtual environment if requested
    if [[ "${CREATE_VENV}" == true ]]; then
        log "Creating virtual environment at ${VENV_DIR}..."
        if [[ -d "${VENV_DIR}" ]]; then
            warning "Virtual environment already exists. Skipping creation."
        else
            python3 -m venv "${VENV_DIR}" || die "Failed to create virtual environment."
            success "Virtual environment created"
        fi
    fi

    # Activate virtual environment
    log "Activating virtual environment..."
    if [[ ! -f "${VENV_DIR}/bin/activate" ]]; then
        die "Virtual environment activation script not found."
    fi
    source "${VENV_DIR}/bin/activate"
    success "Virtual environment activated"

    # Upgrade pip
    log "Upgrading pip..."
    pip install --upgrade pip setuptools wheel > "${LOG_FILE}" 2>&1 || die "Failed to upgrade pip."
    success "pip upgraded"

    # Install requirements
    log "Installing requirements from requirements.txt..."
    if [[ ! -f "${SCRIPT_DIR}/requirements.txt" ]]; then
        die "requirements.txt not found."
    fi
    pip install -r "${SCRIPT_DIR}/requirements.txt" >> "${LOG_FILE}" 2>&1 || die "Failed to install requirements."
    success "Requirements installed"

    # Verify critical packages
    log "Verifying critical packages..."
    local required_packages=("streamlit" "psycopg2" "openai" "pgvector" "python-dotenv")
    for pkg in "${required_packages[@]}"; do
        if ! python3 -c "import ${pkg//-/_}" 2>/dev/null; then
            warning "Package ${pkg} not found after installation. This may cause runtime errors."
        else
            success "  ✓ ${pkg}"
        fi
    done

    success "Dependency installation complete"
}

# ==============================================================================
# Stage 3: Database Setup
# ==============================================================================

setup_database() {
    log "═══════════════════════════════════════════════════════════════"
    log "STAGE 3: Database Setup"
    log "═══════════════════════════════════════════════════════════════"

    source "${VENV_DIR}/bin/activate"
    source "${SCRIPT_DIR}/.env"

    # Run setup_database.py
    log "Running database setup script..."
    if [[ ! -f "${SCRIPT_DIR}/scripts/setup_database.py" ]]; then
        die "setup_database.py not found."
    fi

    python3 "${SCRIPT_DIR}/scripts/setup_database.py" >> "${LOG_FILE}" 2>&1 || {
        warning "Database setup script reported errors. Continuing with verification..."
    }
    success "Database setup script executed"

    # Verify tables exist
    log "Verifying database tables..."
    local required_tables=("company_documents" "document_chunks" "conversations")
    for table in "${required_tables[@]}"; do
        if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
            -c "SELECT to_relname('${table}');" 2>/dev/null | grep -q "${table}"; then
            success "  ✓ Table ${table} exists"
        else
            die "Table ${table} not found. Database setup may have failed."
        fi
    done

    # Run database tests
    log "Running database tests..."
    if [[ -f "${SCRIPT_DIR}/tests/test_database.py" ]]; then
        python3 "${SCRIPT_DIR}/tests/test_database.py" >> "${LOG_FILE}" 2>&1 || {
            warning "Database tests failed. Check logs for details."
        }
        success "Database tests executed"
    else
        warning "test_database.py not found. Skipping database tests."
    fi

    success "Database setup complete"
}

# ==============================================================================
# Stage 4: Application Configuration
# ==============================================================================

configure_application() {
    log "═══════════════════════════════════════════════════════════════"
    log "STAGE 4: Application Configuration"
    log "═══════════════════════════════════════════════════════════════"

    # Set permissions on deployment scripts
    log "Setting permissions on scripts..."
    chmod +x "${SCRIPT_DIR}/deploy.sh" || warning "Could not set execute permission on deploy.sh"
    if [[ -f "${SCRIPT_DIR}/scripts/setup_database.py" ]]; then
        chmod +x "${SCRIPT_DIR}/scripts/setup_database.py" || true
    fi
    success "Permissions configured"

    # Create logs directory if it doesn't exist
    log "Setting up log directory..."
    mkdir -p "${LOG_DIR}" || die "Failed to create log directory."
    success "Log directory ready: ${LOG_DIR}"

    # Create systemd service file (optional, for reference)
    if [[ "${ENVIRONMENT}" == "production" ]]; then
        log "Creating systemd service template..."
        cat > "${SCRIPT_DIR}/rag-chatbot.service.template" << 'SYSTEMD_EOF'
[Unit]
Description=RAG Chatbot Streamlit Application
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/rag-chatbot
Environment="PATH=/path/to/rag-chatbot/.venv/bin"
EnvironmentFile=/path/to/rag-chatbot/.env
ExecStart=/path/to/rag-chatbot/.venv/bin/python -m streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0
Restart=on-failure
RestartSec=10

# Log rotation handled by journald
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rag-chatbot

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF
        info "Systemd service template created at: ${SCRIPT_DIR}/rag-chatbot.service.template"
        info "To install: sudo cp rag-chatbot.service.template /etc/systemd/system/rag-chatbot.service"
        info "Then: sudo systemctl daemon-reload && sudo systemctl enable rag-chatbot && sudo systemctl start rag-chatbot"
    fi

    # Setup log rotation configuration
    log "Creating logrotate configuration template..."
    cat > "${SCRIPT_DIR}/logrotate.conf.template" << 'LOGROTATE_EOF'
/path/to/rag-chatbot/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload rag-chatbot > /dev/null 2>&1 || true
    endscript
}
LOGROTATE_EOF
    info "Logrotate configuration template created at: ${SCRIPT_DIR}/logrotate.conf.template"
    info "To install: sudo cp logrotate.conf.template /etc/logrotate.d/rag-chatbot"

    success "Application configuration complete"
}

# ==============================================================================
# Stage 5: Start Application
# ==============================================================================

start_application() {
    log "═══════════════════════════════════════════════════════════════"
    log "STAGE 5: Starting Application"
    log "═══════════════════════════════════════════════════════════════"

    source "${VENV_DIR}/bin/activate"
    source "${SCRIPT_DIR}/.env"

    # Kill any existing process
    if [[ -f "${PID_FILE}" ]]; then
        local old_pid=$(cat "${PID_FILE}")
        if kill -0 "${old_pid}" 2>/dev/null; then
            log "Stopping existing application (PID: ${old_pid})..."
            kill "${old_pid}" || true
            sleep 2
            kill -9 "${old_pid}" 2>/dev/null || true
        fi
    fi

    # Start Streamlit application in background
    log "Starting Streamlit application..."
    log "  Host: ${HOST}"
    log "  Port: ${PORT}"
    log "  Environment: ${ENVIRONMENT}"

    nohup python3 -m streamlit run "${SCRIPT_DIR}/streamlit_app.py" \
        --server.port="${PORT}" \
        --server.address="${HOST}" \
        --logger.level=info \
        > "${APP_LOG_FILE}" 2>&1 &

    local app_pid=$!
    echo "${app_pid}" > "${PID_FILE}"
    success "Application started (PID: ${app_pid})"

    # Give application time to start
    log "Waiting for application to initialize..."
    sleep 3

    success "Application startup complete"
}

# ==============================================================================
# Stage 6: Post-Deployment Verification
# ==============================================================================

verify_deployment() {
    log "═══════════════════════════════════════════════════════════════"
    log "STAGE 6: Post-Deployment Verification"
    log "═══════════════════════════════════════════════════════════════"

    source "${SCRIPT_DIR}/.env"

    # Check process is running
    log "Checking if application is running..."
    if [[ -f "${PID_FILE}" ]]; then
        local pid=$(cat "${PID_FILE}")
        if kill -0 "${pid}" 2>/dev/null; then
            success "Application process running (PID: ${pid})"
        else
            die "Application process not running (PID: ${pid} not found)."
        fi
    else
        die "PID file not found."
    fi

    # Test database connection
    log "Testing database connection..."
    if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
        -c "SELECT COUNT(*) FROM company_documents;" &> /dev/null; then
        success "Database connection verified"
    else
        warning "Database connection test failed. Check .env and database status."
    fi

    # Health check HTTP endpoint
    log "Attempting health check (HTTP on ${HOST}:${PORT})..."
    local max_attempts=10
    local attempt=1
    while [[ ${attempt} -le ${max_attempts} ]]; do
        if curl -s "http://${HOST}:${PORT}" > /dev/null 2>&1; then
            success "Application is responding on http://${HOST}:${PORT}"
            break
        fi
        if [[ ${attempt} -eq ${max_attempts} ]]; then
            warning "Application not responding to HTTP requests after ${max_attempts} attempts."
            warning "Check ${APP_LOG_FILE} for application errors."
        fi
        sleep 1
        ((attempt++))
    done

    # Summary
    log ""
    log "═══════════════════════════════════════════════════════════════"
    success "DEPLOYMENT COMPLETE"
    log "═══════════════════════════════════════════════════════════════"
    log ""
    info "Application is running at: http://${HOST}:${PORT}"
    info "Application log: ${APP_LOG_FILE}"
    info "Deployment log: ${LOG_FILE}"
    info "Process ID: $(cat ${PID_FILE})"
    log ""
    info "To view logs: tail -f ${APP_LOG_FILE}"
    info "To stop: kill $(cat ${PID_FILE})"
    log ""
}

# ==============================================================================
# Main Execution
# ==============================================================================

main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  RAG Chatbot Production Deployment                             ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Create log directory first
    mkdir -p "${LOG_DIR}"

    # Parse arguments
    parse_arguments "$@"

    # Execute deployment stages
    validate_environment
    install_dependencies
    setup_database
    configure_application
    start_application
    verify_deployment

    log "Deployment script finished at $(date)"
}

# Run main if script is executed (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
