# Infrastructure Operations Guide

This repository provisions all Epic 1 infrastructure for the refactored Naver SMS automation system through Terraform. Use this document as the single source of truth for standing up, operating, and destroying environments.

---

## Overview

- **IaC Tooling:** Terraform `>= 1.5.0`
- **AWS Provider:** `>= 5.0`
- **Supported Environments:** `dev`, `staging`, `prod`, and `sandbox`
- **Modules:** ECR, Secrets Manager, CloudWatch (log group, metric filters, dashboard, alarms, SNS)
- **Remote State:** S3 bucket `terraform-state-{aws_account_id}` with DynamoDB table `terraform-locks`

Directory layout:

```
infrastructure/
├── terraform/
│   ├── backend.tf                 # Remote backend definition
│   ├── main.tf                    # Root module wiring
│   ├── outputs.tf                 # Downstream outputs
│   ├── provider.tf                # Required versions + default tags
│   ├── variables.tf               # Global variables
│   ├── .terraform.lock.hcl        # Provider lock file
│   ├── environments/              # Environment specific tfvars
│   └── modules/                   # ECR / Secrets / CloudWatch modules
├── .tflint.hcl                    # Linting rules
├── README.md                      # (this file)
├── TROUBLESHOOTING.md             # Rollback & incident procedures
└── scripts/
    ├── deploy_infra.sh            # Workspace-aware Terraform wrapper
    └── setup-secrets.sh           # Secrets Manager bootstrap helper
```

---

## Prerequisites

1. **CLI Tooling**
   - Terraform `>= 1.5.0`
   - AWS CLI `>= 2.13.0`
   - TFLint `>= 0.51.0` (with AWS ruleset)
2. **AWS Credentials**
   - IAM role or user with the permissions in `docs/qa/required-iam-policy.json`
   - Access to the account that owns the remote state bucket and DynamoDB lock table
3. **Local Environment File (optional but recommended)**
   - Create `scripts/.env.local` to centralise shared variables:
     ```bash
     # scripts/.env.local (example template)
     export AWS_PROFILE=naver-sms-sre
     export AWS_REGION=ap-northeast-2
     export TF_VAR_lambda_role_arn="arn:aws:iam::123456789012:role/naver-dev-lambda-role"
     export TF_VAR_ci_deployment_role_arn="arn:aws:iam::123456789012:role/naver-dev-ci-role"
     ```
   - Values are sourced automatically by `deploy_infra.sh` and `setup-secrets.sh`.

---

## Remote State Bootstrap

1. **Create S3 Bucket (once per account)**
   ```bash
   aws s3api create-bucket \
     --bucket terraform-state-123456789012 \
     --region ap-northeast-2 \
     --create-bucket-configuration LocationConstraint=ap-northeast-2

   aws s3api put-bucket-versioning \
     --bucket terraform-state-123456789012 \
     --versioning-configuration Status=Enabled

   aws s3api put-bucket-encryption \
     --bucket terraform-state-123456789012 \
     --server-side-encryption-configuration '{
       "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
   ```

2. **Create DynamoDB Table (once per account)**
   ```bash
   aws dynamodb create-table \
     --table-name terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region ap-northeast-2
   ```

3. **Grant Least-Privilege Access**
   - Apply IAM policy from `docs/qa/required-iam-policy.json` to the CI role and trusted operators.

---

## Deploying Infrastructure

### 1. Populate Secrets Safely

Run the helper script to create/update Secrets Manager entries without committing values:

```bash
./scripts/setup-secrets.sh --env dev
```

The script:
- Validates AWS CLI credentials
- Prompts for secret fields (hidden input) or uses environment variables if already exported
- Creates `naver-sms-automation/{env}/` secrets (`naver`, `sens`, `telegram`)
- Optionally updates existing secrets via `PutSecretValue`

### 2. Execute Terraform Commands

All Terraform work happens under `infrastructure/terraform`. Use the wrapper to enforce version checks, backend initialisation, and workspace isolation:

```bash
# Plan
./scripts/deploy_infra.sh -dev plan

# Apply
./scripts/deploy_infra.sh -dev apply

# Validate only (syntax)
./scripts/deploy_infra.sh -dev validate

# Format Terraform files (recursive)
./scripts/deploy_infra.sh -dev fmt
```

Flags: `-dev`, `-staging`, `-prod`, `-sandbox` (destroy is restricted to `-sandbox`).

The script:
- Loads `scripts/.env.local` if present
- Checks Terraform & AWS CLI minimum versions
- Authenticates with AWS (`aws sts get-caller-identity`)
- Initialises S3 backend + DynamoDB locking
- Creates/selects Terraform workspace named after the environment
- Prevents parallel apply via `/tmp/terraform-{env}.lock`

### 3. Manual Terraform Usage (optional)

You can still run Terraform commands manually:

```bash
cd infrastructure/terraform
terraform init \
  -backend-config="bucket=terraform-state-123456789012" \
  -backend-config="key=naver-sms-automation/terraform.tfstate" \
  -backend-config="workspace_key_prefix=naver-sms-automation" \
  -backend-config="region=ap-northeast-2" \
  -backend-config="dynamodb_table=terraform-locks" \
  -backend-config="encrypt=true"

terraform workspace select dev || terraform workspace new dev
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

---

## CI & Quality Gates

- GitHub Actions workflow `.github/workflows/terraform-check.yml` (see repository root) executes on pull requests:
  - `terraform fmt -check`
  - `terraform validate`
  - `tflint`
  - `terraform plan` with uploaded artifact (7-day retention)
- Use `make` or scripts to run the same checks locally before submitting a PR:
  ```bash
  ./scripts/deploy_infra.sh -sandbox fmt
  ./scripts/deploy_infra.sh -sandbox validate
  tflint infrastructure/terraform
  ```

---

## Capturing Outputs

After a sandbox apply, export outputs for downstream stories:

```bash
terraform output -json > /tmp/outputs.json
```

Convert to YAML and paste into `docs/qa/infra-validation-1.5.md` under the `resource_outputs` section. This drives integration for later stories.

---

## Rollback & Incident Response

Refer to `infrastructure/TROUBLESHOOTING.md` for detailed checklists covering:

- Clearing stuck DynamoDB locks
- Restoring Terraform state from S3 object versioning
- Backing out failed deploys or partial applies
- Validating and recreating secrets
- Emergency destroy for sandbox resources

High-level rollback flow:

1. **Stop Changes:** Cancel active Terraform runs, ensure no concurrent applies.
2. **Assess State:** Run `terraform plan` to understand drift. If state is corrupt, restore newest good version from S3.
3. **Reapply / Destroy:** Decide whether to reapply corrected config or destroy problematic resources (sandbox only).
4. **Document:** Update `docs/qa/infra-validation-1.5.md` with findings and follow QA checklist for sign-off.

---

## Frequently Used Commands

```bash
# Format Terraform code
terraform fmt -recursive infrastructure/terraform

# Validate syntax
terraform -chdir=infrastructure/terraform validate

# Lint with TFLint
tflint infrastructure/terraform

# Generate plan artifact manually
terraform -chdir=infrastructure/terraform plan \
  -var-file=environments/sandbox.tfvars \
  -out=tfplan-sandbox.bin
```

---

## Additional References

- Acceptance criteria & story context: `docs/stories/1.5.create-infrastructure-as-code.md`
- Security review log: `docs/qa/infra-security-review-1.5.md`
- IAM requirements: `docs/qa/required-iam-policy.json`
- Sandbox validation report: `docs/qa/infra-validation-1.5.md`
- Migration playbook: `docs/migration-plan-1.5.md`

Keep this README up to date with operational realities—treat it as living documentation.

