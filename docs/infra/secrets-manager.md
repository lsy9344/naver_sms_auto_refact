# Secrets Manager Configuration

## Overview

The Naver SMS automation stack stores all sensitive credentials inside AWS Secrets Manager under the shared namespace `naver-sms-automation/`. Secrets are provisioned via Terraform (`infrastructure/secrets-manager.tf`) to guarantee repeatable deployments and least-privilege access controls.

| Secret Name | Fully Qualified ID | Description | JSON Keys |
|-------------|-------------------|-------------|-----------|
| `naver-credentials` | `naver-sms-automation/naver-credentials` | Naver portal login used by the Selenium automation | `username`, `password` |
| `sens-credentials` | `naver-sms-automation/sens-credentials` | Naver Cloud SENS API credentials for SMS delivery | `access_key`, `secret_key`, `service_id` |
| `telegram-credentials` | `naver-sms-automation/telegram-credentials` | Telegram bot credentials for incident alerts | `bot_token`, `chat_id` |

All secrets are created with placeholder values so they can be safely committed. Populate the real values using the CI deployment role after Terraform applies.

## IAM Access Model

Secrets Manager policies restrict read and write operations to two principals:

1. **Lambda execution role** – `arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role`
   - Read-only access (`GetSecretValue`, `DescribeSecret`)
2. **CI deployment role** – `arn:aws:iam::654654307503:role/naver-sms-automation-ci-role`
   - Read/write access (read permissions plus `PutSecretValue`, `UpdateSecret`, tagging)

Everyone else is explicitly denied through a `Deny` statement that leverages `NotPrincipal`. Terraform generates identical resource policies for each secret so the enforcement is consistent.

### Creating / Updating IAM Roles

If the roles do not exist, provision them before applying the secrets module:

```bash
# Example IAM role creation (Terraform snippet)
resource "aws_iam_role" "lambda_execution" {
  name = "naver-sms-automation-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

resource "aws_iam_role_policy_attachment" "lambda_secrets_access" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role" "ci_pipeline" {
  name = "naver-sms-automation-ci-role"
  assume_role_policy = data.aws_iam_policy_document.ci_trust.json
}
```

Document any role name deviations in Terraform variables (`lambda_role_arn`, `ci_deployment_role_arn`) to keep policies accurate.

## Deployment Workflow

1. **Configure variables** – Update `terraform.tfvars` (or apply flags) with live credentials and IAM role ARNs.
2. **Apply infrastructure** – Run `terraform init && terraform apply` from the `infrastructure/` directory.
3. **Set real secret values** – Assume the CI deployment role and execute `aws secretsmanager put-secret-value` for each secret.
4. **Run validation** – Use the automation script described below and record the output in `VALIDATION.md`.

## Validation Script

The `scripts/validate_secrets.py` tool validates the presence, schema, and policy configuration of each secret. It can optionally assume the Lambda role to prove runtime access.

```bash
# Validate with default AWS credentials
python scripts/validate_secrets.py \
  --expected-principals arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role \
  arn:aws:iam::654654307503:role/naver-sms-automation-ci-role

# Validate using the Lambda execution role
python scripts/validate_secrets.py \
  --assume-role-arn arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role \
  --expected-principals arn:aws:iam::654654307503:role/naver-sms-automation-lambda-role \
  arn:aws:iam::654654307503:role/naver-sms-automation-ci-role
```

Successful output shows `PASS` for each secret and confirms that required keys and resource policies are present.

## Manual Rotation SOP

1. **Initiate rotation**  
   - Assume the CI deployment role.  
   - Prepare new credentials in a secure location (password manager or encrypted file).

2. **Write new secret values**  
   ```bash
   aws secretsmanager put-secret-value \
     --secret-id naver-sms-automation/naver-credentials \
     --secret-string '{"username":"<new>","password":"<new>"}'
   ```

3. **Smoke test**  
   - Re-run `scripts/validate_secrets.py --assume-role-arn <lambda-role-arn>` to ensure Lambda can read the latest version.
   - Trigger the Lambda in a staging environment to verify authentication.

4. **Audit & logging**  
   - CloudTrail automatically records the `PutSecretValue` event.  
   - Log the rotation date and operator in `VALIDATION.md` (Rotation History section).

5. **Rollback (if needed)**  
   - Use `aws secretsmanager list-secret-version-ids` to locate the previous version.  
   - Restore with `aws secretsmanager update-secret-version-stage --remove-from-version-id AWSCURRENT --move-to-version-id <previous-version-id>`.

## Security Notes

- CloudTrail auditing is enabled account-wide; no additional configuration is required, but teams should create saved CloudTrail queries for secret access events (`eventSource=secretsmanager.amazonaws.com`).  
- Never embed production credentials in source control—use Terraform defaults only for scaffolding.  
- Grant temporary CI access tokens instead of static IAM user credentials whenever possible.
