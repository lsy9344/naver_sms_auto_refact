# Infrastructure Tests

## Overview

These tests verify the actual AWS infrastructure setup for the naver-sms-automation project.

## Requirements

- Valid AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- Access to the following AWS resources:
  - ECR repository: `naver-sms-automation` in `ap-northeast-2`
  - IAM policy: `NaverSmsAutomationECRAccessPolicy`
  - IAM role: `naverplace_send_inform-role-vb1bx6ro`

## Running Tests

### With AWS Credentials

When AWS credentials are available, all tests will execute:

```bash
python -m pytest tests/infrastructure/test_ecr.py -v
```

Expected output: `9 passed`

### Without AWS Credentials (CI Environment)

When AWS credentials are not available, tests will be automatically skipped:

```bash
# In CI environment without AWS credentials
python -m pytest tests/infrastructure/test_ecr.py -v
```

Expected output: `9 skipped` with reason "AWS credentials not available - skipping infrastructure tests"

## Test Coverage

The test suite validates all acceptance criteria:

1. **ECR Repository Creation** (AC1, AC2)
   - Repository exists with correct name
   - Repository is in ap-northeast-2 region
   - Repository URI format is correct

2. **Image Scanning** (AC3)
   - Scan on push is enabled

3. **Lifecycle Policy** (AC4)
   - Policy keeps only latest 5 images
   - Older images expire automatically

4. **IAM Permissions** (AC5)
   - ECR access policy exists
   - Policy has correct permissions (pull operations)
   - Policy is attached to Lambda execution role

5. **Repository Access** (AC6, AC7)
   - Test image exists in repository

## CI/CD Integration

These tests are designed to:
- **Skip gracefully** in CI environments without AWS credentials
- **Validate** infrastructure when credentials are available (e.g., deployment pipeline)
- **Provide documentation** of infrastructure requirements through test code

For CI environments that need to verify infrastructure, configure AWS credentials via:
- GitHub Actions: `aws-actions/configure-aws-credentials`
- GitLab CI: AWS environment variables
- Jenkins: AWS credentials plugin
