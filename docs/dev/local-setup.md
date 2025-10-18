# Local Development Setup Guide

This guide explains how to set up the Naver SMS Automation refactored codebase for local development without storing credentials in source files.

## Overview

The application stores all sensitive credentials in AWS Secrets Manager:
- **Naver authentication** (username/password)
- **SENS SMS API keys** (access key, secret key, service ID)
- **Telegram bot credentials** (bot token, chat ID)

Local development fetches credentials securely at runtime using AWS CLI profiles and boto3.

## Prerequisites

- Python 3.13+
- AWS CLI v2 or later
- AWS account with access to Secrets Manager
- Appropriate IAM permissions (see [Bootstrap Script](#bootstrap-script))

## Step 1: Configure AWS CLI Profile

Set up a local AWS CLI profile with your credentials:

```bash
aws configure --profile naver-sms-dev
# Follow prompts:
# AWS Access Key ID: <your-access-key>
# AWS Secret Access Key: <your-secret-key>
# Default region: ap-northeast-2
# Default output format: json
```

**IMPORTANT:** Never store the secret access key in source code. Use AWS CLI's secure credential storage.

### Using IAM User Credentials

For local development, use an IAM user with minimal permissions (principle of least privilege):

1. Create an IAM user in AWS Console:
   - Name: `naver-sms-dev` (or similar)
   - Access type: Programmatic access only

2. Attach policy with Secrets Manager permissions:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Effect": "Allow",
               "Action": [
                   "secretsmanager:GetSecretValue",
                   "secretsmanager:DescribeSecret"
               ],
               "Resource": [
                   "arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:naver-sms-automation/*"
               ]
           },
           {
               "Effect": "Allow",
               "Action": [
                   "kms:Decrypt"
               ],
               "Resource": [
                   "arn:aws:kms:ap-northeast-2:ACCOUNT_ID:key/KEY_ID"
               ],
               "Condition": {
                   "StringEquals": {
                       "kms:ViaService": "secretsmanager.ap-northeast-2.amazonaws.com"
                   }
               }
           }
       ]
   }
   ```

3. Download and securely store the access key and secret key
4. Configure local profile as shown above

## Step 2: Bootstrap Environment

Run the bootstrap script to validate AWS setup and Secrets Manager access:

```bash
source scripts/bootstrap_env.sh
```

This script:
- ✓ Verifies AWS CLI is installed
- ✓ Checks AWS credentials are configured
- ✓ Validates all required secrets exist in Secrets Manager
- ✓ Validates secret schemas (required fields present)
- ✓ Sets required environment variables

## Step 3: Set AWS Profile

Tell the application which AWS profile to use:

```bash
# Option 1: Set for current shell session
export AWS_PROFILE=naver-sms-dev

# Option 2: Add to .env file (local, not checked in)
echo "AWS_PROFILE=naver-sms-dev" > .env.local

# Option 3: Set in IDE/editor configuration
# PyCharm: Run → Edit Configurations → Environment variables
# VS Code: .vscode/settings.json or launch.json
```

## Step 4: Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
pip install -e .  # Install package in development mode
```

## Step 5: Verify Setup

Test that the application can fetch credentials:

```bash
# Run unit tests for configuration loader
python -m pytest tests/unit/test_config.py -v

# Run integration tests with mock DynamoDB
python -m pytest tests/integration/test_naver_auth_live.py -v

# Test credential retrieval directly
python -c "from src.config.settings import get_naver_credentials; creds = get_naver_credentials(); print('✓ Credentials loaded successfully')"
```

## Fetching Temporary Credentials via AWS CLI

If you need to manually verify credentials exist (debugging):

```bash
# List available secrets
aws secretsmanager list-secrets --filters "Key=name,Values=naver-sms-automation" --region ap-northeast-2 --profile naver-sms-dev

# Describe a specific secret (does NOT return secret value)
aws secretsmanager describe-secret \
    --secret-id naver-sms-automation/naver-credentials \
    --region ap-northeast-2 \
    --profile naver-sms-dev

# Retrieve secret value (for debugging only - never log this!)
# WARNING: This exposes credentials in shell history!
aws secretsmanager get-secret-value \
    --secret-id naver-sms-automation/naver-credentials \
    --region ap-northeast-2 \
    --profile naver-sms-dev \
    --query 'SecretString' \
    --output text | jq .
```

## Environment Variables

The application respects the following environment variables:

### For AWS Secrets Manager (Recommended)

```bash
# Use specific AWS region (defaults to ap-northeast-2)
export AWS_REGION=ap-northeast-2

# Use specific AWS profile
export AWS_PROFILE=naver-sms-dev
```

### For Local File-Based Development (Testing Only)

To use a local secrets file for testing without AWS access:

```bash
# Enable local secrets file mode
export USE_LOCAL_SECRETS_FILE=true

# Path to local secrets JSON file (defaults to .local/secrets.json)
export LOCAL_SECRETS_FILE_PATH=.local/secrets.json
```

Local secrets file format:

```json
{
    "naver": {
        "username": "test_user",
        "password": "test_pass123"
    },
    "sens": {
        "access_key": "test_access_key",
        "secret_key": "test_secret_key",
        "service_id": "test_service_id"
    },
    "telegram": {
        "bot_token": "test_bot_token",
        "chat_id": "test_chat_id"
    }
}
```

**IMPORTANT:** Never commit `.local/secrets.json` to version control. Add to `.gitignore`:

```bash
echo ".local/" >> .gitignore
```

## Application Configuration

The application loads credentials from:

1. **AWS Secrets Manager** (production & recommended)
   - Credentials are fetched on Lambda cold start
   - Cached in memory for duration of execution
   - Automatically redacted from CloudWatch Logs

2. **Local secrets file** (development/testing only)
   - Only if `USE_LOCAL_SECRETS_FILE=true`
   - Specified by `LOCAL_SECRETS_FILE_PATH`
   - For testing without AWS credentials

## Security Best Practices

### DO:
- ✓ Use AWS profiles for local development
- ✓ Use minimal IAM permissions (principle of least privilege)
- ✓ Rotate IAM user credentials regularly
- ✓ Use different profiles for dev/test/prod
- ✓ Review bootstrap script output for security warnings
- ✓ Enable CloudTrail logging for Secrets Manager access
- ✓ Use MFA for IAM user accounts in production

### DON'T:
- ✗ Never hardcode credentials in source files
- ✗ Never commit `.env` files with credentials to git
- ✗ Never echo/print secret values to logs or console
- ✗ Never use root AWS account credentials for development
- ✗ Never disable logging or CloudTrail
- ✗ Never share IAM user credentials with other developers

## Troubleshooting

### "Secret not found in Secrets Manager"

```bash
# Verify secret exists and you have access
aws secretsmanager list-secrets --region ap-northeast-2 --profile naver-sms-dev

# Check IAM permissions
aws iam get-user-policy --user-name naver-sms-dev --policy-name <policy-name> --profile naver-sms-dev
```

### "Access denied" error

```bash
# Verify IAM policy is attached
aws iam list-user-policies --user-name naver-sms-dev

# Test permissions with policy simulator
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::ACCOUNT_ID:user/naver-sms-dev \
    --action-names secretsmanager:GetSecretValue \
    --resource-arns arn:aws:secretsmanager:ap-northeast-2:ACCOUNT_ID:secret:naver-sms-automation/* \
    --profile naver-sms-dev
```

### "KMS Decrypt failed"

If using a custom KMS key for Secrets Manager encryption:

```bash
# Grant KMS permissions to IAM user
aws kms create-grant \
    --key-id KEY_ID \
    --grantee-principal arn:aws:iam::ACCOUNT_ID:user/naver-sms-dev \
    --operations Decrypt \
    --region ap-northeast-2 \
    --profile admin-profile
```

### Credentials cached too long in memory

The application caches credentials for the lifetime of the Lambda execution (typically seconds to minutes). For long-running processes, credentials refresh every 60 minutes automatically. To refresh manually:

```python
# Force reload credentials
from src.config.settings import Settings
creds = Settings.load_naver_credentials()  # Fetches fresh copy
```

## Integration with IDE

### PyCharm

1. Settings → Project → Python Interpreter
2. Click gear icon → Edit → Environment Variables
3. Add:
   ```
   AWS_PROFILE=naver-sms-dev
   AWS_REGION=ap-northeast-2
   ```

### VS Code

Create `.vscode/settings.json`:

```json
{
    "python.envFile": "${workspaceFolder}/.env.local",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": [
        "tests"
    ]
}
```

Create `.env.local` (not checked in):

```
AWS_PROFILE=naver-sms-dev
AWS_REGION=ap-northeast-2
```

## Related Documentation

- [Secrets Manager Setup](../../docs/infra/secrets-manager.md)
- [Architecture - Configuration](../../docs/architecture.md)
- [Story 1.2 - Setup Secrets Manager](../../docs/stories/1.2.setup-secrets-manager.md)
- [Story 1.3 - Migrate Credentials](../../docs/stories/1.3.migrate-credentials-to-secrets-manager.md)
