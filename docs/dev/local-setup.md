# Local Development Setup Guide

**Story 4.4 AC 4:** Developer-facing documentation for container build, execution, and integration testing

## Prerequisites

- **Docker Desktop** (for container-based Lambda testing)
- **Python 3.11+** (for local development)
- **AWS CLI v2** (configured with valid credentials)
- **Git** (for version control)
- **Make** (for build automation)

## Quick Start

### Step 1: Clone and Setup Environment

```bash
# Clone repository
git clone <your-repo-url>
cd naver_sms_automation_refactoring

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Secrets

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` with your credentials from AWS Secrets Manager:

```bash
# Naver Authentication
NAVER_USERNAME=your_username
NAVER_PASSWORD=your_password

# SENS SMS API
SENS_ACCESS_KEY=your_access_key
SENS_SECRET_KEY=your_secret_key
SENS_SERVICE_ID=your_service_id

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Slack (optional)
SLACK_ENABLED=false

# AWS
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

**⚠️ WARNING:** Never commit `.env` file to git. Add to `.gitignore`.

### Step 3: Verify Installation

```bash
# Run unit tests
make test-unit

# Run integration tests
make test-integration

# Run all tests
make test-all
```

## Docker Container Setup

### Building the Container

```bash
# Build container image
docker build -t naver-sms-automation:latest .

# Tag for ECR
docker tag naver-sms-automation:latest \
  654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest
```

### Running Locally with Lambda RIE

The **Lambda Runtime Interface Emulator** allows testing Lambda functions locally:

```bash
# Start container with Lambda RIE
docker run --rm \
  -p 9000:8080 \
  --env-file .env \
  naver-sms-automation:latest

# In another terminal, invoke the function:
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"scenario": "test_booking_001"}' \
  -H "Content-Type: application/json"
```

## Running Tests Locally

### Unit Tests Only

```bash
# Run unit tests with coverage
python -m pytest tests/unit/ -v --cov=src --cov-report=html

# Open HTML report
open htmlcov/index.html
```

### Integration Tests

```bash
# Run integration tests
python -m pytest tests/integration/ -v

# Run regression tests (all bookings)
python -m pytest tests/integration/test_rules_regression.py -v

# Run failure scenario tests (new in Story 4.4)
python -m pytest tests/integration/test_failure_scenarios.py -v

# Run Slack integration tests (new in Story 4.4)
python -m pytest tests/integration/test_slack_integration.py -v
```

### Comparison/Parity Tests

```bash
# Run comparison tests between implementations
python -m pytest tests/comparison/test_output_parity.py -v

# Run all scenarios parity check
python -m pytest tests/comparison/test_output_parity.py::TestOutputParity::test_all_scenarios_parity -v

# Run masking validation
python -m pytest tests/comparison/test_output_parity.py::TestOutputParity::test_masking_enforcement -v
```

## Using Make Commands

```bash
# Display all available commands
make help

# Code formatting with Black
make fmt

# Linting and type checking
make lint

# Run all tests except comparison
make test

# Run unit tests only
make test-unit

# Run integration tests
make test-integration

# Run comparison/parity tests
make comparison-test

# Run all tests including comparison
make test-all

# Clean build artifacts
make clean

# Refresh comparison fixtures
make comparison-refresh
```

## Debugging

### Local Debugging

```bash
# Run tests with verbose output
python -m pytest tests/integration/test_rules_regression.py::TestRulesRegression::test_booking_001_new_confirmation -v -s

# Use Python debugger - add this in test:
# import pdb; pdb.set_trace()
```

### Viewing Test Results

```bash
# Generate HTML coverage report
python -m pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# View comparison test artifacts
ls -la tests/comparison/results/

# View regression test artifacts
ls -la tests/integration/artifacts/rule_engine_regression/
```

## Environment Variables Reference

### Required

```bash
AWS_REGION                  # AWS region (default: ap-northeast-2)
```

### Development Only

```bash
NAVER_USERNAME              # Naver login username
NAVER_PASSWORD              # Naver login password
SENS_ACCESS_KEY            # SENS API access key
SENS_SECRET_KEY            # SENS API secret key
SENS_SERVICE_ID            # SENS service ID
TELEGRAM_BOT_TOKEN         # Telegram bot token
TELEGRAM_CHAT_ID           # Telegram chat ID
```

### Optional

```bash
SLACK_ENABLED              # Enable/disable Slack (default: false)
DEBUG                      # Enable debug logging (default: false)
```

## Troubleshooting

### Tests Fail with Import Errors

```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Clear Python cache
make clean
```

### Coverage Threshold Failures

When running tests, if coverage is below 80%:

```bash
# Generate detailed coverage report
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# View which lines need coverage
open htmlcov/index.html
```

### Docker Build Issues

```bash
# Clear Docker cache and rebuild
docker system prune -a
docker build --no-cache -t naver-sms-automation:latest .
```

## Contributing

### Before Committing

```bash
# Format code
make fmt

# Lint and type check
make lint

# Run all tests
make test-all
```

## Next Steps

- **Integration Testing Guide:** See `docs/testing/integration-testing.md`
- **Architecture:** See `docs/brownfield-architecture.md`
