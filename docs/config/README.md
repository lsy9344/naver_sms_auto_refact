# Configuration Management

Complete guide to configuring the Naver SMS Automation system.

## Quick Start

### Local Development Setup

1. **Set environment variables:**

```bash
export NAVER_USERNAME="your_naver_username"
export NAVER_PASSWORD="your_naver_password"
export SENS_ACCESS_KEY="your_sens_access_key"
export SENS_SECRET_KEY="your_sens_secret_key"
export SENS_SERVICE_ID="your_sens_service_id"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
# For local development only - use Secrets Manager in production
export SLACK_ENABLED="true"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

2. **Or create `.env.local` file:**

```bash
NAVER_USERNAME=your_naver_username
NAVER_PASSWORD=your_naver_password
SENS_ACCESS_KEY=your_sens_access_key
SENS_SECRET_KEY=your_sens_secret_key
SENS_SERVICE_ID=your_sens_service_id
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
# For local development only - use Secrets Manager in production
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX
```

Then install python-dotenv:

```bash
pip install python-dotenv
```

3. **Load configuration in code:**

```python
from src.config.settings import get_settings

settings = get_settings()  # Cached on first call
print(f"AWS Region: {settings.aws_region}")
print(f"Stores configured: {len(settings.stores)}")
```

## Configuration Sources (Precedence)

Configuration is loaded with the following priority (highest to lowest):

### 1. Environment Variables (Highest Priority)

Set these environment variables to override all other sources:

```bash
# Naver credentials
NAVER_USERNAME=username
NAVER_PASSWORD=password

# SENS credentials
SENS_ACCESS_KEY=access_key
SENS_SECRET_KEY=secret_key
SENS_SERVICE_ID=service_id

# Telegram credentials
TELEGRAM_BOT_TOKEN=token
TELEGRAM_CHAT_ID=chat_id

# Slack configuration (optional - disabled by default)
# For production: Store webhook URL in AWS Secrets Manager
# For local dev: Use config/my_slack_webhook.yaml or set SLACK_WEBHOOK_URL below
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX

# AWS configuration (optional - defaults to ap-northeast-2)
AWS_REGION=ap-northeast-2
DYNAMODB_TABLE_SMS=sms
DYNAMODB_TABLE_SESSION=session
```

### 2. AWS Secrets Manager

For production, store credentials in AWS Secrets Manager with default names:

- `naver-sms-automation/naver-credentials`
- `naver-sms-automation/sens-credentials`
- `naver-sms-automation/telegram-credentials`

**Example creation:**

```bash
# Naver credentials
aws secretsmanager create-secret \
  --name naver-sms-automation/naver-credentials \
  --secret-string '{
    "username": "your_username",
    "password": "your_password"
  }' \
  --region ap-northeast-2

# SENS credentials
aws secretsmanager create-secret \
  --name naver-sms-automation/sens-credentials \
  --secret-string '{
    "access_key": "your_access_key",
    "secret_key": "your_secret_key",
    "service_id": "your_service_id"
  }' \
  --region ap-northeast-2

# Telegram credentials
aws secretsmanager create-secret \
  --name naver-sms-automation/telegram-credentials \
  --secret-string '{
    "bot_token": "your_bot_token",
    "chat_id": "your_chat_id"
  }' \
  --region ap-northeast-2

# Slack credentials
aws secretsmanager create-secret \
  --name naver-sms-automation/slack-credentials \
  --secret-string '{
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }' \
  --region ap-northeast-2
```

### 3. Local Development Fallback Files

**`.env.local` file:**

```bash
# Requires: pip install python-dotenv
NAVER_USERNAME=your_username
NAVER_PASSWORD=your_password
SENS_ACCESS_KEY=your_access_key
SENS_SECRET_KEY=your_secret_key
SENS_SERVICE_ID=your_service_id
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Or `config/local-secrets.json` file:**

```json
{
  "naver": {
    "username": "your_username",
    "password": "your_password"
  },
  "sens": {
    "access_key": "your_access_key",
    "secret_key": "your_secret_key",
    "service_id": "your_service_id"
  },
  "telegram": {
    "bot_token": "your_bot_token",
    "chat_id": "your_chat_id"
  },
  "slack": {
    "webhook_url": "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
  }
}
```

To use local secrets file, set:

```bash
export USE_LOCAL_SECRETS_FILE=true
export LOCAL_SECRETS_FILE_PATH=config/local-secrets.json
```

### 4. YAML Configuration Files

**`config/stores.yaml`:**

```yaml
default:
  fromNumber: "01055814318"

stores:
  "1051707":
    name: "다비스튜디오 화성점"
    fromNumber: "01055814318"
    templates:
      guide: "1051707"
  
  "867589":
    name: "다비스튜디오 안산 초지점"
    fromNumber: "01022392673"
    templates:
      guide: "867589"
```

**`config/sms_templates.yaml`:**

```yaml
templates:
  confirmation:
    subject: "예약 확정 안내"
    type: "LMS"
    content: |
      다비스튜디오를 찾아주신 고객님, 안녕하세요
      예약 확정되어 이용 안내 드립니다.

  guide_1051707:
    subject: "이용 상세 안내"
    type: "LMS"
    content: |
      다비스튜디오를 찾아주신 고객님, 안녕하세요
      이용 상세 안내 드립니다.
```

**`config/my_slack_webhook.yaml` (Slack configuration - local development):**

```yaml
# Get webhook URL from https://api.slack.com/messaging/webhooks
slack webhook url: "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

**`config/slack_templates.yaml` (Slack message templates):**

```yaml
templates:
  expert_correction_digest:
    blocks:
      - type: "section"
        text:
          type: "mrkdwn"
          text: |
            🔔 *Expert Correction Digest*
            {{ message }}
            
            Date: {{ today_date }}
```

### 5. Default Values

If not set elsewhere, defaults are used:

```python
# AWS Configuration
aws_region = "ap-northeast-2"
dynamodb_table_sms = "sms"
dynamodb_table_session = "session"

# Business Configuration
option_keywords = ["네이버", "인스타", "원본"]
rules = []
```

## Configuration Fields

### AWS Configuration

| Field | Type | Description | Default | Example |
|-------|------|-------------|---------|---------|
| `aws_region` | str | AWS region | `ap-northeast-2` | `ap-northeast-2` |
| `dynamodb_table_sms` | str | DynamoDB SMS table | `sms` | `sms` |
| `dynamodb_table_session` | str | DynamoDB session table | `session` | `session` |

### Naver Credentials

| Field | Type | Description | Source | Required |
|-------|------|-------------|--------|----------|
| `naver_username` | str | Naver account username | Env/Secrets | Yes |
| `naver_password` | str | Naver account password | Env/Secrets | Yes |

### SENS Credentials

| Field | Type | Description | Source | Required |
|-------|------|-------------|--------|----------|
| `sens_access_key` | str | SENS API access key | Env/Secrets | Yes |
| `sens_secret_key` | str | SENS API secret key | Env/Secrets | Yes |
| `sens_service_id` | str | SENS service ID | Env/Secrets | Yes |

### Telegram Credentials

| Field | Type | Description | Source | Required |
|-------|------|-------------|--------|----------|
| `telegram_bot_token` | str | Telegram bot token | Env/Secrets | Yes |
| `telegram_chat_id` | str | Telegram chat ID | Env/Secrets | Yes |

### Slack Configuration (Story 6.2)

| Field | Type | Description | Source | Required |
|-------|------|-------------|--------|----------|
| `slack_enabled` | bool | Enable/disable Slack notifications | Env (SLACK_ENABLED) | No |
| `slack_webhook_url` | str | Slack incoming webhook URL | **Secrets Manager** (recommended) / File / Env | No* |

*Required only when `slack_enabled=true`. **Recommended to store in AWS Secrets Manager for production environments.**

### Slack Message Templates

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `templates` | Dict[str, Template] | Slack message templates | YAML (config/slack_templates.yaml) |

**Template structure:**

```python
# Templates support Jinja2 templating
# Example variables: {{ message }}, {{ today_date }}, {% for item in items %}
template = {
    "blocks": [  # Slack Block Kit format
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Message content with {{ variable }}"
            }
        }
    ]
}
```

### Business Configuration

| Field | Type | Description | Source |
|-------|------|-------------|--------|
| `stores` | Dict[str, Store] | Store configurations | YAML |
| `option_keywords` | List[str] | Keywords for option detection | YAML/Default |
| `rules` | List[Dict] | Rule configurations | YAML |

**Store structure:**

```python
@dataclass
class Store:
    id: str                    # Store ID (e.g., "1051707")
    name: str                  # Store name (Korean)
    fromNumber: str            # Phone number for SMS sending
    templates: Dict[str, str]  # Template mappings (e.g., {"guide": "1051707"})
```

## How to Add Configuration

### Adding a New Configuration Field

1. **Define in Settings dataclass** (`src/config/settings.py`):

```python
@dataclass
class Settings:
    # ... existing fields ...
    
    # New field
    my_new_setting: str = "default_value"
```

2. **Load from configuration source:**

```python
@staticmethod
def load() -> "Settings":
    settings = Settings()
    # ... existing loading code ...
    
    # Load new field from environment or YAML
    if os.getenv("MY_NEW_SETTING"):
        settings.my_new_setting = os.getenv("MY_NEW_SETTING")
    
    return settings
```

3. **Document in this README**

4. **Add tests** in `tests/unit/test_config.py`

### Adding a New Secret to Secrets Manager

1. **Create in Secrets Manager:**

```bash
aws secretsmanager create-secret \
  --name naver-sms-automation/my-new-secret \
  --secret-string '{"key": "value"}' \
  --region ap-northeast-2
```

2. **Update Settings class to load it:**

```python
@staticmethod
def _load_credentials_from_env_or_secrets() -> Dict[str, str]:
    credentials = {}
    
    # Load new secret
    try:
        my_secret = Settings._get_secret_value("naver-sms-automation/my-new-secret")
        credentials["my_new_secret"] = my_secret
    except ConfigurationError:
        pass
    
    return credentials
```

3. **Add to Settings model**

4. **Update tests**

### Adding a New YAML Configuration

1. **Create YAML file** in `config/` directory:

```bash
# config/my_config.yaml
my_settings:
  key1: value1
  key2: value2
```

2. **Add loader method** to Settings:

```python
@staticmethod
def _load_my_config() -> Dict[str, Any]:
    """Load my_config from YAML."""
    return Settings._load_yaml_file("my_config.yaml")
```

3. **Update Settings.load()**:

```python
@staticmethod
def load() -> "Settings":
    settings = Settings()
    # ... existing code ...
    
    # Load new config
    my_config_data = Settings._load_my_config()
    # Process and store...
    
    return settings
```

4. **Document in README**

5. **Add tests for validation**

## Slack Webhook Configuration (Story 6.2)

### Getting Your Slack Webhook URL

**Important:** The `SLACK_WEBHOOK_URL` must be a real Slack Incoming Webhook URL, not a placeholder.

**Steps to get your webhook URL:**

1. Go to https://api.slack.com/messaging/webhooks
2. Click "Create New App" or select existing app
3. Enable "Incoming Webhooks"
4. Click "Add New Webhook to Workspace"
5. Select target channel and authorize
6. Copy the Webhook URL (looks like: `https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX`)

**Example webhook URLs:**
```
https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX
https://hooks.slack.com/services/TXXXXXXXXXX/BXXXXXXXXXX/YYYYYYYYYYYYYYYYYYYYYY
```

**Note:** Always starts with `https://hooks.slack.com/services/` followed by IDs and secret token.

### Overview

Slack integration allows the rule engine to send notifications through Slack webhooks. Notifications are triggered when rule conditions match (e.g., "expert correction" keyword detected).

### Configuration Sources (Priority Order)

Slack webhook URL is loaded with the following priority:

1. **AWS Secrets Manager** `naver-sms-automation/slack-credentials` (production - RECOMMENDED)
2. **`config/my_slack_webhook.yaml`** (local development)
3. **`SLACK_WEBHOOK_URL` environment variable** (emergency override only)

### Enable/Disable Slack Notifications

Slack notifications are **disabled by default**. Enable them explicitly:

#### Option 1: Environment Variable (NOT RECOMMENDED for production)

⚠️ **WARNING:** Only use environment variables for **LOCAL DEVELOPMENT**. For production, use Secrets Manager (Option 3).

```bash
export SLACK_ENABLED=true
# Replace with your actual webhook URL from https://api.slack.com/messaging/webhooks
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

#### Option 2: Local Configuration File (Local Development)

Create `config/my_slack_webhook.yaml`:

```yaml
# Get webhook URL from https://api.slack.com/messaging/webhooks
slack webhook url: "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
```

Then enable:

```bash
export SLACK_ENABLED=true
```

#### Option 3: AWS Secrets Manager (RECOMMENDED for Production) ✅

**This is the secure way to store Slack webhook URLs in production.**

Create secret in Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name naver-sms-automation/slack-credentials \
  --secret-string '{
    "webhook_url": "https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX"
  }' \
  --region ap-northeast-2
```

**Note:** Get your webhook URL from https://api.slack.com/messaging/webhooks

Then enable in Lambda environment:

```bash
export SLACK_ENABLED=true
```

**Advantages:**
- ✅ Webhook URL is encrypted at rest in AWS
- ✅ Access is logged via CloudTrail
- ✅ Easy to rotate credentials without redeploying
- ✅ Lambda role permissions control access
- ✅ No secrets in code or environment variables

### Slack Message Templates

Message templates are defined in `config/slack_templates.yaml` using **Slack Block Kit** format with **Jinja2 variable substitution**:

```yaml
templates:
  expert_correction_digest:
    blocks:
      - type: "section"
        text:
          type: "mrkdwn"
          text: |
            🔔 *Expert Correction Digest*
            
            {{ message }}
            
            Total items: {{ item_count }}
            Date: {{ today_date }}
  
  validation_alert:
    blocks:
      - type: "section"
        text:
          type: "mrkdwn"
          text: |
            ⚠️ *Validation Alert*
            
            Failures: {{ failure_count }}/{{ total_tests }}
            Pass rate: {{ pass_rate }}%
```

### How Templates Are Used

1. **Define in rule configuration:**

```yaml
rules:
  - name: "expert_correction_notification"
    conditions:
      - type: "keyword_detected"
        keywords: ["expert correction"]
    actions:
      - type: "send_slack"
        template_name: "expert_correction_digest"
        variables:
          message: "Expert correction detected in booking"
          item_count: 5
```

2. **Template loader processes Jinja2 variables and renders to Slack**

3. **Webhook client sends rendered message**

### Handling Slack Failures

Slack delivery failures are **non-critical** - they don't block rule execution:

- **Network errors**: Automatically retried up to 3 times with linear backoff
- **Rate limiting** (HTTP 429): Respected with `Retry-After` header
- **Invalid webhook**: Logged as warning; rule continues
- **Webhook disabled**: Gracefully skipped if `SLACK_ENABLED=false`

All failures are logged with structured context for debugging.

### Testing Slack Configuration

```bash
# Check webhook status programmatically
python -c "
from src.notifications.slack_service import SlackWebhookClient
client = SlackWebhookClient()
print(client.get_webhook_status())
"

# Send test notification
python -c "
from src.notifications.slack_service import SlackWebhookClient
client = SlackWebhookClient()
client.send_slack_webhook_test(webhook_url_masked='https://hooks.slack.com/...', status='success')
"
```

## Troubleshooting

### "No configuration source found"

This error means no credentials were found from any source. Fix:

1. **Check environment variables:**

```bash
env | grep -E 'NAVER_|SENS_|TELEGRAM_'
```

2. **Check local files exist:**

```bash
# For .env.local
ls -la .env.local

# For local-secrets.json
ls -la config/local-secrets.json
```

3. **Check Secrets Manager access:**

```bash
aws secretsmanager get-secret-value \
  --secret-id naver-sms-automation/naver-credentials \
  --region ap-northeast-2
```

4. **Verify AWS credentials:**

```bash
aws sts get-caller-identity
```

### "Config file not found: config/stores.yaml"

This error means the stores.yaml file is missing. Fix:

1. **Create stores.yaml:**

```bash
mkdir -p config
touch config/stores.yaml
```

2. **Add valid YAML content:**

```yaml
stores:
  "1051707":
    name: "Test Store"
    fromNumber: "01055814318"
    templates:
      guide: "1051707"
```

### "Invalid YAML in stores.yaml"

YAML file has syntax errors. Fix:

```bash
# Validate YAML syntax
python -m yaml config/stores.yaml
```

Common issues:
- Mixing tabs and spaces (use spaces only)
- Incorrect indentation
- Missing colons after keys
- Unclosed quotes

### Credentials Not Being Loaded

1. **Check precedence** - environment variables override everything:

```bash
# These take priority
export NAVER_USERNAME=test
```

2. **Check Secrets Manager permissions** - Lambda role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:*:secret:naver-sms-automation/*"
    }
  ]
}
```

3. **Check KMS permissions** - If secrets are encrypted:

```json
{
  "Effect": "Allow",
  "Action": [
    "kms:Decrypt"
  ],
  "Resource": "arn:aws:kms:ap-northeast-2:*:key/*"
}
```

### "Sensitive fields not redacted in logs"

Ensure redaction filter is initialized:

```python
from src.config.settings import setup_logging_redaction
import logging

# Call early in application startup
setup_logging_redaction()

# Now log messages will have credentials redacted
logger = logging.getLogger(__name__)
logger.info(f"Loaded settings: {settings}")  # Passwords will be ****
```

### "Slack webhook URL not configured"

Slack notifications are disabled when webhook URL is not found. Fix:

1. **Check if Slack is enabled:**

```bash
echo $SLACK_ENABLED
```

2. **Check environment variable:**

```bash
echo $SLACK_WEBHOOK_URL
```

3. **Check local config file:**

```bash
ls -la config/my_slack_webhook.yaml
cat config/my_slack_webhook.yaml
```

4. **Check Secrets Manager:**

```bash
aws secretsmanager get-secret-value \
  --secret-id naver-sms-automation/slack-credentials \
  --region ap-northeast-2
```

5. **Verify webhook URL format:**

```bash
# Valid Slack webhook URL should start with:
https://hooks.slack.com/services/
```

## Security Best Practices

### 1. Never Commit Credentials

Add to `.gitignore`:

```bash
# .gitignore
.env.local
config/local-secrets.json
config/*-secrets.json
```

### 2. Use IAM Roles in Production

Instead of hardcoding credentials:

```python
# Lambda automatically uses its execution role
# No credentials needed in code
settings = get_settings()
```

### 3. Rotate Secrets Regularly

Update secrets in Secrets Manager periodically:

```bash
aws secretsmanager update-secret \
  --secret-id naver-sms-automation/naver-credentials \
  --secret-string '{"username": "new_user", "password": "new_pass"}'
```

### 4. Audit Configuration Access

Enable CloudTrail to monitor Secrets Manager access:

```bash
# Enable CloudTrail logging for Secrets Manager
aws cloudtrail start-logging --trail-name my-trail
```

### 5. Use Least Privilege

Grant minimal required permissions to Lambda role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT:secret:naver-sms-automation/*",
      "Condition": {
        "StringEquals": {
          "secretsmanager:resource/AllowRotationLambdaArn": "arn:aws:lambda:ap-northeast-2:ACCOUNT:function:my-function"
        }
      }
    }
  ]
}
```

## Configuration Examples

### Example 1: Local Development

**`.env.local` file:**

```bash
NAVER_USERNAME=dltnduf4318
NAVER_PASSWORD=MyPassword123
SENS_ACCESS_KEY=my_access_key
SENS_SECRET_KEY=my_secret_key
SENS_SERVICE_ID=ncp:sms:kr:service123
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=987654321
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX
```

**`config/stores.yaml`:**

```yaml
default:
  fromNumber: "01055814318"

stores:
  "1051707":
    name: "다비스튜디오 화성점"
    fromNumber: "01055814318"
    templates:
      guide: "1051707"
  
  "951291":
    name: "다비스튜디오 안산 당곡점"
    fromNumber: "01055814318"
    templates:
      guide: "951291"
```

### Example 2: Production with Secrets Manager

All credentials in AWS Secrets Manager:

```bash
# Create all secrets
aws secretsmanager create-secret --name naver-sms-automation/naver-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/sens-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/telegram-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/slack-credentials \
  --secret-string '{"webhook_url": "https://hooks.slack.com/services/..."}'

# Lambda environment: Enable Slack
export SLACK_ENABLED=true

# Lambda role has permission to read all secrets
# No hardcoded values or .env.local
# Configuration is secure and audited
```

### Example 3: Mixed Configuration

```bash
# Environment: Critical credentials from env vars
export NAVER_USERNAME=production_user
export NAVER_PASSWORD=secure_password
export SLACK_ENABLED=true
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T1234567890/B1234567890/XXXXXXXXXXXXXXXXXXXX

# Secrets Manager: Less-critical credentials
aws secretsmanager create-secret --name naver-sms-automation/sens-credentials ...
aws secretsmanager create-secret --name naver-sms-automation/telegram-credentials ...

# YAML: Business configuration
# config/stores.yaml contains all stores
# config/slack_templates.yaml contains Slack message templates
```

## API Reference

### Loading Configuration

```python
from src.config.settings import get_settings, Settings

# Get singleton instance (cached)
settings = get_settings()

# Or load fresh instance
settings = Settings.load()

# Reload (mainly for tests)
from src.config.settings import reload_settings
new_settings = reload_settings()
```

### Accessing Configuration

```python
settings = get_settings()

# AWS Configuration
region = settings.aws_region
sms_table = settings.dynamodb_table_sms

# Credentials
username = settings.naver_username
api_key = settings.sens_access_key

# Business Config
for store_id, store in settings.stores.items():
    print(f"Store {store_id}: {store.name}")

# Keywords
for keyword in settings.option_keywords:
    print(keyword)
```

### Logging with Redaction

```python
from src.config.settings import setup_logging_redaction
import logging

setup_logging_redaction()
logger = logging.getLogger(__name__)

# Log shows settings with credentials redacted
logger.info(f"Configuration loaded: {settings}")
# Output: Configuration loaded: Settings(naver_password=****, ...)
```

## References

- [Settings Dataclass Documentation](../../src/config/settings.py)
- [Slack Service Documentation](../../src/notifications/slack_service.py)
- [Slack Integration Tests](../../tests/integration/test_slack_integration.py)
- [Slack Integration Guide](../testing/slack-integration.md)
- [Story 6.2: Add Slack Integration](../stories/6.2.add-slack-integration.md)
- [Dependency Injection Guide](./INTEGRATION.md)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
- [Slack Block Kit](https://api.slack.com/block-kit)
