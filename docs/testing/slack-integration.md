# Slack Integration Configuration - Story 6.2

**Story 6.2:** Add Slack Integration with webhook delivery and template rendering

## Overview

The Naver SMS Automation system sends Slack notifications through webhook delivery with Jinja2 template rendering. This guide explains how to configure, enable/disable, and troubleshoot Slack notifications for booking alerts and operational events.

### Key Features

- **Webhook-only delivery** (AC 1): Uses incoming webhooks for simplicity and scalability
- **Template rendering** (AC 3): Supports Jinja2 templates from `config/slack_templates.yaml`
- **Graceful toggle** (AC 2): Disable Slack delivery via configuration flag without code changes
- **Automatic integration** (AC 4): Booking conditions automatically trigger Slack actions
- **Structured logging** (AC 1): All operations logged with redacted secrets

---

## Quick Start

### 1. Create Local Configuration

```bash
# Create slack webhook config for local development
cat > config/my_slack_webhook.yaml << 'EOF'
slack webhook url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
EOF
```

### 2. Enable Slack

```bash
# Set environment variable to enable
export SLACK_ENABLED=true
```

### 3. Run Tests

```bash
pytest tests/integration/test_slack_integration.py -v
```

---

## Configuration Files

### Local Development: `config/my_slack_webhook.yaml`

**Purpose:** Store webhook URL for local testing (DO NOT commit real webhook URLs)

```yaml
slack webhook url: https://hooks.slack.com/services/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
```

**Format:** Single key `slack webhook url` with YAML value

**Loading Priority:**
1. `SLACK_WEBHOOK_URL` environment variable (direct override)
2. `config/my_slack_webhook.yaml` (local development, via `SLACK_CONFIG_FILE`)
3. AWS Secrets Manager `naver-sms-automation/slack-credentials` (production)

### Message Templates: `config/slack_templates.yaml`

**Purpose:** Define Jinja2 templates for formatted Slack messages (AC 3)

```yaml
expert_correction_digest: |
  {{ today_date }} 보정 요청 리스트:
  {% for user in users %}
  {{ loop.index }}. {{ user.name }} - {{ user.count }}장
  {% endfor %}
```

**Available Variables:**
- `today_date`: Current date string
- `users`: List of user objects with name/count
- `booking`: Booking object (if applicable)
- Custom variables passed via `template_params`

**Example Rendering:**

```python
from src.rules.actions import SlackTemplateLoader

loader = SlackTemplateLoader()
rendered = loader.render(
    "expert_correction_digest",
    today_date="2025-10-22",
    users=[{"name": "User A", "count": 5}]
)
```

### Environment Variables

**Required:**
```bash
SLACK_ENABLED=true|false         # Enable/disable Slack notifications (default: false)
SLACK_CONFIG_FILE=config/my_slack_webhook.yaml  # Path to webhook config
```

**Optional (Overrides):**
```bash
SLACK_WEBHOOK_URL=...            # Direct webhook URL override (if set, used instead of config file)
```

---

## Usage Examples

### Example 1: Send Static Message

```python
from src.rules.actions import send_slack, ActionContext, SlackTemplateLoader
from src.notifications.slack_service import SlackWebhookClient
from src.config.settings import Settings

# Load webhook URL
webhook_url = Settings.load_slack_webhook_url()
slack_service = SlackWebhookClient(webhook_url=webhook_url)

# Create context
context = ActionContext(
    booking=booking,
    settings_dict={"slack_enabled": True},
    db_repo=db_repo,
    sms_service=sms_client,
    slack_service=slack_service,
    slack_template_loader=SlackTemplateLoader(),
    logger=logger,
)

# Send static message
send_slack(context, message="Booking confirmed for user")
```

### Example 2: Send Template-Rendered Message

```python
# Send template-rendered message
send_slack(
    context,
    template_name="expert_correction_digest",
    template_params={
        "today_date": "2025-10-22",
        "users": [
            {"name": "보정자 A", "count": 5},
            {"name": "보정자 B", "count": 3},
        ]
    }
)
```

### Example 3: Automatic Booking Condition Integration

```yaml
# rules.yaml - Slack triggered automatically when booking condition matches
rules:
  - name: "Expert Correction Alert"
    conditions:
      - type: "booking_contains_keyword"
        params:
          keyword: "expert correction"
    actions:
      - type: "send_slack"
        params:
          template_name: "expert_correction_digest"
          template_params:
            today_date: "{{ booking.booking_time }}"
            users: "{{ correction_users }}"
```

---

## Enable/Disable Behavior

### When Slack is ENABLED (`SLACK_ENABLED=true`)

1. ✅ `send_slack` action executes normally
2. ✅ Template is rendered if `template_name` provided
3. ✅ Webhook call is made to Slack
4. ✅ Failures are logged but do NOT block other actions
5. ✅ All secrets are redacted in logs

**Test:**
```bash
export SLACK_ENABLED=true
pytest tests/integration/test_slack_integration.py::TestSendSlackAction::test_send_slack_with_static_message -v
```

### When Slack is DISABLED (`SLACK_ENABLED=false`)

1. ✅ `send_slack` action returns early (no-op)
2. ✅ No webhook call made (saves network time)
3. ✅ No error raised (graceful skip)
4. ✅ Debug log written: "Slack is disabled, skipping notification"
5. ✅ Other rule actions continue normally

**Test:**
```bash
export SLACK_ENABLED=false
pytest tests/integration/test_slack_integration.py::TestSendSlackAction::test_send_slack_disabled_skips_delivery -v
```

---

## Template Rendering (AC 3)

### SlackTemplateLoader Class

Located in `src/rules/actions.py`

```python
class SlackTemplateLoader:
    """Loads and renders Jinja2 templates from config/slack_templates.yaml"""

    def __init__(self, template_path="config/slack_templates.yaml", logger=None):
        """Initialize loader"""

    def load_templates(self):
        """Load templates from YAML file (cached after first load)"""

    def render(self, template_name: str, **context) -> str:
        """Render template with variables"""

    def get_template_names(self) -> list:
        """List all available template names"""
```

### Rendering Examples

```python
from src.rules.actions import SlackTemplateLoader

loader = SlackTemplateLoader()

# Render with variables
message = loader.render(
    "expert_correction_digest",
    today_date="2025-10-22",
    users=[
        {"name": "User A", "count": 5},
        {"name": "User B", "count": 3},
    ]
)

# Output:
# 2025-10-22 보정 요청 리스트:
# 1. User A - 5장
# 2. User B - 3장
```

### Error Handling

```python
try:
    loader.render("nonexistent_template")
except ValueError as e:
    # ValueError: Template 'nonexistent_template' not found
    pass
```

---

## Webhook URL Configuration (AC 2)

### Priority Order

The system loads webhook URL with this priority:

**Priority 1: Environment Variable Override**
```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

**Priority 2: Local Config File** (recommended for development)
```yaml
# config/my_slack_webhook.yaml
slack webhook url: https://hooks.slack.com/services/...
```

**Priority 3: AWS Secrets Manager** (production)
```bash
# Create secret in Secrets Manager
aws secretsmanager create-secret \
    --name naver-sms-automation/slack-credentials \
    --secret-string '{"webhook_url": "https://hooks.slack.com/services/..."}'
```

### Getting Your Webhook URL

1. Go to Slack workspace: https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name your app, select workspace
4. Go to "Incoming Webhooks"
5. Click "Add New Webhook to Workspace"
6. Select channel and authorize
7. Copy webhook URL (starts with `https://hooks.slack.com/...`)

---

## Configuration Plumbing (AC 2)

### Settings Module

Located in `src/config/settings.py`

```python
# Constants
SLACK_ENABLED = os.getenv("SLACK_ENABLED", "false").lower() == "true"
SLACK_WEBHOOK_URL_ENV = os.getenv("SLACK_WEBHOOK_URL", None)
SLACK_CONFIG_FILE = os.getenv("SLACK_CONFIG_FILE", "config/my_slack_webhook.yaml")

# Methods
class Settings:
    @staticmethod
    def load_slack_webhook_url() -> Optional[str]:
        """Load webhook URL with priority: env → config file → Secrets Manager"""

# Convenience functions
def get_slack_webhook_url() -> Optional[str]:
    """Get Slack webhook URL"""
```

### Usage

```python
from src.config.settings import get_slack_webhook_url, SLACK_ENABLED

# Check if enabled
if SLACK_ENABLED:
    webhook_url = get_slack_webhook_url()
    slack_service = SlackWebhookClient(webhook_url=webhook_url)
```

---

## Integration with Booking Conditions (AC 4)

### Booking Condition Detection

Slack is triggered when booking conditions match:

```python
# From src/api/naver_booking.py
if "expert correction" in booking_data:
    # Rule engine detects this condition
    # Automatically triggers send_slack action
    # No separate configuration needed
```

### Example Flow

```
Booking API processes data
    ↓
    Detects "expert correction" keyword
    ↓
    Rule engine condition matches
    ↓
    send_slack action executes
    ↓
    Slack message sent to webhook
```

---

## Error Handling and Logging

### Error Scenarios

**Scenario 1: Missing webhook URL**
```
ActionExecutionError:
  executor_name: send_slack
  booking_id: store123_booking456
  error: RuntimeError("SlackWebhookClient not configured")
```

**Scenario 2: Template not found**
```
ActionExecutionError:
  executor_name: send_slack
  booking_id: store123_booking456
  error: ValueError("Template 'missing_template' not found")
```

**Scenario 3: Webhook delivery failed**
```
ActionExecutionError:
  executor_name: send_slack
  booking_id: store123_booking456
  error: SlackServiceError("Webhook responded with 401: invalid token")
```

### Logging Details

All operations log structured data:

```python
# Debug: Sending
{
  "operation": "send_slack",
  "booking_id": "store123_booking456",
  "template_name": "expert_correction_digest",
  "message_length": 256
}

# Info: Success
{
  "operation": "send_slack",
  "booking_id": "store123_booking456",
  "status": "Slack notification sent"
}

# Error: Failure
{
  "operation": "send_slack",
  "booking_id": "store123_booking456",
  "error": "SlackServiceError(...)"
}
```

**Secrets Redaction:** All webhook URLs, tokens, and sensitive data are redacted in logs as `***REDACTED***`

---

## Testing

### Unit Tests: Template Loader

```bash
# Test template loading and caching
pytest tests/integration/test_slack_integration.py::TestSlackTemplateLoader -v

# Test specific template rendering
pytest tests/integration/test_slack_integration.py::TestSlackTemplateLoader::test_template_render_with_variables -v
```

### Unit Tests: Send Slack Action

```bash
# Test action executor
pytest tests/integration/test_slack_integration.py::TestSendSlackAction -v

# Test static message
pytest tests/integration/test_slack_integration.py::TestSendSlackAction::test_send_slack_with_static_message -v

# Test template rendering
pytest tests/integration/test_slack_integration.py::TestSendSlackAction::test_send_slack_with_template_rendering -v

# Test disable toggle
pytest tests/integration/test_slack_integration.py::TestSendSlackAction::test_send_slack_disabled_skips_delivery -v
```

### Integration Tests: Configuration

```bash
# Test webhook URL loading
pytest tests/integration/test_slack_integration.py::TestSlackConfigurationPlumbing -v

# Test enable flag
pytest tests/integration/test_slack_integration.py::TestSlackConfigurationPlumbing::test_slack_enabled_flag_in_settings_dict -v
```

### Regression Tests

```bash
# Verify Slack disabled by default
pytest tests/integration/test_slack_integration.py::TestSlackRegressionDefaults::test_slack_disabled_in_regression_by_default -v

# Run all tests without coverage bloat
pytest tests/integration/test_slack_integration.py -v --tb=short
```

---

## Troubleshooting

### Problem: "Webhook URL not configured"

**Cause:** No webhook URL found in environment, config file, or Secrets Manager

**Solution:**
```bash
# Option 1: Set environment variable
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Option 2: Create config file
cat > config/my_slack_webhook.yaml << 'EOF'
slack webhook url: https://hooks.slack.com/services/...
EOF

# Option 3: Create Secrets Manager secret
aws secretsmanager create-secret \
    --name naver-sms-automation/slack-credentials \
    --secret-string '{"webhook_url": "https://hooks.slack.com/services/..."}'
```

### Problem: "Template not found"

**Cause:** Template name not in `config/slack_templates.yaml`

**Solution:**
```bash
# List available templates
python -c "
from src.rules.actions import SlackTemplateLoader
loader = SlackTemplateLoader()
print('Available templates:', loader.get_template_names())
"

# Add missing template to config/slack_templates.yaml
echo 'new_template: |
  Your message: {{ variable }}' >> config/slack_templates.yaml
```

### Problem: "Slack is disabled"

**Cause:** `SLACK_ENABLED=false` or not set

**Solution:**
```bash
# Enable Slack
export SLACK_ENABLED=true

# Verify it's set
echo $SLACK_ENABLED
```

---

## Operator Checklist

**Before enabling Slack in production:**

- [ ] Webhook URL is from valid Slack workspace
- [ ] Webhook URL is stored securely (AWS Secrets Manager)
- [ ] `SLACK_ENABLED=true` is set in production environment
- [ ] All tests pass: `pytest tests/integration/test_slack_integration.py -v`
- [ ] Test message sent successfully to webhook
- [ ] Error handling verified (test with invalid webhook)
- [ ] Log redaction verified (check logs contain no exposed tokens)
- [ ] Rollback plan documented (disable via `SLACK_ENABLED=false`)

**To disable Slack (emergency rollback):**

```bash
# Option 1: Environment variable
export SLACK_ENABLED=false

# Option 2: Update Lambda config
aws lambda update-function-configuration \
    --function-name naver-sms-automation \
    --environment Variables={SLACK_ENABLED=false}

# No code rollback needed - configuration toggle is sufficient
```

---

## References

- **Source:** `src/rules/actions.py` - send_slack, SlackTemplateLoader
- **Config:** `config/slack_templates.yaml` - Message templates
- **Settings:** `src/config/settings.py` - Webhook URL loading
- **Tests:** `tests/integration/test_slack_integration.py` - AC 1-5 verification
- **Service:** `src/notifications/slack_service.py` - Webhook client
- **Story:** Story 6.2 - Add Slack Integration
