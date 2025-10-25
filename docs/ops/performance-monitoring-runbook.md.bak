# Performance Monitoring & Alerts Runbook

**Story 4.5: Performance Testing & Optimization (AC 4, 5)**

**Date Created:** 2025-10-20  
**Version:** 1.0  
**Author:** James (Dev Agent)

---

## Overview

This runbook provides step-by-step instructions for monitoring Lambda performance, detecting regressions, and responding to performance alerts in production. All queries are built from structured logging fields and CloudWatch Insights.

**Performance Thresholds (from PRD, docs/prd.md:234-238):**
- Execution Duration: ≤ 4 minutes (240 seconds)
- Cold Start: ≤ 10 seconds
- Memory Usage: ≤ 512 MB
- DynamoDB Latency: ≤ 100 ms per operation

---

## 1. CloudWatch Log Group & Logging Setup

### Log Group
```
/aws/lambda/naverplace_send_inform
```

### Expected Log Format (Structured Logging)
All operations log with these fields via `logger.info/error(..., duration_ms=...)`

Example from `src/utils/logger.py`:
```json
{
  "timestamp": "2025-10-20T14:59:00.123Z",
  "level": "INFO",
  "function": "naverplace_send_inform",
  "phase": "authenticate",
  "duration_ms": 2345.67,
  "status": "success",
  "message": "Naver authentication completed",
  "booking_id": "BOOKING_001"
}
```

### Key Phases Logged
1. `load_settings` - Configuration loading
2. `authenticate` - Naver login & session validation
3. `process_rules` - Rule engine execution
4. `send_summary` - SMS/Telegram notification
5. `update_database` - DynamoDB write operations

---

## 2. CloudWatch Insights Queries

### 2.1 Execution Duration - Slowest Requests (Last 1 Hour)

**Purpose:** Identify requests taking > 10 seconds or close to 4-minute limit

```
fields @timestamp, @duration, phase, booking_id
| filter ispresent(duration_ms)
| stats max(duration_ms) as max_duration, avg(duration_ms) as avg_duration by booking_id
| filter max_duration > 10000
| sort max_duration desc
| limit 20
```

**Interpretation:**
- `max_duration > 10000` = Request took >10 seconds
- `max_duration > 240000` = **CRITICAL** - Approaching timeout
- If any requests > 180000ms (3 min), investigate immediately

**Action Thresholds:**
- > 120000ms (2 min): 🟡 Yellow alert - Monitor
- > 180000ms (3 min): 🔴 Red alert - Investigate
- > 240000ms (4 min): 🔴🔴 Critical - Lambda will timeout

---

### 2.2 Per-Phase Duration Breakdown (Last 1 Hour)

**Purpose:** Identify which phase is causing slowdowns

```
fields @timestamp, phase, duration_ms, booking_id
| filter ispresent(duration_ms) and ispresent(phase)
| stats avg(duration_ms) as avg_phase_duration, max(duration_ms) as max_phase_duration, pct(duration_ms, 95) as p95_duration by phase
| sort max_phase_duration desc
```

**Expected Baseline (typical values):**
- `load_settings`: 200-500 ms
- `authenticate`: 3000-5000 ms (includes Selenium)
- `process_rules`: 1000-3000 ms
- `send_summary`: 500-2000 ms
- `update_database`: 300-800 ms

**If any phase exceeds 2x baseline:**
1. Identify which phase
2. Check for DynamoDB throttling or slow Selenium
3. Review query patterns

---

### 2.3 Operation Count & Throughput (Last 1 Hour)

**Purpose:** Monitor successful vs failed executions, detect volume spikes

```
fields @timestamp, @message, level, booking_id
| filter level = "INFO" or level = "ERROR"
| stats count() as total_invocations, count(level="ERROR") as error_count by @timestamp % 5m
| fields @timestamp, total_invocations, error_count
| sort @timestamp desc
```

**Interpretation:**
- `error_count = 0` for all windows = ✅ Healthy
- `error_count > 0` = 🔴 Investigate error logs
- `total_invocations` should be consistent (20 per hour is typical)

---

### 2.4 Memory Usage Tracking

**Purpose:** Monitor for memory leaks or unexpected spikes

```
fields @memoryUsed
| filter ispresent(@memoryUsed)
| stats avg(@memoryUsed/1024) as avg_memory_mb, max(@memoryUsed/1024) as max_memory_mb, pct(@memoryUsed/1024, 95) as p95_memory_mb
| filter max_memory_mb > 100
```

**Threshold:** ≤ 512 MB (Lambda limit)
- < 256 MB: ✅ Good headroom
- 256-400 MB: 🟡 Monitor for growth
- 400-512 MB: 🔴 Limited headroom - optimize
- > 512 MB: 🔴🔴 Critical - Lambda will OOM

---

### 2.5 DynamoDB Latency Monitoring

**Purpose:** Track DynamoDB operation performance and throttling

```
fields @timestamp, operation, latency_ms, status
| filter ispresent(operation) and ispresent(latency_ms)
| stats avg(latency_ms) as avg_latency, max(latency_ms) as max_latency, pct(latency_ms, 95) as p95_latency, pct(latency_ms, 99) as p99_latency by operation
| sort max_latency desc
```

**Expected Latencies:**
- GetItem: 10-50 ms
- PutItem: 10-50 ms
- Query (small result): 20-80 ms
- Scan (full table): 100-500 ms (or more if large table)

**If latency > 100 ms:**
1. Check DynamoDB throttling: `aws dynamodb describe-table --table-name sms`
2. Monitor CloudWatch metrics: `ConsumedReadCapacityUnits`, `ConsumedWriteCapacityUnits`
3. If throttled, increase provisioned capacity or implement caching

---

### 2.6 Error Analysis (Last 24 Hours)

**Purpose:** Track errors by type and frequency

```
fields @timestamp, @message, level, error_code
| filter level = "ERROR"
| stats count() as error_count by error_code
| sort error_count desc
```

**Common Error Codes to Watch:**
- `NAVER_AUTH_FAILED` - Login issue (check credentials)
- `DYNAMODB_THROTTLED` - Capacity exceeded
- `SMS_SERVICE_ERROR` - SENS API issue
- `RULE_ENGINE_FAILED` - Rule processing error
- `TIMEOUT` - Lambda execution timeout

**Action:** If error rate > 5% of total invocations, investigate immediately.

---

### 2.7 Cold-Start Detection (Last 24 Hours)

**Purpose:** Identify cold-start events and measure overhead

```
fields @duration, @memoryUsed, @initDuration, @message
| filter ispresent(@initDuration)
| stats count() as cold_starts, avg(@initDuration) as avg_init_duration, max(@initDuration) as max_init_duration, pct(@initDuration, 95) as p95_init_duration
```

**Expected Cold-Start Duration:**
- Baseline: 5-10 seconds (includes Lambda init + Selenium initialization)
- If > 10 seconds: 🔴 Investigate Selenium or dependency loading

**Optimization:** If cold-starts consistently > 10s:
1. Review `src/auth/session_manager.py` for lazy initialization
2. Check if Selenium driver is being created at startup
3. Consider connection pooling or caching

---

## 3. Setting Up CloudWatch Alarms

### 3.1 High Execution Duration Alarm

**AWS Console Steps:**
1. CloudWatch → Alarms → Create Alarm
2. Select Log Group: `/aws/lambda/naverplace_send_inform`
3. Create Metric Filter:
   ```
   [fields duration_ms] | max(duration_ms) > 180000
   ```
4. Threshold: 1 occurrence in 1 minute
5. Action: SNS notification to ops-team@company.com

**CLI Command:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda High Execution Duration" \
  --alarm-description "Alert if execution > 3 minutes" \
  --namespace "AWS/Lambda" \
  --metric-name "Duration" \
  --statistic "Maximum" \
  --period 300 \
  --threshold 180000 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions "arn:aws:sns:ap-northeast-2:ACCOUNT:ops-alerts"
```

### 3.2 Error Rate Alarm

**Threshold:** Error count > 2 in 5 minutes

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "Lambda Error Rate High" \
  --alarm-description "Alert if error count exceeds 2 per 5 min" \
  --namespace "AWS/Lambda" \
  --metric-name "Errors" \
  --statistic "Sum" \
  --period 300 \
  --threshold 2 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --alarm-actions "arn:aws:sns:ap-northeast-2:ACCOUNT:ops-alerts"
```

### 3.3 Memory Usage Alarm

**Threshold:** Peak memory > 400 MB (leaving 112 MB buffer)

```bash
aws logs put-metric-filter \
  --log-group-name "/aws/lambda/naverplace_send_inform" \
  --filter-name "HighMemoryUsage" \
  --filter-pattern "[fields @memoryUsed > 400000000]" \
  --metric-transformations \
    metricName="HighMemoryUsage",metricNamespace="CustomMetrics",metricValue=1
```

---

## 4. On-Call Response Procedures

### 4.1 Alert Received: High Execution Duration

**Step 1: Assess Severity (1 min)**
```bash
# Check recent execution times
aws logs start-query \
  --log-group-name "/aws/lambda/naverplace_send_inform" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, duration_ms | filter ispresent(duration_ms) | stats max(duration_ms) as max_duration, avg(duration_ms) as avg_duration'
```

**Step 2: Identify Bottleneck (2 min)**
```bash
# Check phase breakdown
aws logs start-query \
  --log-group-name "/aws/lambda/naverplace_send_inform" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields phase, duration_ms | stats max(duration_ms) as max_phase_duration by phase | sort max_phase_duration desc'
```

**Step 3: Take Action Based on Bottleneck**

| Bottleneck | Action |
|-----------|--------|
| `authenticate` (>5s) | Check Naver service status, verify credentials, restart session |
| `process_rules` (>3s) | Review rule complexity, check for infinite loops, profile engine |
| `update_database` (>1s) | Check DynamoDB throttling, verify write capacity, check table size |
| `send_summary` (>2s) | Check SENS API status, verify Telegram bot connectivity |

---

### 4.2 Alert Received: High Error Rate

**Step 1: Categorize Errors (2 min)**
```bash
aws logs start-query \
  --log-group-name "/aws/lambda/naverplace_send_inform" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @message, error_code | filter level = "ERROR" | stats count() as error_count by error_code | sort error_count desc'
```

**Step 2: Investigation by Error Type**

| Error Code | Investigation |
|-----------|---|
| `NAVER_AUTH_FAILED` | Check Naver credentials in Secrets Manager, test login manually |
| `DYNAMODB_THROTTLED` | Run `aws dynamodb describe-table --table-name sms` check `ProvisionedThroughput` |
| `SMS_SERVICE_ERROR` | Check SENS API status page, verify service credentials |
| `TIMEOUT` | Review recent code changes, check for new slow queries |

---

### 4.3 Alert Received: High Memory Usage

**Step 1: Check Current Memory (1 min)**
```bash
aws lambda get-function-concurrency --function-name naverplace_send_inform
```

**Step 2: Optimize or Increase Allocation**

**Option A: Optimize (preferred)**
- Check for memory leaks in `src/` modules
- Profile with: `python -m memory_profiler src/main.py`

**Option B: Increase Allocation (temporary)**
```bash
aws lambda update-function-configuration \
  --function-name naverplace_send_inform \
  --memory-size 1024  # Increase from current (typically 512)
```

**Option C: Restart Lambda**
```bash
# Update function code to trigger restart and clear memory
aws lambda update-function-code \
  --function-name naverplace_send_inform \
  --image-uri <current-image-uri>
```

---

## 5. Performance Regression Testing

### 5.1 Before Deployment

**Run performance baseline locally:**
```bash
make test-performance
```

**Expected Output:**
```
Execution Duration Stats: {
  "min_ms": 1200,
  "max_ms": 8900,
  "avg_ms": 4500,
  "p95_ms": 7200,
  "p99_ms": 8500,
  "threshold_ms": 240000,
  "compliant": true
}
```

**If compliant: ✅ Safe to deploy**
**If not compliant: 🔴 Do NOT deploy, fix performance issues**

### 5.2 Post-Deployment Verification

**Wait 10 minutes after Lambda update, then run:**
```bash
# Check Lambda performance in production
aws logs start-query \
  --log-group-name "/aws/lambda/naverplace_send_inform" \
  --start-time $(date -d '15 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields duration_ms | filter ispresent(duration_ms) | stats avg(duration_ms) as avg, max(duration_ms) as max, pct(duration_ms, 95) as p95'
```

**Verification Checklist:**
- [ ] No errors in logs
- [ ] Execution duration ≤ 4 minutes
- [ ] Memory < 400 MB
- [ ] All bookings processed (no skips)

---

## 6. Automated Performance Validation

### 6.1 CI/CD Integration

Performance tests run automatically on each commit:

```bash
# GitHub Actions workflow (.github/workflows/test.yml)
- name: Run Performance Tests
  run: make test-performance
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

### 6.2 Pre-Release Performance Gate

**Story 4.5 Acceptance Criteria (AC5):**
```bash
# Before marking "Ready for Release":
pytest tests/performance/ -v -m "performance"

# Must pass:
# ✅ test_baseline_execution_duration
# ✅ test_baseline_memory_usage
# ✅ test_load_harness_100_bookings
# ✅ test_cold_start_simulation
# ✅ test_dynamodb_optimization_verification
```

---

## 7. Key Contacts & Escalation

### On-Call Escalation
1. **🟡 Yellow Alert (Duration 120-180s):** Review logs, no action needed
2. **🔴 Red Alert (Duration > 180s):** Investigate root cause, may require optimization
3. **🔴🔴 Critical (Duration > 240s):** Immediate action, potential production impact

### Contacts
- **Naver Integration Issues:** Dev Team (@dev-team)
- **DynamoDB/AWS Issues:** DevOps (@devops-team)
- **SMS Service Issues:** Vendor Support (SENS support@sensapi.com)
- **Telegram Bot Issues:** Dev Team (@dev-team)

---

## 8. Performance Tuning Reference

### Cold-Start Optimization
**File:** `src/auth/session_manager.py`
- Ensure Selenium driver is lazily initialized (only when needed)
- Use connection pooling for DynamoDB
- Cache Naver session tokens

### DynamoDB Optimization
**File:** `src/database/dynamodb_client.py`
- Avoid full table scans (use Query with GSI)
- Batch operations with `batch_write_item`
- Monitor and optimize query patterns

### Rule Engine Optimization
**File:** `src/rules/engine.py`
- Profile rule conditions (avoid complex regex in loops)
- Cache rule evaluation results
- Consider lazy rule loading

---

## 9. Appendix: Query Templates

### Template: Custom Duration Threshold
```
fields @timestamp, duration_ms, booking_id
| filter duration_ms > THRESHOLD_MS_HERE
| stats count() as violations, avg(duration_ms) as avg_violation_duration
```

### Template: Specific Booking Performance
```
fields @timestamp, phase, duration_ms
| filter booking_id = "BOOKING_ID_HERE"
| stats max(duration_ms) as total_duration, sum(duration_ms) as sum_phases by booking_id
```

### Template: Error Drill-Down
```
fields @timestamp, @message, error_code, booking_id
| filter level = "ERROR" and error_code = "ERROR_CODE_HERE"
| limit 20
```

---

**Last Updated:** 2025-10-20  
**Next Review:** 2025-11-20  
**Owner:** James (Dev Agent) / Operations Team
