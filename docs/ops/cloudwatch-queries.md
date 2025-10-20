# CloudWatch Logs Insights Query Examples

This document provides ready-to-use CloudWatch Logs Insights queries for monitoring and troubleshooting the Naver SMS automation service.

## Getting Started

1. Navigate to [CloudWatch Logs Insights](https://console.aws.amazon.com/cloudwatch/home?region=ap-northeast-2#logsV2:logs-insights)
2. Select log group: `/aws/lambda/naver-sms-automation`
3. Select time range (e.g., "Last 1 hour")
4. Paste a query from below
5. Click "Run query"

---

## Basic Queries

### 1. View All Logs in Last Hour

```sql
fields @timestamp, level, message, status, action_type
| sort @timestamp desc
| limit 100
```

**Use:** Get overview of recent activity

---

### 2. Show Only Errors

```sql
fields @timestamp, message, status, request_id, error_code
| filter status = "failure" or level = "ERROR"
| sort @timestamp desc
| limit 50
```

**Use:** Quickly find all failures

---

### 3. Show Only Warnings

```sql
fields @timestamp, message, status, request_id
| filter level = "WARNING"
| sort @timestamp desc
| limit 50
```

**Use:** Monitor potentially problematic situations

---

## Metric Aggregation Queries

### 4. Count Logs by Status

```sql
fields status
| stats count() by status
```

**Use:** Get summary of success vs failure rates

**Output Example:**
```
status     | count
-----------|------
success    | 450
failure    | 12
```

---

### 5. Count Errors by Action Type

```sql
fields action_type, status
| filter status = "failure"
| stats count() by action_type
```

**Use:** Identify which operations are failing

---

### 6. Logs per Hour

```sql
fields @timestamp
| stats count() by bin(1h)
```

**Use:** Identify busiest time periods and anomalies

---

## Filtering Queries

### 7. Filter by Rule Name

```sql
fields @timestamp, message, rule_name, status
| filter rule_name = "new_booking_notification"
| sort @timestamp desc
| limit 50
```

**Use:** Monitor specific automation rule

**Note:** Replace `"new_booking_notification"` with desired rule name

---

### 8. Filter by Request ID

```sql
fields @timestamp, message, status, action_type
| filter request_id = "abc123-def456"
```

**Use:** Trace complete request flow

**Note:** Request IDs appear in all related logs

---

### 9. Filter by Phone Number Suffix

```sql
fields @timestamp, message, phone_number, status
| filter phone_number like /5678$/
| sort @timestamp desc
| limit 50
```

**Use:** Find all SMS sent to specific customer (last 4 digits)

---

### 10. Find All Login Failures

```sql
fields @timestamp, message, status, request_id
| filter action_type = "login" and status = "failure"
| sort @timestamp desc
| limit 30
```

**Use:** Troubleshoot authentication issues

---

## Performance Queries

### 11. Slowest Requests (by Duration)

```sql
fields @timestamp, message, request_id, duration_ms
| filter ispresent(duration_ms)
| sort duration_ms desc
| limit 20
```

**Use:** Find performance bottlenecks

---

### 12. Requests Taking Longer Than 5 Seconds

```sql
fields @timestamp, request_id, action_type, duration_ms
| filter duration_ms > 5000
| sort duration_ms desc
```

**Use:** Identify slow operations

---

### 13. Average Duration by Action Type

```sql
fields action_type, duration_ms
| filter ispresent(duration_ms)
| stats avg(duration_ms) as avg_ms, max(duration_ms) as max_ms by action_type
```

**Use:** Performance baseline for each action

---

## Time-Based Analysis

### 14. Failures per Day

```sql
fields @timestamp, status
| filter status = "failure"
| stats count() as failures by bin(1d)
```

**Use:** Identify daily failure patterns

---

### 15. SMS Volume Trend (Hourly)

```sql
fields @timestamp, action_type
| filter action_type = "send_sms" and status = "success"
| stats count() as sms_sent by bin(1h)
```

**Use:** Monitor SMS sending volume trend

---

### 16. Errors by Hour (Find Peak Error Times)

```sql
fields @timestamp, status
| filter status = "failure"
| stats count() as errors by bin(1h)
| sort errors desc
```

**Use:** Identify when most errors occur

---

## Secrets & Security Queries

### 17. All Secrets-Related Errors

```sql
fields @timestamp, message, status, component
| filter component = "secrets" and status = "failure"
| sort @timestamp desc
```

**Use:** Monitor credential retrieval issues

---

### 18. Count Redacted Values in Logs

```sql
fields @timestamp, message
| filter message like /\*\*\*REDACTED\*\*\*/
| stats count()
```

**Use:** Verify PII redaction is working (should be frequent for sensitive operations)

---

## Debugging Queries

### 19. Trace Request from Start to End

```sql
fields @timestamp, message, status, action_type
| filter request_id = "INSERT_REQUEST_ID_HERE"
| sort @timestamp asc
```

**Use:** Follow complete request lifecycle

**Steps:**
1. Find interesting request_id from other queries
2. Replace `INSERT_REQUEST_ID_HERE`
3. See all actions and status for that request

---

### 20. Find Errors Within Time Window

```sql
fields @timestamp, message, status, error_code, request_id
| filter @timestamp >= "2025-10-19 14:30:00" and @timestamp <= "2025-10-19 14:45:00"
| filter status = "failure"
| sort @timestamp desc
```

**Use:** Investigate specific incident by time

**Steps:**
1. Adjust time range to incident window
2. Review error_code field
3. Use request_id to trace full context

---

## Report-Style Queries

### 21. Daily Summary Report

```sql
fields @timestamp, status, action_type
| stats count() as total,
        count(case when status = "success" then 1 end) as success_count,
        count(case when status = "failure" then 1 end) as failure_count
        by action_type, bin(1d)
```

**Use:** Generate daily operational report

---

### 22. Success Rate by Rule

```sql
fields rule_name, status
| stats count() as total,
        count(case when status = "success" then 1 end) as success_count
        by rule_name
| fields rule_name, success_count, total, (success_count / total * 100) as success_rate_pct
```

**Use:** Identify rules with low success rates

---

### 23. Error Distribution (Top 10)

```sql
fields message
| filter status = "failure"
| stats count() as error_count by message
| sort error_count desc
| limit 10
```

**Use:** Find most common errors

---

## Advanced Patterns

### 24. Detect Anomalies (Sudden Spike in Errors)

```sql
fields @timestamp, status
| stats count() as log_count by bin(5m)
| filter log_count > 100
```

**Use:** Find abnormal periods

**Note:** Adjust threshold (100) based on normal baseline

---

### 25. Missing Logs (Gaps in Activity)

```sql
fields @timestamp
| stats count() as log_count by bin(1h)
| filter log_count < 5
```

**Use:** Identify when Lambda isn't being invoked

---

## Story 5.4: Comparison Monitoring Queries

These queries support monitoring the comparison validation campaign for dual-Lambda deployment readiness.

### Query 1: Comparison Summary Statistics (Last 24h)

```sql
fields @timestamp, event_type, sms_sent_old, sms_sent_new, match_percentage, sms_match_old, sms_match_new
| filter event_type = "comparison_summary"
| stats count() as runs, avg(match_percentage) as avg_match, min(match_percentage) as min_match, max(match_percentage) as max_match by bin(1h)
```

**Use:** Track overall comparison health over time. 100% match_percentage indicates full parity.

**Output Example:**
```
Time (bin)  | runs | avg_match | min_match | max_match
------------|------|-----------|-----------|----------
1h ago      | 3    | 100       | 100       | 100
2h ago      | 3    | 100       | 100       | 100
```

---

### Query 2: All Detected Mismatches (Last 24h)

```sql
fields @timestamp, event_type, booking_id, phone_masked, match, sample_diffs
| filter match = false
| sort @timestamp desc
| limit 500
```

**Use:** Review all discrepancies found during comparison. Each row = one mismatch.

**Output Columns:**
- `event_type` - Type of mismatch (sms_comparison, db_operation_comparison, telegram_comparison)
- `booking_id` - Booking ID that triggered mismatch
- `phone_masked` - Customer phone (masked for security)
- `sample_diffs` - Up to 10 sample differences for debugging

---

### Query 3: Mismatch Count by Type (Last 24h)

```sql
fields event_type
| filter event_type like /comparison_/ and match = false
| stats count() as mismatches by event_type
```

**Use:** Identify which comparison types have issues (SMS, DB, Telegram).

**Output Example:**
```
event_type             | mismatches
-----------------------|----------
sms_comparison         | 5
db_operation_comparison| 2
telegram_comparison    | 0
```

---

### Query 4: SMS Mismatch Details (Last 24h)

```sql
fields @timestamp, booking_id, phone_masked, sms_old, sms_new, sample_diffs
| filter event_type = "sms_comparison" and match = false
| sort @timestamp desc
| limit 100
```

**Use:** Debug SMS payload differences between old and new Lambda.

**Fields:**
- `sms_old` - SMS text from old Lambda
- `sms_new` - SMS text from new Lambda
- `sample_diffs` - Up to 10 differing character positions

---

### Query 5: Database Operation Mismatches (Last 24h)

```sql
fields @timestamp, booking_id, operation_type, db_old, db_new, sample_diffs
| filter event_type = "db_operation_comparison" and match = false
| sort @timestamp desc
| limit 100
```

**Use:** Track DynamoDB write/update discrepancies.

**Fields:**
- `operation_type` - DynamoDB operation (put_item, update_item, etc.)
- `db_old` - Old Lambda DynamoDB output
- `db_new` - New Lambda DynamoDB output

---

### Query 6: Telegram Event Comparison (Last 24h)

```sql
fields @timestamp, booking_id, telegram_action_old, telegram_action_new, match
| filter event_type = "telegram_comparison"
| stats count() as total, sum(case when match = true then 1 else 0 end) as matched by match
```

**Use:** Verify Telegram notification parity.

**Output Example:**
```
match | total | matched
------|-------|--------
true  | 150   | 150
false | 2     | 0
```

---

### Query 7: Match Percentage Trend (Last 7 Days)

```sql
fields @timestamp, match_percentage
| filter event_type = "comparison_summary"
| stats avg(match_percentage) as avg_match by bin(6h)
| sort @timestamp desc
```

**Use:** Monitor validation campaign progress. Expect 100% for go/no-go approval.

---

### Query 8: Recent Failures in Comparison (Last 24h)

```sql
fields @timestamp, level, message, status
| filter (event_type like /comparison_/ or level = "ERROR") and status = "failure"
| sort @timestamp desc
| limit 50
```

**Use:** Identify any errors in the comparison system itself.

---

### Query 9: Comparison Configuration Audit (Last 7 Days)

```sql
fields @timestamp, comparison_mode, sms_send_enabled, event_type
| filter event_type = "comparison_summary"
| stats values(comparison_mode) as mode, values(sms_send_enabled) as sms_enabled by bin(1h)
| limit 100
```

**Use:** Verify comparison mode remained in test (SMS sending disabled) throughout validation campaign.

---

### Query 10: Performance: Comparison Duration (Last 24h)

```sql
fields @timestamp, duration_ms
| filter event_type = "comparison_summary"
| stats avg(duration_ms) as avg_duration, max(duration_ms) as max_duration, pct(duration_ms, 95) as p95_duration
```

**Use:** Monitor comparison processing performance (should complete <10s per invocation).

---

## Tips & Tricks

### Exporting Results

1. After running query, click "Export results"
2. Choose format (CSV, JSON)
3. Save for analysis or archival

### Creating Dashboards from Queries

1. Run query successfully
2. Click "Add to dashboard"
3. Create new dashboard or add to existing
4. Customize widget display

### Saving Frequent Queries

1. After running query, click "Save"
2. Give it a descriptive name
3. Access from "Saved queries" tab

### Query Syntax Help

- `filter` - WHERE clause equivalent
- `fields` - SELECT specific fields
- `stats` - Aggregate (count, sum, avg, max, min)
- `sort` - ORDER BY
- `limit` - LIMIT rows
- `like` - Pattern matching with regex
- `bin(1h)` - Group by time interval

### Common Field Names

- `@timestamp` - Log entry timestamp
- `level` - Log level (DEBUG, INFO, WARNING, ERROR)
- `message` - Main log message
- `status` - Operation status (success/failure)
- `action_type` - Type of action (send_sms, login, etc.)
- `request_id` - Request correlation ID
- `rule_name` - Automation rule name
- `phone_number` - Customer phone (masked)
- `error_code` - Specific error identifier
- `duration_ms` - Operation duration in milliseconds

---

## Troubleshooting No Results

1. **Check time range** - Expand if too narrow
2. **Verify log group** - Must be `/aws/lambda/naver-sms-automation`
3. **Check filter conditions** - Ensure fields/values exist
4. **Review field names** - Case-sensitive and must be exact
5. **Use simpler query first** - Start with `fields @timestamp | limit 10` to verify data exists

---

## Related Documentation

- [Operations Runbook](runbook.md) - How to respond to issues
- [CloudWatch Dashboard](../../infrastructure/cloudwatch.tf) - Dashboard configuration
- [Logging Implementation](../../src/utils/logger.py) - How logs are generated
