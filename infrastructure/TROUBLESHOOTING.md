# Infrastructure Troubleshooting & Recovery

Use this runbook to recover from failed Terraform operations, state corruption, or AWS resource issues. Each section lists symptoms, root causes, and step-by-step remediation actions.

---

## 1. Terraform Backend Initialisation Fails

**Symptoms**
- `Error acquiring the state lock` or `NoSuchBucket: The specified bucket does not exist`
- `AccessDenied` while running `terraform init`

**Resolution**
1. Confirm the S3 bucket exists: `aws s3 ls terraform-state-<account-id>`
2. Verify IAM permissions include the statements in `docs/qa/required-iam-policy.json`
3. If bucket exists but permissions fail, re-run `aws sts get-caller-identity` to confirm the active principal
4. Ensure DynamoDB table `terraform-locks` exists in the same region
5. Re-run `terraform init` via `./scripts/deploy_infra.sh -<env> plan`

---

## 2. Stuck Terraform Lock

**Symptoms**
- `Error acquiring the state lock` persists even though no apply is running
- Lock entry remains inside DynamoDB table

**Resolution**
1. Inspect lock: `aws dynamodb get-item --table-name terraform-locks --key '{"LockID":{"S":"naver-sms-automation"} }'`
2. If the lock is stale, delete it:
   ```bash
   aws dynamodb delete-item \
     --table-name terraform-locks \
     --key '{"LockID":{"S":"naver-sms-automation"}}'
   ```
3. Retry the Terraform command
4. Document the incident in `docs/qa/infra-validation-1.5.md`

---

## 3. State Corruption or Rollback

**Symptoms**
- Terraform plan shows unexpected large drift
- State file accidently modified or deleted

**Resolution**
1. List previous versions:
   ```bash
   aws s3api list-object-versions \
     --bucket terraform-state-<account-id> \
     --prefix env:<workspace>/naver-sms-automation/terraform.tfstate
   ```
2. Restore the latest good version:
   ```bash
   aws s3api copy-object \
     --copy-source terraform-state-<account-id>/<version-id> \
     --bucket terraform-state-<account-id> \
     --key env:<workspace>/naver-sms-automation/terraform.tfstate
   ```
3. Run `terraform refresh` followed by `terraform plan`
4. Capture details and remediation in the validation report

---

## 4. Apply Failure Midway

**Symptoms**
- `terraform apply` stops part-way because of AWS throttling, missing permissions, or validation errors

**Resolution**
1. Review Terraform error output for the failing resource
2. Manually inspect AWS console / CLI to verify partial resources
3. Fix configuration or IAM permissions
4. Re-run the same command: `./scripts/deploy_infra.sh -<env> apply`
5. If resources are stuck in an inconsistent state, destroy failed resources manually then re-run apply

---

## 5. Secrets Manager Issues

**Symptoms**
- Lambda cannot read secrets
- Terraform apply fails on secret policy updates

**Resolution**
1. Re-run `./scripts/setup-secrets.sh --env <env>` to push correct values
2. Inspect IAM policies:
   ```bash
   aws secretsmanager get-resource-policy \
     --secret-id naver-sms-automation/<env>/naver-credentials
   ```
3. Ensure the Lambda execution role and CI deployment role ARNs match the values in `environments/<env>.tfvars`

---

## 6. Emergency Sandbox Teardown

**Use only for sandbox.**

```bash
./scripts/deploy_infra.sh -sandbox destroy
```

Record the teardown timestamp and resulting cleanup status in `docs/qa/infra-validation-1.5.md`.

---

## 7. CloudWatch Dashboard / Alarm Drift

**Symptoms**
- Dashboard widgets missing metrics or show `Insufficient Data`
- Alarms fail to trigger after metric filter updates

**Resolution**
1. Confirm metric filters exist: `aws logs describe-metric-filters --log-group-name "/aws/lambda/<function>"`
2. Check namespace used: `NaverSMSAutomation` by default
3. Reapply Terraform to ensure metric filters and alarms match the desired configuration
4. For new metrics, wait 5-10 minutes for data to propagate

---

## 8. IAM Policy Review

**Checklist**
- No wildcard (`*`) principals or actions unless accompanied by justification comment
- Roles limited to least privilege actions listed in `docs/qa/required-iam-policy.json`
- Validate with IAM policy simulator: `https://policysim.aws.amazon.com/`

---

## Incident Documentation

For every incident:
1. Record the context, root cause, and fix in `docs/qa/infra-validation-1.5.md`
2. Update `docs/qa/infra-security-review-1.5.md` if permissions changed
3. Notify stakeholders with summary and follow-up items

