# Security Review – Story 1.5 Infrastructure as Code

Complete this checklist during QA sign-off. Attach evidence (policy simulator screenshots, CLI outputs) where relevant.

---

## Reviewer Metadata

- **Reviewer:** TODO
- **Date:** TODO
- **AWS Account:** TODO
- **Workspace:** TODO (dev/staging/prod)

---

## IAM & Access Controls

- [ ] ECR repository policy grants pull access only to the Lambda execution role (`lambda_role_arn`)
- [ ] ECR repository policy grants push access only to CI / deployment role (`ci_deployment_role_arn`)
- [ ] No wildcard (`*`) principals or actions without documented justification
- [ ] Secrets Manager resource policies limited to Lambda + CI roles
- [ ] SNS topic permissions restricted to expected subscribers
- [ ] Default tags present (`Project`, `ManagedBy`, `Environment`, `ProvisionedBy`)

Evidence / notes:
```
TODO
```

---

## Least Privilege Validation

- [ ] IAM Policy Simulator run for Lambda role (secrets read only)
- [ ] IAM Policy Simulator run for CI role (secrets write + ECR push)
- [ ] Terraform S3 backend bucket restricted to specific roles
- [ ] DynamoDB locking table restricted to Terraform roles

Evidence / notes:
```
TODO
```

---

## Secrets Handling

- [ ] No plain-text secrets committed to repo
- [ ] `scripts/setup-secrets.sh` tested (dry run + real run)
- [ ] Secrets stored under `naver-sms-automation/<env>/` namespace
- [ ] Rotation process documented / referenced in ops runbooks

---

## Findings & Recommendations

```
TODO: list any issues, required follow-up tasks, or waivers.
```

---

## Decision

- [ ] PASS – Meets security requirements
- [ ] CONCERNS – Ship with follow-up tasks recorded
- [ ] FAIL – Block release until resolved

Signature: TODO

