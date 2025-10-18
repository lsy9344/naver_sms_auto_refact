# Infra Validation Report – Story 1.5

> Populate this document immediately after executing the sandbox deployment. Replace all `TODO` markers with real values captured from Terraform outputs and AWS console verification.

---

## Deployment Summary

- **Environment:** sandbox
- **Terraform Version:** TODO
- **AWS Provider Version:** TODO
- **Deployment Timestamp (UTC):** TODO
- **Operator:** TODO

---

## Terraform Outputs (YAML)

```yaml
resource_outputs:
  environment: sandbox
  ecr_repository_uri: TODO
  ecr_repository_arn: TODO
  ecr_registry_id: TODO
  secrets:
    naver_credentials_name: TODO
    naver_credentials_arn: TODO
    sens_credentials_name: TODO
    sens_credentials_arn: TODO
    telegram_credentials_name: TODO
    telegram_credentials_arn: TODO
  cloudwatch:
    log_group_name: TODO
    log_group_arn: TODO
    dashboard_url: TODO
    sns_topic_arn: TODO
    metric_filters:
      sms_sent_total: TODO
      sms_failed_total: TODO
      login_failure_total: TODO
      secrets_error_total: TODO
    alarms:
      lambda_errors: TODO
      secrets_errors: TODO
      login_failures: TODO
```

---

## Validation Checklist

- [ ] `terraform fmt -check`
- [ ] `terraform validate`
- [ ] `tflint`
- [ ] `terraform plan` reviewed by peer (attach artifact link)
- [ ] Secrets retrievable via AWS CLI (`aws secretsmanager get-secret-value`)
- [ ] Metric filters emitting data (`aws logs describe-metric-filters`)
- [ ] SNS subscription confirmed (email)
- [ ] Dashboard loads without errors

Document findings or screenshots here:

```
TODO: Attach evidence links / notes
```

---

## Teardown

- **Destroy Command:** `./scripts/deploy_infra.sh -sandbox destroy`
- **Teardown Timestamp (UTC):** TODO
- **Residual Resources:** TODO (list or confirm none)

---

## Sign-off

- **QA Reviewer:** TODO
- **Date:** TODO
- **Decision:** PASS / CONCERNS / FAIL (choose one)
- **Notes:** TODO

