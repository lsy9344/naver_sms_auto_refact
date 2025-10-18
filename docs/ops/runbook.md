# Naver SMS Automation - Operations Runbook

This runbook documents how to respond to CloudWatch alarms, interpret dashboards, and troubleshoot the Naver SMS automation service.

## CloudWatch Dashboard Overview

**Dashboard Name:** `naver-sms-automation-dashboard`

**URL:** [Open in AWS Console](https://console.aws.amazon.com/cloudwatch/home?region=ap-northeast-2#dashboards:name=naver-sms-automation-dashboard)

### Dashboard Widgets

1. **SMS Delivery Volume (5-min)**
   - Shows SMS sent vs failed in 5-minute buckets
   - Goal: High "SMS Sent" count, minimal "SMS Failed"
   - Action if concerning: Check Lambda logs for send failures

2. **Error Metrics (5-min)**
   - Lambda Errors: Unhandled exceptions in Lambda
   - Login Failures: Naver authentication failures
   - Secrets Errors: AWS Secrets Manager retrieval failures
   - Goal: All metrics at 0
   - Action if non-zero: See alarm response sections below

3. **Log Summary by Status (Last 1h)**
   - Summary of logs grouped by status field
   - Goal: Mostly "success" entries
   - Action if high failure rate: Investigate recent code changes

4. **Lambda Duration Percentiles (5-min)**
   - p50 and p95 execution time in milliseconds
   - Goal: p95 < 5000ms (5 seconds)
   - Action if increasing: Check for performance regressions

5. **Lambda Invocations & Throttles (5-min)**
   - Total invocations vs throttled invocations
   - Goal: No throttles (indicates concurrency limit hit)
   - Action if throttles: Request Lambda concurrency increase

---

## Alarm Responses

### 🔴 **Alarm: Lambda Errors (Severity: HIGH)**

**Threshold:** ≥1 error in 5 minutes

**Meaning:** Lambda function encountered an unhandled exception or timed out.

**Response Steps:**

1. **Check CloudWatch Logs**
   ```
   Log Group: /aws/lambda/naver-sms-automation
   Recent 5-minute window for ERROR level entries
   ```

2. **Common Causes:**
   - Secrets retrieval failure → See Secrets Error alarm
   - Naver login failure → Check login credentials validity
   - Network/timeout → Review Lambda timeout configuration
   - Code bug → Check recent deployments

3. **Immediate Actions:**
   - Check if issue is transient (single error) or persistent (multiple errors)
   - If transient and no pattern, monitor and wait
   - If persistent, start [Debugging Procedure](#debugging-procedure)

4. **Escalation:**
   - If cannot resolve in 15 minutes, engage development team
   - Provide CloudWatch log excerpts with ERROR entries

---

### 🟠 **Alarm: Secrets Retrieval Errors (Severity: HIGH)**

**Threshold:** ≥1 error in 15 minutes

**Meaning:** Lambda failed to retrieve credentials from AWS Secrets Manager.

**Response Steps:**

1. **Verify Secrets Exist**
   ```bash
   aws secretsmanager list-secrets --filters "Key=name,Values=naver-sms-automation" --region ap-northeast-2
   ```
   Should return 3 secrets: naver-credentials, sens-credentials, telegram-credentials

2. **Check IAM Permissions**
   ```bash
   # Verify Lambda role has secretsmanager:GetSecretValue permission
   aws iam get-role-policy --role-name naver-sms-automation-lambda-role --policy-name cloudwatch-logs --region ap-northeast-2
   ```

3. **Check KMS Encryption** (if using custom key)
   ```bash
   # Verify Lambda role has kms:Decrypt permission for Secrets Manager KMS key
   aws kms describe-key --key-id <key-id> --region ap-northeast-2
   ```

4. **Common Causes:**
   - Secret deleted accidentally
   - IAM policy detached from Lambda role
   - KMS key rotation or permissions change
   - Temporary AWS API issue

5. **Recovery:**
   - If secret deleted: Restore from backup or recreate
   - If IAM policy missing: Reattach via Terraform `terraform apply`
   - If KMS issue: Check key policy and grant Lambda role access

---

### 🟡 **Alarm: Login Failures (Severity: MEDIUM)**

**Threshold:** ≥3 failures in 30 minutes

**Meaning:** Naver authentication is failing repeatedly. May indicate credential issues or Naver website changes.

**Response Steps:**

1. **Check Credential Validity**
   ```bash
   # Verify credentials are correct in Secrets Manager
   aws secretsmanager get-secret-value --secret-id naver-sms-automation/naver-credentials --region ap-northeast-2
   ```

2. **Check Naver Service Status**
   - Visit https://www.naver.com and test login manually
   - Check if Naver has blocked the automation's IP/user-agent

3. **Review Recent Code Changes**
   - Check if login logic was recently modified
   - Review browser/Selenium version compatibility

4. **Check CloudWatch Logs for Login Errors**
   ```
   Log Group: /aws/lambda/naver-sms-automation
   Filter: action_type = "login" AND status = "failure"
   ```

5. **Common Causes:**
   - Credentials expired or incorrect
   - Naver account locked (too many failed attempts)
   - Naver website structure changed (Selenium selectors invalid)
   - Browser driver version incompatible

6. **Recovery:**
   - Update credentials if changed
   - Reset Naver account if locked
   - Update Selenium selectors if website changed
   - Update browser driver version if outdated

---

## Debugging Procedure

### Access CloudWatch Logs

1. **Navigate to CloudWatch Logs Console**
   ```
   Region: ap-northeast-2
   Log Group: /aws/lambda/naver-sms-automation
   ```

2. **Search for Specific Issues**
   - By request_id: `{ $.request_id = "xxx-yyy-zzz" }`
   - By status: `{ $.status = "failure" }`
   - By action: `{ $.action_type = "send_sms" }`
   - By time range: Use log group UI time picker

3. **View Full Log Entry**
   - Click on any log entry to see complete JSON
   - Look for error messages and stack traces

### Use CloudWatch Logs Insights

1. **Query All Errors in Last Hour**
   ```sql
   fields @timestamp, message, status, action_type
   | filter status = "failure"
   | sort @timestamp desc
   | limit 50
   ```

2. **Count Failures by Type**
   ```sql
   fields action_type, status
   | filter status = "failure"
   | stats count() by action_type
   ```

3. **Find Errors for Specific Rule**
   ```sql
   fields @timestamp, message, status
   | filter rule_name = "new_booking_notification"
   | filter status = "failure"
   ```

See [CloudWatch Queries Documentation](cloudwatch-queries.md) for more examples.

### Monitor Lambda Metrics

1. **Duration**
   - If suddenly increasing, may indicate network slowness or code regression
   - Check if Naver website is responding slower

2. **Throttles**
   - If throttles occurring, Lambda concurrency limit reached
   - Request increase or optimize code for faster execution

3. **Errors**
   - Spike in errors → Check recent deployment
   - Gradual increase → May indicate resource exhaustion

---

## Incident Response Matrix

| Symptom | Likely Cause | Check First | Fix |
|---------|--------------|-------------|-----|
| Lambda Errors spike | Code bug | Deploy logs, recent code changes | Rollback or hot-fix |
| Lambda Errors + Secrets Errors | Secrets issue | IAM policy, secret exists | Reattach policy or recreate secret |
| Login Failures increase | Naver issue | Website status, selectors | Update selectors, reset account |
| No SMS being sent | Low invocation count | Schedule/trigger | Check EventBridge/CloudWatch Events |
| High duration | Performance issue | Network latency, DB queries | Optimize code, increase timeout |

---

## Maintenance Tasks

### Daily
- Monitor dashboard for error trends
- Acknowledge and resolve any active alarms
- Check Lambda invocation count meets expectations

### Weekly
- Review CloudWatch Logs Insights queries for patterns
- Analyze cost metrics
- Test manual runbook procedures

### Monthly
- Review and tune alarm thresholds based on patterns
- Rotate logs for archival (automated by 90-day retention)
- Plan for major version upgrades

---

## Contact & Escalation

**On-Call Developer:** [TBD in team calendar]

**Escalation Path:**
1. Try debugging steps in this runbook (10 min max)
2. If unresolved, page on-call developer
3. If developer unavailable, escalate to engineering manager

**Communication:**
- Critical issues: Page immediately
- High priority: Slack #alerts channel
- Medium: JIRA ticket with alarm context

---

## Related Documentation

- [CloudWatch Queries Guide](cloudwatch-queries.md) - Logs Insights query examples
- [Architecture Overview](../../docs/architecture.md) - System design
- [Lambda Configuration](../../infrastructure/cloudwatch.tf) - Terraform IaC
- [Secrets Manager Setup](../../docs/infra/secrets-manager.md) - Credential management
