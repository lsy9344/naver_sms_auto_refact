# Slack Integration Configuration

**Story 4.4 AC 7:** Slack notification executor configuration and validation alongside Telegram alerts

## Overview

The Naver SMS Automation system supports dual-channel notifications via Slack and Telegram. This guide explains how to configure, enable/disable, and troubleshoot Slack notifications for release reporting and operational alerts.

---

## Configuration

### Environment Variables

Slack integration is configured via environment variables sourced from AWS Secrets Manager or local `.env` files.

#### Required Keys

```bash
# Slack bot token (OAuth token for app authentication)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

# Global enable/disable flag (boolean, default: false)
SLACK_ENABLED=true

# Alert channels configuration
SLACK_CHANNEL_ALERTS=#naver-sms-alerts
SLACK_CHANNEL_BOOKINGS=#naver-sms-bookings
SLACK_CHANNEL_DEBUG=#naver-sms-debug
```

#### Optional Keys

```bash
# Slack workspace domain (for logs, optional)
SLACK_WORKSPACE=your-workspace.slack.com

# Thread metadata (optional)
SLACK_THREAD_TS=                    # Parent message timestamp for threading

# Retry configuration (optional, defaults shown)
SLACK_RETRY_MAX_ATTEMPTS=3
SLACK_RETRY_DELAY_SECONDS=5
```

### Local Development Setup

#### Step 1: Create `.env` File

```bash
cd /path/to/naver_sms_automation_refactoring
cp .env.example .env
```

Edit `.env` with your Slack credentials:

```bash
# .env (local development)
SLACK_ENABLED=true
SLACK_BOT_TOKEN=xoxb-your-test-bot-token
SLACK_CHANNEL_ALERTS=#naver-sms-dev-alerts
SLACK_CHANNEL_BOOKINGS=#naver-sms-dev-bookings
SLACK_CHANNEL_DEBUG=#naver-sms-dev-debug

# For testing without real Slack
# SLACK_ENABLED=false
```

#### Step 2: Verify Configuration

```bash
# Source environment
source .env

# Verify variables are loaded
python -c "import os; print(f'Slack Enabled: {os.getenv(\"SLACK_ENABLED\")}'); print(f'Bot Token Set: {bool(os.getenv(\"SLACK_BOT_TOKEN\"))}')"
```

#### Step 3: Run Tests with Slack Support

```bash
# Run Slack integration tests
pytest tests/integration/test_slack_integration.py -v

# Run with Slack enabled in context
pytest tests/integration/test_slack_integration.py -v -k "slack_honored_when_enabled"
```

---

## Channel Routing

Messages are routed to appropriate channels based on severity and message type:

| Channel | Message Type | Conditions |
|---------|-------------|------------|
| `#naver-sms-alerts` | Critical failures, errors | severity=critical, SLACK_ENABLED=true |
| `#naver-sms-bookings` | Booking confirmations, completion reports | type=booking_report, SLACK_ENABLED=true |
| `#naver-sms-debug` | Debug logs, detailed trace information | SLACK_ENABLED=true AND DEBUG=true |

### Example Channel Configuration

```bash
# Production channels (restricted access)
SLACK_CHANNEL_ALERTS=#naver-sms-production-alerts
SLACK_CHANNEL_BOOKINGS=#naver-sms-production-reports

# Development/test channels (public)
SLACK_CHANNEL_ALERTS=#naver-sms-dev-alerts
SLACK_CHANNEL_BOOKINGS=#naver-sms-dev-bookings
SLACK_CHANNEL_DEBUG=#naver-sms-dev-debug
```

---

## Enable/Disable Behavior

### Enabling Slack Notifications

When `SLACK_ENABLED=true`:

1. All configured notification actions execute
2. Messages are sent to specified channels
3. Failures in Slack sending are logged but do NOT block execution
4. Telegram notifications continue regardless of Slack status

```python
# Example: Rule engine behavior
context = {
    "slack_enabled": True,
    "booking_id": "booking_001"
}

# Both Slack AND Telegram actions execute
results = engine.process_booking(context)
```

### Disabling Slack Notifications

When `SLACK_ENABLED=false`:

1. Slack notification actions are skipped
2. Telegram notifications continue to execute
3. No Slack API calls are made
4. Reduces network calls and latency

```python
# Example: Rule engine behavior
context = {
    "slack_enabled": False,
    "booking_id": "booking_001"
}

# Only Telegram actions execute, Slack actions skipped
results = engine.process_booking(context)
```

### Testing Enable/Disable

```bash
# Test with Slack enabled
SLACK_ENABLED=true pytest tests/integration/test_slack_integration.py::TestSlackConfigurationFlags::test_slack_honored_when_enabled -v

# Test with Slack disabled
SLACK_ENABLED=false pytest tests/integration/test_slack_integration.py::TestSlackConfigurationFlags::test_slack_skipped_when_disabled -v
```

---

## Message Formatting

### Payload Structure

All Slack messages follow this structure:

```json
{
  "channel": "#naver-sms-alerts",
  "text": "Message content with emoji indicators",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Booking Status*\nID: booking_001\nStatus: ✅ Confirmed"
      }
    }
  ]
}
```

### Message Formatting Examples

**Success Message:**
```
✅ New booking confirmed
ID: booking_001
Phone: 010****1234 (masked)
Time: 14:30 KST
```

**Error Message:**
```
🚨 CRITICAL: SMS service unavailable
Error: SENS API timeout after 30 seconds
Action: Will retry in 5 minutes
```

**Warning Message:**
```
⚠️ Database operation failed
Operation: Update booking record
Error: Provisioned throughput exceeded
Status: Request queued for retry
```

---

## Retry Logic

Slack integration includes automatic retry for temporary failures:

```python
# Default retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
BACKOFF_MULTIPLIER = 2

# Retry on these errors:
# - ConnectionError (temporary network issues)
# - TimeoutError (Slack API timeout)
# - 429 Too Many Requests (rate limiting)

# Do NOT retry on these errors:
# - 401 Unauthorized (invalid token)
# - 403 Forbidden (bot lacks permissions)
# - 404 Not Found (invalid channel)
```

### Monitoring Retry Behavior

```bash
# View retry logs
grep -i "retry\|attempt" .ai/debug-log.md | tail -20

# Enable debug logging for retry details
DEBUG=true pytest tests/integration/test_slack_integration.py -v -s
```

---

## Dual-Channel Notifications

Slack and Telegram notifications work together seamlessly:

### Execution Order

1. **Slack notifications** sent first (if enabled)
2. **Telegram notifications** sent second (always enabled)
3. If either fails, the other continues
4. Execution errors are logged but do not stop processing

### Example Execution Flow

```
Rule Engine Processes Booking
    ↓
    ├─→ Slack Action (if SLACK_ENABLED=true)
    │   ├─→ Send to #naver-sms-alerts
    │   └─→ Log result (success or retry)
    │
    ├─→ Telegram Action (always executes)
    │   ├─→ Send to Telegram chat
    │   └─→ Log result
    │
    └─→ Continue Processing
        (regardless of notification success/failure)
```

### Testing Dual Notifications

```bash
# Test both Slack and Telegram sent
pytest tests/integration/test_slack_integration.py::TestSlackAndTelegramCoexistence::test_slack_and_telegram_both_executed -v

# Test execution order preserved
pytest tests/integration/test_slack_integration.py::TestSlackAndTelegramCoexistence::test_notification_order_preserved -v
```

---

## Error Scenarios

### Connection Failures

**Error:** `ConnectionError: Failed to connect to slack.com`

**Solution:**
```bash
# 1. Verify network connectivity
ping slack.com

# 2. Check bot token validity
python -c "
from slack_sdk import WebClient
client = WebClient(token='xoxb-your-token')
auth_test = client.auth_test()
print(f'Valid: {auth_test[\"ok\"]}, User: {auth_test.get(\"user_id\")}'
)
"

# 3. Verify Slack is not blocked by firewall
telnet slack.com 443
```

### Authentication Failures

**Error:** `401 Unauthorized - invalid_token`

**Solution:**
```bash
# 1. Verify token format (should start with xoxb- or xoxp-)
echo $SLACK_BOT_TOKEN | grep -E "^xoxb-|^xoxp-"

# 2. Regenerate token in Slack workspace settings
# Settings → Apps & integrations → Custom apps → Bot User OAuth Token → Regenerate

# 3. Update .env and redeploy
SLACK_BOT_TOKEN=xoxb-new-token
```

### Channel Access Denied

**Error:** `403 Forbidden - not_in_channel`

**Solution:**
```bash
# 1. Add bot to channel
# Open Slack channel → Details → Integrations → Add app

# 2. Or create channel if it doesn't exist
# Use Slack CLI: slack channels create naver-sms-alerts

# 3. Verify channel name matches exactly (case-sensitive in config)
```

### Rate Limiting

**Error:** `429 Too Many Requests`

**Solution:**
```bash
# Increase retry delay in .env
SLACK_RETRY_MAX_ATTEMPTS=5
SLACK_RETRY_DELAY_SECONDS=10

# Or implement exponential backoff (already configured)
# Each retry doubles the delay: 5s → 10s → 20s → 40s
```

### Message Too Long

**Error:** `message_text_too_long - Message text exceeds 4000 characters`

**Solution:**
```python
# Truncate message to 4000 characters
message = message[:4000]

# Or split into multiple messages
if len(message) > 4000:
    messages = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for msg in messages:
        send_slack(msg)
```

---

## Testing

### Unit Tests

Run Slack executor tests in isolation:

```bash
# Test Slack executor registration and basic functionality
pytest tests/integration/test_slack_integration.py::TestSlackNotificationExecutor -v

# Test Slack payload structure validation
pytest tests/integration/test_slack_integration.py::TestSlackNotificationExecutor::test_slack_payload_structure_valid -v

# Test channel routing
pytest tests/integration/test_slack_integration.py::TestSlackNotificationExecutor::test_slack_channel_routing_correct -v
```

### Integration Tests

Test Slack with other components:

```bash
# Test Slack + Telegram coexistence
pytest tests/integration/test_slack_integration.py::TestSlackAndTelegramCoexistence -v

# Test enable/disable flags
pytest tests/integration/test_slack_integration.py::TestSlackConfigurationFlags -v

# Test error scenarios
pytest tests/integration/test_slack_integration.py::TestSlackErrorNotifications -v
```

### Full Test Suite

```bash
# Run all Slack integration tests
pytest tests/integration/test_slack_integration.py -v

# Run with coverage
pytest tests/integration/test_slack_integration.py -v --cov=src/rules --cov-report=html

# Run in parallel
pytest tests/integration/test_slack_integration.py -v -n auto
```

---

## Troubleshooting

### Debug Logging

Enable detailed logs:

```bash
# Set debug level
DEBUG=true

# Re-run tests with verbose output
pytest tests/integration/test_slack_integration.py -v -s --log-cli-level=DEBUG

# Check debug log file
tail -100 .ai/debug-log.md
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| No messages in Slack | `SLACK_ENABLED=false` | Set to `true` in .env |
| Messages in wrong channel | Channel name mismatch | Verify `SLACK_CHANNEL_*` matches config |
| Timeout errors | Network latency or Slack API slow | Increase `SLACK_RETRY_DELAY_SECONDS` |
| Memory issues with large messages | Message payload too large | Implement truncation logic |
| Tests fail locally but pass in CI | Environment variable mismatch | Use `source .env` before running tests |

### Verification Checklist

Before deploying to production:

- [ ] `SLACK_BOT_TOKEN` is valid (starts with `xoxb-`)
- [ ] Bot is added to all configured channels
- [ ] Channel names in `SLACK_CHANNEL_*` match actual channels
- [ ] `SLACK_ENABLED=true` is set in production environment
- [ ] Retry configuration is appropriate for expected traffic
- [ ] All Slack integration tests pass: `pytest tests/integration/test_slack_integration.py -v`
- [ ] Dual-channel tests pass: `pytest tests/integration/test_slack_integration.py::TestSlackAndTelegramCoexistence -v`
- [ ] Manual test message sent successfully
- [ ] Error scenarios tested (e.g., disable bot temporarily and verify graceful fallback)

---

## Production Deployment

### Pre-Deployment Checklist

```bash
# 1. Verify all tests pass
make test-all

# 2. Verify Slack configuration
python -c "
import os
from slack_sdk import WebClient

token = os.getenv('SLACK_BOT_TOKEN')
if not token:
    raise ValueError('SLACK_BOT_TOKEN not set')

client = WebClient(token=token)
auth = client.auth_test()
print(f'✅ Slack Auth Valid: {auth[\"ok\"]}')
print(f'   User: {auth[\"user_id\"]}')
print(f'   Team: {auth[\"team_id\"]}')
"

# 3. Test channel connectivity
python -c "
import os
from slack_sdk import WebClient

client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))
channels = [
    os.getenv('SLACK_CHANNEL_ALERTS'),
    os.getenv('SLACK_CHANNEL_BOOKINGS'),
]
for ch in channels:
    if not ch:
        continue
    try:
        result = client.conversations_info(channel=ch)
        print(f'✅ {ch}: accessible')
    except Exception as e:
        print(f'❌ {ch}: {e}')
"

# 4. Run Slack tests
pytest tests/integration/test_slack_integration.py -v

# 5. Deploy with confidence
git push origin feature/slack-integration
```

### Post-Deployment Validation

```bash
# 1. Check recent Slack messages in #naver-sms-alerts
# (Should see test message if deployment successful)

# 2. Monitor for errors in CloudWatch logs
aws logs tail /aws/lambda/naver-sms-automation --follow

# 3. Verify both Slack and Telegram alerts working
# Trigger a test booking and verify messages in both channels

# 4. Set up Slack workflow for escalation (optional)
# Configure #naver-sms-alerts to notify on-call engineer
```

---

## Best Practices

1. **Keep bot token secure** - Use AWS Secrets Manager, never commit to git
2. **Use appropriate channels** - Separate critical alerts from routine reports
3. **Implement rate limiting** - Avoid spam in Slack channels
4. **Monitor retry behavior** - Set up CloudWatch alerts for persistent failures
5. **Test both paths** - Always test with `SLACK_ENABLED=true` and `false`
6. **Use threading** - Group related messages using `thread_ts` for better organization
7. **Implement rich formatting** - Use blocks and attachments for better UX
8. **Document runbooks** - Keep Slack channel description with troubleshooting links

---

## References

- Slack SDK: https://slack.dev/python-slack-sdk/
- Slack API Docs: https://api.slack.com/
- Story 4.4 Tests: `tests/integration/test_slack_integration.py`
- Architecture: `docs/brownfield-architecture.md#action-executors`
- Integration Testing Guide: `docs/testing/integration-testing.md`
