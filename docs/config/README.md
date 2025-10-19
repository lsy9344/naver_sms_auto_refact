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
# Secrets Manager has all credentials
# Lambda role has permission to read them
# No .env.local or hardcoded values
# Configuration is secure and audited
```

### Example 3: Mixed Configuration

```bash
# Environment: Critical credentials from env vars
export NAVER_USERNAME=production_user
export NAVER_PASSWORD=secure_password

# Secrets Manager: Less-critical credentials
aws secretsmanager create-secret --name naver-sms-automation/sens-credentials ...

# YAML: Business configuration
# config/stores.yaml contains all stores
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
- [Dependency Injection Guide](./INTEGRATION.md)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Pydantic Documentation](https://pydantic-ai.dev/) (if using pydantic models)
