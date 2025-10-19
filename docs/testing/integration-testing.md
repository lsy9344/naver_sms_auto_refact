# Integration Testing Guide

**Story 4.4 AC 4:** Regression harness documentation with Lambda RIE invocation and required environment variables

## Overview

This guide explains how to run the integration and comparison testing suite for the Naver SMS Automation system. The testing framework validates that the refactored system produces identical results to the legacy implementation.

## Test Types

### 1. Regression Tests (`tests/integration/test_rules_regression.py`)

Validates that the new rule engine produces identical action sequences to the legacy system.

**Purpose:** Ensure business logic parity between implementations

**Run command:**
```bash
python -m pytest tests/integration/test_rules_regression.py -v
```

**Key tests:**
- `test_regression_suite` - Run all 15 booking fixtures
- `test_booking_001_new_confirmation` - New booking scenario
- `test_booking_002_two_hour_reminder` - Reminder window scenario
- `test_booking_003_evening_option_sms` - Option keyword at 8 PM
- `test_booking_004_all_flags_set` - No actions execute
- `test_booking_005_no_keyword` - Non-matching keyword

**Expected output:**
```
tests/integration/test_rules_regression.py::TestRulesRegression::test_regression_suite PASSED
6 passed in 1.23s
```

### 2. Failure Scenario Tests (`tests/integration/test_failure_scenarios.py`)

**NEW in Story 4.4** - Tests error handling and Telegram alert pathways (AC 2, 7)

**Purpose:** Validate resilience and proper error notification

**Run command:**
```bash
python -m pytest tests/integration/test_failure_scenarios.py -v
```

**Test categories:**

- **Naver API Failures** (4 tests)
  - API timeout
  - Session expiry
  - Rate limiting (429)
  - Authentication failure (401)

- **DynamoDB Failures** (3 tests)
  - Connection timeout
  - Table not found
  - Provisioned throughput exceeded

- **SMS Service Failures** (3 tests)
  - Authentication failure
  - Service timeout
  - Invalid phone number

- **Telegram Alert Pathway** (3 tests)
  - Success alerts sent
  - Payload structure validation
  - Critical failure alerts

- **End-to-End Recovery** (2 tests)
  - Lambda completes despite errors
  - Error context captured for debugging

**Expected output:**
```
tests/integration/test_failure_scenarios.py::TestNaverAPIFailureHandling::test_naver_api_timeout_graceful_handling PASSED
[... 14 more tests ...]
15 passed in 0.89s
```

### 3. Slack Integration Tests (`tests/integration/test_slack_integration.py`)

**NEW in Story 4.4** - Tests Slack notification executor (AC 7)

**Purpose:** Validate Slack notifications work alongside Telegram

**Run command:**
```bash
python -m pytest tests/integration/test_slack_integration.py -v
```

**Test categories:**

- **Slack Executor** (4 tests)
  - Executor registration
  - Payload structure
  - Channel routing
  - Message formatting

- **Slack + Telegram Coexistence** (2 tests)
  - Both notifications executed
  - Execution order preserved

- **Configuration Flags** (2 tests)
  - Slack honored when enabled
  - Slack skipped when disabled

- **Retry Logic** (2 tests)
  - Retry on temporary failure
  - Failure after max retries

- **Error Notifications** (2 tests)
  - Critical SMS alerts
  - Warning DB alerts

- **Documentation** (2 tests)
  - Secret Manager keys documented
  - Enable flag available in context

**Expected output:**
```
tests/integration/test_slack_integration.py::TestSlackNotificationExecutor::test_slack_executor_registered PASSED
[... 13 more tests ...]
14 passed in 0.70s
```

### 4. Comparison/Parity Tests (`tests/comparison/test_output_parity.py`)

Replays production bookings through both implementations and asserts SMS, DynamoDB, and Telegram outputs match exactly.

**Purpose:** Comprehensive parity validation before production cutover

**Run command:**
```bash
python -m pytest tests/comparison/test_output_parity.py -v
```

**Key tests:**
- `test_all_scenarios_parity` - Master parity suite
- `test_masking_enforcement` - Validates PII is not stored in reports
- `test_determinism` - Execution is deterministic
- `test_idempotency` - No duplicate effects on repeated runs
- `TestComparisonFixtures` - Fixture integrity

## Running All Integration Tests

```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Run with coverage report
python -m pytest tests/integration/ -v --cov=src --cov-report=html

# Run with specific markers
python -m pytest tests/integration/ -v -m "not slow"
```

## Running All Tests (Unit + Integration + Comparison)

```bash
# Run complete test suite
make test-all

# Or manually:
python -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
```

## Docker-based Testing

### Build Container for Testing

```bash
# Build test container
docker build -t naver-sms-automation:test .
```

### Run Integration Tests in Container

```bash
# Start container with volume mount
docker run --rm \
  --env-file .env \
  -v $(pwd)/tests:/app/tests \
  -v $(pwd)/src:/app/src \
  naver-sms-automation:test \
  python -m pytest tests/integration/ -v
```

### Lambda RIE Invocation Testing

```bash
# Start container with Lambda RIE
docker run --rm \
  -p 9000:8080 \
  --env-file .env \
  naver-sms-automation:latest

# In another terminal, invoke via RIE:
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{
    "scenario": "test_booking_001",
    "booking_id": "case1_new_booking_001",
    "test_mode": true
  }' \
  -H "Content-Type: application/json"
```

**Expected response:**
```json
{
  "statusCode": 200,
  "body": "{\"success\": true, \"processed_bookings\": 1, \"sms_sent\": 1}",
  "timestamp": "2025-10-20T12:34:56Z"
}
```

## Test Fixtures

### Fixture Location

```
tests/fixtures/
├── production_bookings.json          # 15 booking scenarios
├── production_expected_outputs.json  # Expected outputs for each
├── legacy_bookings.json              # Legacy system data
├── legacy_expected_actions.json      # Legacy action sequences
├── dataset_manifest.json             # Fixture documentation
└── sens/                             # SENS API test data
```

### Loading Fixtures in Tests

```python
from tests.comparison.comparison_factory import ComparisonFactory

# Load bookings
bookings = ComparisonFactory().load_bookings_fixture()
for booking in bookings["bookings"]:
    booking_id = booking["booking_id"]
    # Test with booking
```

### Refreshing Fixtures

When adding new edge cases:

```bash
# Refresh comparison fixtures
make comparison-refresh

# Or manually:
python scripts/comparison/refresh_comparison_dataset.py
```

## Test Results and Artifacts

### Regression Test Artifacts

```
tests/integration/artifacts/rule_engine_regression/
├── summary.json          # Aggregate results
└── {booking_id}.json     # Per-booking details (only on failure)
```

### Comparison Test Artifacts

```
tests/comparison/results/
├── {booking_id}.json     # Detailed comparison results
├── {booking_id}.md       # Human-readable diff
└── aggregate_summary.json # Aggregate statistics
```

### Viewing Artifacts

```bash
# View regression summary
cat tests/integration/artifacts/rule_engine_regression/summary.json | jq

# View comparison results
ls -lah tests/comparison/results/

# View specific failure details
cat tests/comparison/results/case1_new_booking_001.md
```

## Coverage Requirements

All tests must meet **≥80% code coverage** for `src/` directory:

```bash
# Check coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML report
python -m pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

## Environment Variables for Testing

### Required

```bash
# AWS Configuration
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret

# Naver
NAVER_USERNAME=test_user
NAVER_PASSWORD=test_password

# SENS SMS
SENS_ACCESS_KEY=test_key
SENS_SECRET_KEY=test_secret
SENS_SERVICE_ID=test_service

# Telegram (for alert testing)
TELEGRAM_BOT_TOKEN=test_token
TELEGRAM_CHAT_ID=test_chat
```

### Optional

```bash
# Slack (for Slack integration tests)
SLACK_ENABLED=true
SLACK_BOT_TOKEN=xoxb-slack-token

# Debug Mode
DEBUG=true
```

## CI/CD Integration

### GitHub Actions

Tests run automatically on:
- Push to main/develop branches
- Pull requests
- Manual trigger

**Workflow files:**
- `.github/workflows/test.yml` - Unit & integration tests
- `.github/workflows/comparison-tests.yml` - Parity validation

**View results:**
```bash
# View workflow runs
gh run list

# View specific run
gh run view <run-id>

# Download artifacts
gh run download <run-id> -n comparison-results
```

## Troubleshooting

### Tests Timeout

Increase pytest timeout:

```bash
python -m pytest tests/integration/ --timeout=300 -v
```

### Import Errors

```bash
# Rebuild dependencies
pip install --force-reinstall -r requirements.txt

# Clear caches
make clean
python -m pytest --cache-clear
```

### Fixture-related Failures

```bash
# Verify fixtures are valid
python -m pytest tests/comparison/test_output_parity.py::TestComparisonFixtures -v

# Regenerate if corrupted
make comparison-refresh
```

### Local vs CI Differences

```bash
# Match CI environment locally
python -m pytest tests/ --cov=src --cov-fail-under=80 -v

# If CI passes but local fails:
# 1. Verify Python version: python --version (should be 3.11+)
# 2. Check dependencies: pip list | grep -E "(pytest|coverage)"
# 3. Clear all caches: make clean && pip install --force-reinstall -r requirements.txt
```

## Performance Optimization

### Running Tests Faster

```bash
# Skip slow tests
python -m pytest tests/ -m "not slow" -v

# Run in parallel (requires pytest-xdist)
pip install pytest-xdist
python -m pytest tests/ -n auto -v
```

### Profiling Tests

```bash
# Show slowest tests
python -m pytest tests/integration/ --durations=10 -v

# Profile specific test
python -c "
import cProfile
import pstats
from tests.integration import test_rules_regression
cProfile.run('test_rules_regression.TestRulesRegression().test_regression_suite()', 'profile.prof')
stats = pstats.Stats('profile.prof')
stats.sort_stats('cumulative').print_stats(10)
"
```

## Best Practices

### Writing New Integration Tests

1. **Use existing fixtures** - Leverage `tests/fixtures/production_bookings.json`
2. **Test edge cases** - Include error scenarios and boundary conditions
3. **Mock external services** - Use `unittest.mock` for SENS, Telegram, Slack
4. **Assert behavior** - Check both success and failure paths
5. **Document purpose** - Add docstrings explaining test intent

### Example Test Pattern

```python
def test_my_scenario(self):
    """Test description explaining business scenario"""
    engine = RuleEngine(str(rules_file))
    
    # Setup conditions
    engine.register_condition("my_condition", lambda ctx, **p: ctx.get("flag"))
    
    # Setup actions with tracking
    results_captured = []
    engine.register_action("my_action", lambda ctx, **p: results_captured.append(ctx))
    
    # Execute
    context = {"flag": True}
    results = engine.process_booking(context)
    
    # Assert
    assert len(results) > 0
    assert results[0].success is True
    assert len(results_captured) == 1
```

## Next Steps

- **Local Setup:** See `docs/dev/local-setup.md`
- **CI/CD:** See `.github/workflows/`
- **Architecture:** See `docs/brownfield-architecture.md`
