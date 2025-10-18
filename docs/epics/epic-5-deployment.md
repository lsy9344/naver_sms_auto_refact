# Epic 5: Deployment & Production Cutover

**Epic ID:** EPIC-5
**Status:** Draft
**Duration:** Weeks 4-5 (10 days)
**Dependencies:** Epic 4 (Integration & Testing)
**Risk Level:** Critical (production deployment)

---

## Epic Overview

Deploy the containerized Lambda to production using a parallel deployment strategy, validate outputs for 1 week, then perform zero-downtime cutover. This epic includes rollback planning, monitoring setup, and validation procedures to ensure safe production deployment.

**Why This Epic:** Brownfield deployment to production requires extreme caution. Parallel deployment minimizes risk while allowing comprehensive validation.

---

## Epic Goals

1. ✅ Deploy container to ECR
2. ✅ Create new Lambda function (separate from old)
3. ✅ Run parallel deployment for 1 week (old + new Lambda)
4. ✅ Compare outputs continuously (zero discrepancies required)
5. ✅ Perform zero-downtime cutover to new Lambda
6. ✅ Monitor for 1 week post-cutover
7. ✅ Decommission old Lambda

---

## Success Criteria

- [ ] Container image pushed to ECR successfully
- [ ] New Lambda function created and configured
- [ ] Parallel deployment runs for 7 days
- [ ] Comparison monitoring shows 100% match
- [ ] Cutover completes without customer disruption
- [ ] Post-cutover monitoring shows zero incidents
- [ ] Old Lambda decommissioned safely

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status |
|----------|-------|----------|--------|--------|
| 5.1 | Deploy to ECR | P0 | 0.5d | Draft |
| 5.2 | Create New Lambda Function | P0 | 1d | Draft |
| 5.3 | Setup Parallel Deployment | P0 | 1d | Draft |
| 5.4 | Implement Comparison Monitoring | P0 | 1.5d | Draft |
| 5.5 | Run 1-Week Parallel Validation | P0 | 5d | Draft |
| 5.6 | Perform Production Cutover | P0 | 0.5d | Draft |
| 5.7 | Post-Cutover Monitoring | P0 | 0.5d | Draft |

**Total Estimated Effort:** 10 days (includes 5-day waiting period)

---

## Technical Context

### Parallel Deployment Architecture

```
EventBridge (every 20 minutes)
    │
    ├──────────────┬──────────────┐
    │              │              │
    ▼              ▼              ▼
Old Lambda    New Lambda    Comparison
(existing)    (new)         Script
    │              │              │
    │              │              │
    ▼              ▼              ▼
DynamoDB      DynamoDB      CloudWatch
(sms table)   (sms_v2?)     Metrics
    │              │
    └──────┬───────┘
           ▼
    Comparison
    Dashboard
```

**Strategy:**
1. Both Lambdas run every 20 minutes (separate EventBridge rules)
2. Both read same Naver Booking API
3. Both write to separate DynamoDB tables (sms vs sms_v2) OR same table with version tagging
4. Comparison script compares outputs every execution
5. After 1 week of 100% match → cutover
6. Cutover: disable old Lambda's EventBridge rule, enable new Lambda's rule
7. Monitor for 1 week
8. Decommission old Lambda

### Deployment Steps

**1. ECR Deployment:**
```bash
# Tag image
docker tag naver-sms-automation:latest \
  654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest

# Push to ECR
docker push 654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest
```

**2. Lambda Function Creation:**
```bash
aws lambda create-function \
  --function-name naverplace_send_inform_v2 \
  --package-type Image \
  --code ImageUri=654654307503.dkr.ecr.ap-northeast-2.amazonaws.com/naver-sms-automation:latest \
  --role arn:aws:iam::654654307503:role/lambda-execution-role \
  --timeout 300 \
  --memory-size 512 \
  --region ap-northeast-2
```

**3. EventBridge Rule (Disabled Initially):**
```bash
aws events put-rule \
  --name naver-sms-automation-v2-trigger \
  --schedule-expression "rate(20 minutes)" \
  --state DISABLED \
  --region ap-northeast-2

aws events put-targets \
  --rule naver-sms-automation-v2-trigger \
  --targets "Id"="1","Arn"="arn:aws:lambda:ap-northeast-2:654654307503:function:naverplace_send_inform_v2"
```

### Comparison Monitoring

**Metrics to Compare:**
- Number of SMS sent (by type: confirmation, guide, event)
- SMS content (character-by-character)
- DynamoDB records created
- DynamoDB records updated
- Telegram notifications sent

**CloudWatch Custom Metrics:**
- `naver-sms/comparison/discrepancies` (should be 0)
- `naver-sms/comparison/sms_sent_old`
- `naver-sms/comparison/sms_sent_new`
- `naver-sms/comparison/match_percentage` (should be 100%)

**Alerting:**
- Alert if discrepancies > 0
- Alert if match_percentage < 100%
- Alert if error rate > 1%

### Rollback Procedures

**Scenario 1: Discrepancies Detected During Parallel Deployment**
- Action: Keep old Lambda running, fix new Lambda
- Timeline: No customer impact (old Lambda still serving)

**Scenario 2: Issues After Cutover**
- Action:
  1. Disable new Lambda EventBridge rule
  2. Enable old Lambda EventBridge rule
  3. Verify old Lambda working
  4. Investigate new Lambda issues
- Timeline: <5 minutes to rollback

**Scenario 3: Database Issues**
- Action:
  1. Rollback Lambda (as above)
  2. Restore DynamoDB from backup if needed
  3. Replay missed bookings manually
- Timeline: <15 minutes

### References
- Architecture Doc: Lines 1439-1446 (Phase 5: Deployment)
- Architecture Doc: Lines 1440-1446 (Parallel Deployment Strategy)
- Architecture Doc: Lines 1683-1713 (Comparison Testing)
- PRD: Section 5.1 MSC1 (Functional Parity)
- PRD: Section 7.1 BC1 (Zero Downtime Requirement)

---

## Epic Dependencies

### Upstream Dependencies
- **Epic 4:** Tested Docker container
- **Epic 1:** ECR repository

### Downstream Dependencies
- **Epic 6 (Enhancements):** Can only start after successful cutover

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Discrepancies found | Medium | High | Fix before cutover, keep old Lambda running |
| Cutover causes downtime | Low | Critical | EventBridge rule switching is instant |
| Rollback needed | Low | High | Documented procedures, tested rollback |
| Database corruption | Very Low | Critical | Separate tables during parallel, backups |
| Monitoring gaps | Medium | Medium | Comprehensive metrics, alarms |
| Cost overrun (2 Lambdas) | Low | Low | ~$10 extra for 1 week, acceptable |

---

## Acceptance Criteria (Epic Level)

1. **ECR Deployment:**
   - Container image in ECR with tag `latest` and `v1.0.0`
   - Image size <10GB
   - Image scans show no critical vulnerabilities

2. **New Lambda Function:**
   - Function name: `naverplace_send_inform_v2`
   - Runtime: Container (Python 3.11)
   - Memory: 512MB
   - Timeout: 5 minutes
   - IAM role: Permissions for DynamoDB, Secrets Manager, CloudWatch
   - Environment variables: None (use Secrets Manager)

3. **Parallel Deployment:**
   - Both Lambdas triggered every 20 minutes
   - Both process same bookings
   - Both write to separate tracking (DynamoDB tables or version tags)
   - Comparison script runs after each execution

4. **Comparison Monitoring:**
   - CloudWatch dashboard shows comparison metrics
   - Alarms configured for discrepancies
   - Slack/Telegram notifications for alerts
   - Logs include comparison results

5. **1-Week Validation:**
   - 7 days × 24 hours × 3 executions/hour = ~504 executions
   - 100% match rate required (zero discrepancies)
   - No errors or timeouts
   - Performance within NFRs

6. **Production Cutover:**
   - Disable old Lambda EventBridge rule
   - Enable new Lambda EventBridge rule
   - Verify first execution successful
   - No customer SMS disruption
   - Zero downtime

7. **Post-Cutover Monitoring:**
   - 1 week zero production incidents
   - Error rate <1%
   - Performance within NFRs
   - Customer feedback: zero complaints

8. **Decommission Old Lambda:**
   - Archive old Lambda function (don't delete)
   - Disable but keep for 30 days
   - Document rollback to old Lambda if needed
   - Clean up old Lambda Layers

---

## Go/No-Go Decision Points

**Decision Point 1: Enable Parallel Deployment (Day 0)**
- ✅ Container deployed to ECR
- ✅ New Lambda function created
- ✅ Comparison monitoring ready
- ✅ Rollback procedures documented
- **Go/No-Go:** Enable both Lambdas if all green

**Decision Point 2: Proceed to Cutover (Day 7)**
- ✅ 100% match rate for 7 days
- ✅ Zero discrepancies
- ✅ No errors or timeouts
- ✅ Performance acceptable
- **Go/No-Go:** Cutover if validation passes

**Decision Point 3: Decommission Old Lambda (Day 14)**
- ✅ 1 week post-cutover with zero incidents
- ✅ New Lambda stable
- ✅ Team comfortable with new system
- **Go/No-Go:** Archive old Lambda if stable

---

## Monitoring & Alerting Plan

**CloudWatch Alarms:**
1. **Comparison Discrepancies Alarm**
   - Metric: `naver-sms/comparison/discrepancies`
   - Threshold: > 0
   - Action: Slack + Telegram + Email

2. **New Lambda Error Rate Alarm**
   - Metric: `AWS/Lambda/Errors`
   - Threshold: > 5% of invocations
   - Action: Slack + Telegram

3. **New Lambda Duration Alarm**
   - Metric: `AWS/Lambda/Duration`
   - Threshold: > 240000 ms (4 minutes)
   - Action: Slack

4. **Match Percentage Alarm**
   - Metric: `naver-sms/comparison/match_percentage`
   - Threshold: < 100%
   - Action: Slack + Telegram + Email

**CloudWatch Dashboard:**
- Comparison metrics (old vs new)
- Lambda invocations, errors, duration
- DynamoDB read/write capacity
- SENS API call counts
- SMS sent (by type, by store)

---

## Rollback Testing

**Pre-Deployment:**
- Test rollback procedure in test environment
- Verify EventBridge rule switching works instantly
- Confirm DynamoDB state after rollback
- Practice rollback communication

**Rollback SLA:**
- Detection: <5 minutes (monitoring alerts)
- Decision: <5 minutes (PO approval)
- Execution: <5 minutes (disable/enable EventBridge)
- **Total: <15 minutes from issue to rollback complete**

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-18 | 1.0 | Epic created from PRD and architecture doc | Sarah (PO) |
