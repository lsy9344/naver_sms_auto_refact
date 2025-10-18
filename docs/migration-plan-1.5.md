# Migration Plan – Story 1.5 Infrastructure as Code Adoption

This document describes how to migrate infrastructure created during Stories 1.1–1.4 into Terraform state managed by Story 1.5. The goal is zero configuration drift and the ability to reproduce environments across dev, staging, prod, and sandbox.

---

## Scope

Resources provisioned prior to Story 1.5:

| Story | Resource | Current Location | Migration Strategy |
|-------|----------|------------------|--------------------|
| 1.1   | AWS ECR repository & lifecycle policy | `naver-sms-automation` (manual) | Import into Terraform |
| 1.2   | IAM policies / Secrets Manager secrets | Manual CLI / console | Import or recreate with Terraform modules |
| 1.3   | CloudWatch log group, metric filters, alarms | Manual | Recreate via Terraform module for deterministic config |
| 1.4   | CI placeholders, README snippets | Git repo | Superseded by Story 1.5 automation |

---

## Migration Strategy

1. **Freeze Changes**
   - Announce change window
   - Disable manual updates in AWS console
   - Ensure Terraform state bucket & DynamoDB table exist (see `infrastructure/README.md`)

2. **Prepare Environment**
   ```bash
   cd infrastructure/terraform
   terraform init \
     -backend-config="bucket=terraform-state-<account-id>" \
     -backend-config="key=naver-sms-automation/terraform.tfstate" \
     -backend-config="workspace_key_prefix=naver-sms-automation" \
     -backend-config="region=ap-northeast-2" \
     -backend-config="dynamodb_table=terraform-locks"
   terraform workspace select dev || terraform workspace new dev
   ```

3. **Import Existing Resources**

   | Resource | Import Command |
   |----------|----------------|
   | ECR Repository | `terraform import module.ecr.aws_ecr_repository.main naver-sms-automation` |
   | ECR Lifecycle Policy | `terraform import module.ecr.aws_ecr_lifecycle_policy.main naver-sms-automation` |
   | Secrets Manager (if keeping existing secrets) | `terraform import module.secrets_manager.aws_secretsmanager_secret.secrets["naver-credentials"] naver-sms-automation/dev/naver-credentials` (repeat for `sens` & `telegram`) |
   | CloudWatch Log Group (optional) | `terraform import module.cloudwatch.aws_cloudwatch_log_group.lambda /aws/lambda/naver-sms-automation` |
   | CloudWatch Dashboard (optional) | `terraform import module.cloudwatch.aws_cloudwatch_dashboard.main naver-sms-automation-dashboard` |

   > **Recommendation:** prefer recreating CloudWatch resources via Terraform apply to ensure dashboard JSON and alarms match Story 1.5 definitions.

4. **Validate Plan**
   ```bash
   terraform plan -var-file=environments/dev.tfvars
   ```
   - Expect zero destructive changes
   - Resolve diffs by adjusting `environments/dev.tfvars`

5. **Promote to Other Environments**
   - Repeat import / apply steps for `staging` and `prod` workspaces
   - Use environment-specific tfvars with correct ARNs

---

## Rollback Decision Tree

1. **Plan Shows Unintended Deletes**
   - Abort `apply`
   - Restore state from S3 versioning (see `infrastructure/TROUBLESHOOTING.md`)
   - Re-import missing resources if required

2. **Apply Fails Midway**
   - Review error output
   - Re-run apply after fixing issues (permissions, naming conflicts)
   - For sandbox: run `./scripts/deploy_infra.sh -sandbox destroy` to clean up

3. **Production Instability Detected**
   - Stop Terraform activity
   - Manually revert changes using previous AWS console configuration
   - Restore Terraform state file from the last known-good S3 version
   - Document incident in `docs/qa/infra-validation-1.5.md`

---

## Timeline Recommendation

1. **Day 1 (Sandbox)**
   - Import existing resources or apply fresh Terraform stack
   - Verify outputs and document in `docs/qa/infra-validation-1.5.md`

2. **Day 2 (Dev Environment)**
   - Import existing resources using commands above
   - Run `terraform plan` to ensure zero drift
   - Execute CI workflow to capture plan artifact

3. **Day 3 (Staging / Prod)**
   - Repeat import process during low-traffic window
   - Obtain QA sign-off using `docs/qa/infra-security-review-1.5.md`
   - Update runbooks and notify stakeholders

---

## Post-Migration Checklist

- [ ] Secrets created via Terraform module only (no console-created duplicates)
- [ ] `terraform plan` returns zero changes for each workspace
- [ ] CI pipeline green (`terraform-check.yml`)
- [ ] Migration documented in `docs/qa/infra-validation-1.5.md`
- [ ] Operations team briefed on new processes (`infrastructure/README.md`)
- [ ] Manual console access restricted to break-glass only

---

## References

- Story: `docs/stories/1.5.create-infrastructure-as-code.md`
- Validation checklist: `docs/qa/infra-validation-1.5.md`
- Security review log: `docs/qa/infra-security-review-1.5.md`
- Troubleshooting playbook: `infrastructure/TROUBLESHOOTING.md`

