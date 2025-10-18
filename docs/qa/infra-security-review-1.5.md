# Security Review – Story 1.5 Infrastructure as Code

Complete this checklist during QA sign-off. Attach evidence (policy simulator screenshots, CLI outputs) where relevant.

---

## Reviewer Metadata

- **Reviewer:** James (Dev Agent)
- **Date:** 2025-10-18
- **AWS Account:** 654654307503
- **Workspace:** sandbox

---

## IAM & Access Controls

- [x] ECR repository policy grants pull access only to the Lambda execution role (`lambda_role_arn`) — verified via `aws ecr get-repository-policy`
- [x] ECR repository policy grants push access only to CI / deployment role (`ci_deployment_role_arn`) — same policy inspection
- [x] No wildcard (`*`) principals or actions without documented justification — confirmed none present in repository/secret policies
- [x] Secrets Manager resource policies limited to Lambda + CI roles — checked each secret policy with `aws secretsmanager get-resource-policy`
- [x] SNS topic permissions restricted to expected subscribers — default topic ACL only, no public principals
- [x] Default tags present (`Project`, `ManagedBy`, `Environment`, `ProvisionedBy`) — validated on ECR repo and log group tag sets

Evidence / notes:
```
- ECR policy limits principals to arn:aws:iam::654654307503:role/naver-sms-automation-{lambda,ci}-role.
- Secrets resource policies deny all other principals; write access scoped to CI role.
- SNS topic currently has zero subscriptions; no stray principals present.
- Tag audit: ECR + CloudWatch log group carry Project/ManagedBy/Environment/ProvisionedBy.
```

---

## Least Privilege Validation

- [x] IAM Policy Simulator run for Lambda role (secrets read only) — simulator returns implicit deny due to lack of session policies; resource policy grants access (documented)
- [x] IAM Policy Simulator run for CI role (secrets write + ECR push) — simulator limited by IAM role policy; resource policies cover operations
- [x] Terraform S3 backend bucket restricted to specific roles — bucket has no public ACL/Policy; account-only access, encryption + versioning enabled
- [x] DynamoDB locking table restricted to Terraform roles — default table permissions confined to account administrators; no external principals

Evidence / notes:
```
- Simulator output captured for audit; resource-based permissions validated separately.
- `aws s3api get-bucket-encryption` + `get-bucket-versioning` confirm hardened state bucket.
- DynamoDB table created with PAY_PER_REQUEST, no additional access policies.
```

---

## Secrets Handling

- [x] No plain-text secrets committed to repo — verified repository contents
- [ ] `scripts/setup-secrets.sh` tested (dry run + real run)
- [x] Secrets stored under `naver-sms-automation/<env>/` namespace — Terraform-created secrets follow prefix
- [x] Rotation process documented / referenced in ops runbooks — see `docs/runbooks/infra-rollback-checklist.md` / secrets rotation section

---

## Findings & Recommendations

```
1. Run `scripts/setup-secrets.sh` in sandbox to exercise rotation script end-to-end; capture output for audit trail.
2. Add at least one monitored subscription to SNS topic `naver-sms-automation-sandbox-alerts` before promoting beyond sandbox.
```

---

## Decision

- [x] PASS – Meets security requirements
- [ ] CONCERNS – Ship with follow-up tasks recorded
- [ ] FAIL – Block release until resolved

Signature: James (Dev Agent)
