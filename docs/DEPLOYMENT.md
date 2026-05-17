<!-- Deployment Guide for RAG Chatbot -->

# Deployment Guide

This guide covers production deployment of the RAG Chatbot application on both Linux/macOS and Windows systems.

## Quick Start

### Linux/macOS

```bash
# Make script executable
chmod +x deploy.sh

# Run with defaults (port 8501)
./deploy.sh

# Run with custom settings
./deploy.sh --port 8502 --host 127.0.0.1 --env production
```

### Windows (PowerShell)

```powershell
# Allow script execution (if needed)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run with defaults
.\deploy.ps1

# Run with custom settings
.\deploy.ps1 -Port 8502 -Host 127.0.0.1 -Environment production
```

## Deployment Stages

### Stage 1: Environment Validation

**Checks:**
- Python version (≥3.9)
- PostgreSQL installed and accessible
- pgvector extension availability
- .env file exists with required variables:
  - `OPENAI_API_KEY`
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (if using Bedrock)

**Actions:**
- Validates Python version compatibility
- Tests database connectivity
- Checks all required environment variables

### Stage 2: Dependency Installation

**Actions:**
- Creates Python virtual environment (if not present)
- Activates virtual environment
- Upgrades pip, setuptools, wheel
- Installs all requirements from `requirements.txt`
- Verifies critical packages:
  - streamlit
  - psycopg2
  - openai
  - pgvector
  - python-dotenv

### Stage 3: Database Setup

**Actions:**
- Runs `scripts/setup_database.py` to:
  - Create database and admin user (if needed)
  - Create pgvector extension
  - Create schema tables:
    - `company_documents`
    - `document_chunks`
    - `conversations`
  - Create indexes (HNSW for vector similarity, B-tree for metadata)
  - Set proper permissions
- Verifies all tables were created successfully
- Runs `tests/test_database.py` to validate setup

### Stage 4: Application Configuration

**Actions:**
- Creates log directory structure
- Sets execute permissions on scripts
- Creates systemd service template (Linux, production only)
- Creates logrotate configuration template (Linux)
- Creates NSSM service template (Windows, production only)

### Stage 5: Starting Application

**Actions:**
- Stops any existing Streamlit process
- Launches Streamlit application with:
  - Specified port (default: 8501)
  - Specified host (default: 0.0.0.0)
  - Logger level: info
- Saves process ID to `.streamlit.pid`
- Waits 3 seconds for application initialization

### Stage 6: Post-Deployment Verification

**Checks:**
- Confirms application process is running
- Tests database connection
- Performs HTTP health check (max 10 attempts)
- Provides summary with:
  - Application URL
  - Log file locations
  - Process ID
  - Quick commands for management

## Configuration Files

### .env File

Create `.env` in project root (or copy from `.env.example`):

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_db
DB_USER=admin
DB_PASSWORD=secure_password

# AWS Bedrock (optional, if using as LLM provider)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1

# Application Settings
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
```

### Required Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings & LLM | Yes |
| `DB_HOST` | PostgreSQL hostname | Yes |
| `DB_PORT` | PostgreSQL port | Yes (default: 5432) |
| `DB_NAME` | Database name | Yes |
| `DB_USER` | Database user | Yes |
| `DB_PASSWORD` | Database password | Yes |
| `AWS_ACCESS_KEY_ID` | AWS credentials (Bedrock) | No |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials (Bedrock) | No |
| `AWS_REGION` | AWS region | No (default: ap-south-1) |
| `RAG_CHUNK_SIZE` | Text chunk size | No (default: 1000) |
| `RAG_CHUNK_OVERLAP` | Chunk overlap | No (default: 200) |

## System Integration (Linux)

### Using systemd Service

After deployment, you can set up the application as a systemd service:

```bash
# 1. Copy and edit the service template
sudo cp rag-chatbot.service.template /etc/systemd/system/rag-chatbot.service

# 2. Edit the service file to set correct paths
sudo nano /etc/systemd/system/rag-chatbot.service

# 3. Update these placeholders:
#    - /path/to/rag-chatbot with actual project path
#    - www-data with appropriate user

# 4. Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable rag-chatbot
sudo systemctl start rag-chatbot

# 5. Check status
sudo systemctl status rag-chatbot

# 6. View logs
sudo journalctl -u rag-chatbot -f
```

### Using logrotate

```bash
# 1. Copy and edit logrotate configuration
sudo cp logrotate.conf.template /etc/logrotate.d/rag-chatbot

# 2. Edit to set correct path:
sudo nano /etc/logrotate.d/rag-chatbot

# 3. Test the configuration
sudo logrotate -d /etc/logrotate.d/rag-chatbot

# 4. Verify logs are being rotated (automatic, typically daily)
```

## System Integration (Windows)

### Using NSSM Service Manager

NSSM (Non-Sucking Service Manager) allows running Streamlit as a Windows service:

```powershell
# 1. Download NSSM from https://nssm.cc/download
# 2. Extract to a location in PATH or use full path

# 3. Install service (as Administrator)
nssm install RagChatbot "$ProjectPath\.venv\Scripts\python.exe" `
  "-m streamlit run streamlit_app.py --server.port=8501 --server.address=0.0.0.0"
nssm set RagChatbot AppDirectory "$ProjectPath"

# 4. Set environment variables
nssm set RagChatbot AppEnvironmentExtra DB_HOST=localhost

# 5. Start service
nssm start RagChatbot

# 6. Manage service
nssm stop RagChatbot        # Stop
nssm restart RagChatbot     # Restart
nssm status RagChatbot      # Check status
nssm remove RagChatbot      # Remove service (admin console)
```

### Using Windows Task Scheduler

Alternative to NSSM, you can use Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task
3. Name: "RAG Chatbot"
4. Trigger: "At startup"
5. Action:
   - Program: `C:\path\to\.venv\Scripts\python.exe`
   - Arguments: `-m streamlit run streamlit_app.py --server.port=8501`
   - Start in: `C:\path\to\project\`
6. Check "Run with highest privileges" if needed
7. Check "Run whether user is logged in or not"

## Monitoring

### Log Files

- **Deployment Log**: `logs/deployment.log`
- **Application Log**: `logs/app.log`

### View Logs

**Linux/macOS:**
```bash
# Follow application log in real-time
tail -f logs/app.log

# View recent deployment logs
tail -50 logs/deployment.log
```

**Windows PowerShell:**
```powershell
# Follow application log
Get-Content -Path logs/app.log -Wait

# View recent deployment logs
Get-Content -Path logs/deployment.log -Tail 50
```

### Systemd Monitoring

```bash
# Check service status
systemctl status rag-chatbot

# View recent logs
journalctl -u rag-chatbot -n 100

# Follow logs in real-time
journalctl -u rag-chatbot -f

# View logs since service start
journalctl -u rag-chatbot --since today
```

## Troubleshooting

### Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Linux/macOS: Find and kill process on port 8501
lsof -i :8501 | grep -v COMMAND | awk '{print $2}' | xargs kill -9

# Windows PowerShell: Find and kill process on port 8501
Get-NetTCPConnection -LocalPort 8501 | Select-Object -ExpandProperty OwningProcess | ForEach-Object {Stop-Process -Id $_ -Force}
```

### Database Connection Error

**Error:** `FATAL: Ident authentication failed`

**Solution:**
1. Verify PostgreSQL is running
2. Check `.env` credentials are correct
3. Verify database user has proper permissions
4. Try connecting manually: `psql -h DB_HOST -U DB_USER -d DB_NAME`

### pgvector Extension Not Found

**Error:** `extension "vector" does not exist`

**Solution:**
1. Install pgvector: See PostgreSQL installation guide in README
2. Run setup script again: `python3 scripts/setup_database.py`
3. Verify extension: `psql -d DB_NAME -c "SELECT * FROM pg_extension WHERE extname='vector';"`

### OpenAI API Key Invalid

**Error:** `401 Unauthorized`

**Solution:**
1. Verify API key is correct in `.env`
2. Check API key has not expired or been revoked
3. Test API key directly: `curl https://api.openai.com/v1/models -H "Authorization: Bearer YOUR_KEY"`

### Application Won't Start

**Check:**
1. Verify all .env variables are set correctly
2. Check Python version: `python3 --version`
3. Check virtual environment is activated
4. Review application log: `tail -50 logs/app.log`
5. Try running directly: `streamlit run streamlit_app.py`

## Performance Tuning

### Streamlit Configuration

Create `~/.streamlit/config.toml`:

```toml
[client]
maxMessageSize = 200

[server]
maxUploadSize = 200
enableCORS = false
enableXsrfProtection = true
port = 8501

[logger]
level = "info"

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

### Database Performance

```sql
-- Analyze query performance
ANALYZE document_chunks;

-- Check index usage
SELECT * FROM pg_stat_user_indexes;

-- Rebuild indexes if needed
REINDEX TABLE document_chunks;
```

### Resource Management

- **Memory**: Streamlit typically uses 100-300MB + 500MB per concurrent user
- **CPU**: Primarily used during embedding generation and response synthesis
- **Storage**: ~1GB per 1M embeddings (1536-dim vectors)

## Backup and Recovery

### Database Backup

```bash
# Full backup
pg_dump -h DB_HOST -U DB_USER -d DB_NAME > rag-backup-$(date +%Y%m%d).sql

# With compression
pg_dump -h DB_HOST -U DB_USER -Fc -d DB_NAME > rag-backup-$(date +%Y%m%d).dump

# Restore from backup
psql -h DB_HOST -U DB_USER -d DB_NAME < rag-backup-20230101.sql
```

### Application Data

Key files to back up:
- `.env` (credentials)
- `requirements.txt` (dependencies)
- Database backups
- Uploaded documents (stored in DB)

## Security Checklist

- [ ] `.env` file is NOT in version control (check `.gitignore`)
- [ ] `.env` file has restrictive permissions: `chmod 600 .env`
- [ ] Database password is strong (min 12 chars, mixed case, numbers, symbols)
- [ ] API keys are rotated regularly
- [ ] HTTPS is used in production (reverse proxy recommended)
- [ ] Firewall only allows necessary ports (8501 for app, 5432 for DB)
- [ ] Database backups are encrypted
- [ ] Application logs are monitored for errors
- [ ] Rate limiting is configured if exposed to internet

## Next Steps

1. Configure monitoring and alerting
2. Set up automated backups
3. Plan scaling strategy (horizontal scaling with load balancer)
4. Implement CI/CD pipeline for updates
5. Configure SSL/TLS for production access

For more information, see:
- [Streamlit Deployment Guide](https://docs.streamlit.io/library/get-started/installation)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
