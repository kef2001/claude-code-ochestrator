# Claude Orchestrator Deployment Checklist

## Pre-Deployment Checklist

### 1. Environment Setup
- [ ] Python 3.8+ installed (3.10+ recommended)
- [ ] pip package manager updated (`python -m pip install --upgrade pip`)
- [ ] Git installed and configured
- [ ] ripgrep (rg) installed for security scanning (optional but recommended)

### 2. Repository Setup
```bash
# Clone the repository
git clone <repository-url>
cd claude-code-orchestrator

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
- [ ] Copy `.env.example` to `.env`
  ```bash
  cp .env.example .env
  ```
- [ ] Set `ANTHROPIC_API_KEY` in `.env` file
- [ ] Set proper file permissions
  ```bash
  chmod 600 .env
  ```
- [ ] Review and update `orchestrator_config.json`:
  - [ ] Set appropriate worker count based on API limits
  - [ ] Configure timeouts for your use case
  - [ ] Set notification preferences
  - [ ] Review model selections (Opus for manager, Sonnet for workers)

### 4. API Keys and Credentials
- [ ] Anthropic API key configured and validated
  ```bash
  co check  # Verifies API key format
  ```
- [ ] Optional: Slack webhook URL configured (if using notifications)
- [ ] Optional: Perplexity API key configured (if using AI research features)

### 5. Pre-Flight Checks
```bash
# Run setup check
co check

# Initialize project (creates necessary directories)
co init

# Verify Claude CLI connection
co status

# Test task creation
co add "Test task: Verify deployment"

# List tasks to confirm Task Master is working
co list

# Run security audit
co security-audit
```

### 6. Testing
- [ ] Run unit tests
  ```bash
  pytest tests/
  ```
- [ ] Run tests with coverage
  ```bash
  co coverage
  # or
  make coverage
  ```
- [ ] Run linting checks
  ```bash
  ruff check .
  # or
  make lint
  ```
- [ ] Run type checking
  ```bash
  mypy claude_orchestrator --ignore-missing-imports
  # or
  make type-check
  ```

### 7. Security Review
- [ ] Run security audit
  ```bash
  co security-audit
  ```
- [ ] Verify no hardcoded secrets
  ```bash
  rg -i "sk-[a-zA-Z0-9\-]{40,}" --type py
  ```
- [ ] Check file permissions
  ```bash
  ls -la .env*
  ```
- [ ] Review `.gitignore` for sensitive files
- [ ] Ensure no personal/temporary files in repository

## Production Deployment

### 1. System Requirements
- **CPU**: 2+ cores recommended for parallel workers
- **Memory**: 4GB+ RAM (depends on task complexity)
- **Storage**: 10GB+ free space for logs and checkpoints
- **Network**: Stable internet connection for API calls

### 2. Environment Variables
```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional
export ORCHESTRATOR_CONFIG="/path/to/config.json"
export ORCHESTRATOR_LOG_LEVEL="INFO"
export ORCHESTRATOR_WORKING_DIR="/path/to/projects"
```

### 3. Service Setup (Optional)
For running as a service, create a systemd unit file:

```ini
[Unit]
Description=Claude Orchestrator Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/claude-orchestrator
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python -m claude_orchestrator.main run
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Monitoring and Logging
- [ ] Configure log rotation
  ```bash
  # Example logrotate config
  /path/to/logs/*.log {
      daily
      rotate 7
      compress
      delaycompress
      missingok
      notifempty
  }
  ```
- [ ] Set up monitoring for:
  - [ ] API rate limits
  - [ ] Worker failures
  - [ ] Disk space usage
  - [ ] Memory usage

### 5. Backup Strategy
- [ ] Regular backup of `.taskmaster/` directory
- [ ] Backup of configuration files
- [ ] Checkpoint retention policy configured

## Post-Deployment Verification

### 1. Functional Tests
- [ ] Create and execute a simple task
  ```bash
  co add "Post-deployment test task"
  co run --id <task-id>
  ```
- [ ] Verify worker parallel execution
  ```bash
  co add "Task 1: Quick test"
  co add "Task 2: Another test"
  co run --workers 2
  ```
- [ ] Test rollback functionality
  ```bash
  co checkpoint "Test checkpoint"
  co list-checkpoints
  ```

### 2. Performance Verification
- [ ] Monitor initial task execution times
- [ ] Check API usage dashboard
- [ ] Verify no memory leaks during extended runs

### 3. Integration Tests
- [ ] Test Slack notifications (if configured)
- [ ] Verify file system operations work correctly
- [ ] Test error handling and recovery

## Troubleshooting

### Common Issues

1. **API Key Issues**
   ```bash
   co check  # Validates configuration
   co security-audit  # Checks for security issues
   ```

2. **Permission Errors**
   ```bash
   # Fix .env permissions
   chmod 600 .env
   
   # Fix directory permissions
   chmod 755 .taskmaster/
   ```

3. **Import Errors**
   ```bash
   # Reinstall in development mode
   pip install -e .
   
   # Verify PYTHONPATH
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

4. **Worker Failures**
   - Check logs in `.taskmaster/logs/`
   - Reduce worker count if hitting rate limits
   - Increase timeouts for complex tasks

## Maintenance

### Regular Tasks
- [ ] Weekly: Review and clean old logs
- [ ] Weekly: Run security audit
- [ ] Monthly: Update dependencies
- [ ] Monthly: Review and optimize configuration

### Updates
```bash
# Update code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Run tests
make test

# Restart service if running as daemon
systemctl restart claude-orchestrator
```

## Rollback Procedure

If issues occur after deployment:

1. **Immediate Rollback**
   ```bash
   # List available checkpoints
   co list-checkpoints
   
   # Rollback to previous checkpoint
   co rollback <checkpoint-id>
   ```

2. **Code Rollback**
   ```bash
   # Revert to previous git commit
   git log --oneline -10
   git checkout <previous-commit-hash>
   ```

3. **Database Recovery**
   ```bash
   # Restore task database from backup
   cp .taskmaster/tasks/tasks.json.backup .taskmaster/tasks/tasks.json
   ```

## Success Criteria

Deployment is considered successful when:
- [ ] All pre-flight checks pass
- [ ] Test suite runs with >70% coverage
- [ ] Security audit shows no critical issues
- [ ] Can successfully create and execute tasks
- [ ] Workers execute in parallel without errors
- [ ] No memory leaks after 1 hour of operation

---

**Last Updated**: 2025-07-07
**Version**: 2.0