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

## Story 5.4: Comparison Monitoring (Validation Campaign)

**Status:** Active during offline validation phase before production cutover

**Purpose:** Monitor functional parity between old and new Lambda implementations to validate readiness for production.

### Dashboard Widgets (Comparison Section)

1. **Comparison: Run Count & Discrepancies (5-min)**
   - ComparisonRun: Number of comparison invocations
   - SMSMismatchCount: SMS payload differences detected
   - DBMismatchCount: DynamoDB operation differences detected
   - TelegramMismatchCount: Telegram notification differences detected
   - Goal: All mismatch counts at 0
   - Success Criterion: Run count >0, all mismatches = 0 for 7 days

2. **Comparison: Match Percentage Stats (Last 1h)**
   - Tracks percentage match between old and new Lambda outputs
   - Goal: 100% match (avg, min, max all = 100)
   - Success Criterion: 100% parity maintained throughout validation window

3. **Comparison: Event-Type Breakdown (Last 1h)**
   - Displays mismatch count by type (SMS, DB, Telegram)
   - Helps identify which subsystem needs investigation
   - Goal: All counts = 0

4. **Comparison: Recent SMS Mismatches (Last 1h)**
   - Shows latest SMS discrepancies with booking ID, phone (masked), and sample diffs
   - Allows engineers to investigate specific mismatches
   - Goal: Empty table (no mismatches)

### Key CloudWatch Queries for Troubleshooting

**Quick Health Check (Run this daily):**
```sql
fields @timestamp, event_type, match_percentage
| filter event_type = "comparison_summary"
| stats avg(match_percentage) as avg_match, count() as runs
```
Expected: avg_match = 100, runs > 0

**Find Recent Mismatches:**
```sql
fields @timestamp, event_type, booking_id, match
| filter match = false
| sort @timestamp desc
| limit 50
```
Expected: Empty result

**Verify Comparison Configuration:**
```sql
fields @timestamp, comparison_mode, sms_send_enabled
| filter event_type = "comparison_summary"
| stats values(comparison_mode) as mode, values(sms_send_enabled) as enabled
| limit 1
```
Expected: mode = "comparison", sms_send_enabled = false (never send actual SMS during validation)

See [CloudWatch Queries Guide](cloudwatch-queries.md#story-54-comparison-monitoring-queries) for additional queries.

### Alarms: Comparison Monitoring

**🔴 Alarm: Comparison Discrepancies Detected (Severity: HIGH)**
- **Threshold:** SMSMismatchCount ≥ 0 (triggers on any mismatch)
- **Meaning:** Old and new Lambda produced different SMS content
- **Action:**
  1. Check dashboard "Comparison: Recent SMS Mismatches" widget
  2. Run query: `fields @timestamp, booking_id, sms_old, sms_new | filter event_type = "sms_comparison" and match = false`
  3. Compare old vs new SMS content
  4. Identify logic difference in new Lambda
  5. File issue with specific booking ID for reproduction

**🔴 Alarm: DB Operation Mismatches (Severity: HIGH)**
- **Threshold:** DBMismatchCount ≥ 0
- **Meaning:** Old and new Lambda wrote different data to DynamoDB
- **Action:**
  1. Check dashboard for affected bookings
  2. Query: `fields @timestamp, booking_id, operation_type, db_old, db_new | filter event_type = "db_operation_comparison" and match = false`
  3. Compare operation sequences and results
  4. Check if write conflicts or timing issues involved

**🟠 Alarm: Comparison Match Percentage Below 100% (Severity: HIGH)**
- **Threshold:** Match percentage < 100%
- **Meaning:** Overall parity dropped below target
- **Action:**
  1. Check all mismatch alarms above
  2. Determine which component type has issues (SMS/DB/Telegram)
  3. Escalate to development team with query results

**🟡 Alarm: Telegram Mismatches (Severity: MEDIUM)**
- **Threshold:** TelegramMismatchCount ≥ 0
- **Meaning:** Telegram notification behavior differs
- **Action:**
  1. Query: `fields @timestamp, booking_id, telegram_action_old, telegram_action_new | filter event_type = "telegram_comparison" and match = false`
  2. Verify if differences are significant (e.g., message content vs delivery timing)
  3. Decide if acceptable for production or requires fix

### Response Workflow for Validation Campaign

**Step 1: Acknowledge Alarm**
- Review which comparison metric triggered
- Open dashboard to see context

**Step 2: Assess Impact**
- Is this a single isolated mismatch or pattern?
- How long has it been occurring?
- Affects how many bookings?

**Step 3: Investigate Root Cause**
- Use CloudWatch Logs Insights queries (see queries section above)
- Check recent code deployments to new Lambda
- Verify no environment differences (secrets, configuration)

**Step 4: Document for QA**
- Collect evidence: dashboard screenshot, query results, affected booking IDs
- Append to VALIDATION.md file
- Note whether issue is blockers for go/no-go or acceptable risk

**Step 5: Escalate if Needed**
- If blocking issue: Halt validation, notify development team
- If non-blocking: Continue monitoring, document in go/no-go sign-off

### Success Criteria for Validation Sign-Off

- ✅ Zero SMS mismatches over 7-day validation window
- ✅ Zero DynamoDB operation mismatches
- ✅ Zero Telegram notification mismatches
- ✅ 100% match percentage maintained
- ✅ All dashboard widgets show zero discrepancies
- ✅ Evidence collected and archived in VALIDATION.md

### Post-Campaign Tasks

Once validation complete and approved:
1. **Disable Comparison Mode:** Set `COMPARISON_MODE_ENABLED = false` in Lambda configuration
2. **Archive Evidence:** Save all dashboard screenshots and query results to VALIDATION.md
3. **Transition to Production:** Enable new Lambda via EventBridge rule
4. **Monitor Post-Cutover:** Switch to standard operational alarms (see sections above)

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
