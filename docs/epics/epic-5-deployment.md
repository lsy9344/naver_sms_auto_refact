# Epic 5: Deployment & Production Cutover

**Epic ID:** EPIC-5
**Status:** Draft
**Duration:** Weeks 4-5 (10 days)
**Dependencies:** Epic 4 (Integration & Testing)
**Risk Level:** Critical (production deployment)

---

## Epic Overview

Deploy the containerized Lambda to production after comprehensive offline validation using golden datasets and comparison testing artifacts. The legacy Lambda is no longer operational, so validation relies on captured test data, regression suites, and monitoring readiness checks before production cutover.

**Why This Epic:** Brownfield deployment to production requires extreme caution. Offline validation against golden datasets and comprehensive testing ensures functional parity before cutover.

---

## Epic Goals

1. ✅ Deploy container to ECR
2. ✅ Create new Lambda function
3. ✅ Execute comprehensive offline validation using golden datasets and regression suites
4. ✅ Verify monitoring and alerting infrastructure readiness
5. ✅ Perform production cutover after validation sign-off
6. ✅ Monitor for 1 week post-cutover
7. ✅ Archive legacy artifacts and document migration completion

---

## Success Criteria

- [ ] Container image pushed to ECR successfully
- [ ] New Lambda function created and configured
- [ ] Offline validation campaign shows 100% parity with golden datasets
- [ ] Monitoring and alerting infrastructure verified and ready
- [ ] Cutover completes without customer disruption
- [ ] Post-cutover monitoring shows zero incidents for 1 week
- [ ] Migration documentation complete and legacy artifacts archived

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status |
|----------|-------|----------|--------|--------|
| 5.1 | Deploy to ECR | P0 | 0.5d | Draft |
| 5.2 | Create New Lambda Function | P0 | 1d | Draft |
| ~~5.3~~ | ~~Setup Parallel Deployment~~ | ~~P0~~ | ~~1d~~ | **REMOVED** (no legacy Lambda) |
| 5.4 | Implement Monitoring Infrastructure | P0 | 1d | Draft |
| 5.5 | Validate New Lambda Readiness | P0 | 2d | Draft |
| 5.6 | Perform Production Cutover | P0 | 0.5d | Draft |
| 5.7 | Post-Cutover Monitoring | P0 | 1d | Draft |

**Total Estimated Effort:** 6 days

**Note:** Story 5.3 removed as legacy Lambda is no longer operational; parallel deployment strategy not applicable.

---

## Technical Context

### Validation-Only Deployment Architecture

```
Offline Validation Phase:
┌─────────────────────────────────────────┐
│ Golden Datasets (from Epic 4)           │
│ - Captured booking scenarios           │
│ - Expected outputs (SMS, DB, Telegram) │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │   New Lambda       │
         │   (Test Mode)      │
         └────────┬───────────┘
                  │
                  ▼
         ┌────────────────────┐
         │  Diff Reporter     │
         │  Comparison Tool   │
         └────────┬───────────┘
                  │
                  ▼
         ┌────────────────────┐
         │ Validation Report  │
         │ (100% parity req.) │
         └────────────────────┘

Production Cutover:
EventBridge (every 20 minutes)
    │
    ▼
New Lambda (Container-based)
    │
    ├─────────┬──────────┬──────────┐
    │         │          │          │
    ▼         ▼          ▼          ▼
DynamoDB   SENS SMS   Telegram  CloudWatch
```

**Strategy:**
1. Execute offline validation using golden datasets captured during Epic 4
2. Run regression test suite against new Lambda
3. Use diff reporter to verify 100% parity with expected outputs
4. Verify monitoring infrastructure (CloudWatch, alarms, dashboards)
5. Obtain go/no-go approval based on validation evidence
6. Cutover: Enable EventBridge rule for new Lambda
7. Monitor production for 1 week
8. Archive legacy artifacts after successful validation period

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

**3. EventBridge Rule (Production Trigger):**
```bash
# Create EventBridge rule (disabled until validation complete)
aws events put-rule \
  --name naver-sms-automation-trigger \
  --schedule-expression "rate(20 minutes)" \
  --state DISABLED \
  --region ap-northeast-2

aws events put-targets \
  --rule naver-sms-automation-trigger \
  --targets "Id"="1","Arn"="arn:aws:lambda:ap-northeast-2:654654307503:function:naverplace_send_inform_v2"
```

**4. Offline Validation:**
```bash
# Run validation suite using golden datasets
pytest tests/comparison/test_output_parity.py -v

# Generate validation report
python scripts/generate_validation_report.py
```

### Monitoring Infrastructure

**CloudWatch Metrics to Monitor:**
- Lambda invocations, errors, duration
- DynamoDB read/write capacity
- SENS API call counts
- SMS sent (by type, by store)
- Telegram notification success rate

**CloudWatch Alarms:**
- Lambda error rate > 5%
- Lambda duration > 4 minutes
- DynamoDB throttling events
- SENS API failures

**Alerting Channels:**
- Telegram for critical alerts
- CloudWatch Logs for detailed diagnostics

### Rollback Procedures

**IMPORTANT:** Legacy Lambda is no longer operational. Rollback strategy relies on rapid issue detection and Lambda code reversion.

**Scenario 1: Critical Issues Detected Post-Cutover**
- Action:
  1. Disable new Lambda EventBridge rule (stop all automated processing)
  2. Assess issue severity and impact
  3. If code defect: Deploy previous working container image version
  4. If infrastructure issue: Fix infrastructure and re-enable
- Timeline: <15 minutes to stop automation, <1 hour to deploy fix

**Scenario 2: Database Corruption**
- Action:
  1. Disable Lambda EventBridge rule immediately
  2. Restore DynamoDB from point-in-time backup
  3. Manually process missed bookings using runbook procedures
  4. Verify data integrity before re-enabling
- Timeline: <30 minutes

**Scenario 3: Partial Failure (e.g., SMS sending issues)**
- Action:
  1. Keep Lambda running if non-critical
  2. Monitor error rates and customer impact
  3. Apply hotfix if possible
  4. Disable if customer impact exceeds threshold
- Timeline: Monitoring-based decision within 1 hour

**Mitigation:** Comprehensive offline validation (Story 5.5) minimizes rollback probability

### References
- Architecture Doc: Lines 1439-1446 (Phase 5: Deployment)
- Architecture Doc: Lines 1683-1713 (Comparison Testing Strategy)
- PRD: Section 5.1 MSC1 (Functional Parity)
- Epic 4: Integration & Testing (golden dataset creation)
- Story 4.4: Integration Testing (test artifacts and comparison tooling)

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
| Undiscovered edge cases | Medium | High | Comprehensive offline validation with diverse golden datasets |
| Cutover causes downtime | Low | Critical | EventBridge rule switching is instant, monitoring in place |
| Rollback needed post-cutover | Medium | High | Container versioning, rapid redeployment procedures, DynamoDB backups |
| Monitoring gaps | Medium | Medium | Pre-validate all CloudWatch alarms and dashboards (Story 5.4) |
| Golden datasets incomplete | Medium | High | Epic 4 coverage review, ensure representative scenarios captured |
| Production environment differences | Low | Medium | Test in staging environment mirroring production config |

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

3. **Offline Validation Campaign:**
   - Automated regression suite executes successfully with 100% pass rate
   - Comparison testing against golden datasets shows 100% parity
   - All edge cases and error scenarios validated
   - Validation evidence documented in VALIDATION.md

4. **Monitoring Infrastructure:**
   - CloudWatch dashboard configured with Lambda, DynamoDB, SENS metrics
   - Alarms configured for error rate, duration, throttling
   - Telegram notifications verified and working
   - Logs structured and queryable

5. **Validation Sign-Off:**
   - PO/stakeholder review of validation evidence complete
   - Go/no-go decision documented
   - Readiness report confirms MSC1 functional parity criteria satisfied
   - Rollback procedures tested and documented

6. **Production Cutover:**
   - EventBridge rule enabled for new Lambda
   - First execution successful with no errors
   - No customer SMS disruption
   - Zero downtime

7. **Post-Cutover Monitoring:**
   - 1 week zero critical production incidents
   - Error rate <1%
   - Performance within NFRs (execution time, throughput)
   - Customer feedback: zero complaints

8. **Migration Completion:**
   - Legacy artifacts archived and documented
   - Migration runbook updated with lessons learned
   - Team trained on new system operations
   - Documentation complete (operational runbooks, troubleshooting guides)

---

## Go/No-Go Decision Points

**Decision Point 1: Begin Offline Validation (After Epic 4 Complete)**
- ✅ Container deployed to ECR
- ✅ New Lambda function created
- ✅ Golden datasets available from Epic 4
- ✅ Comparison tooling ready
- **Go/No-Go:** Start validation campaign if infrastructure ready

**Decision Point 2: Proceed to Production Cutover (After Validation Complete)**
- ✅ Offline validation shows 100% parity
- ✅ Zero critical discrepancies in validation report
- ✅ Monitoring infrastructure verified
- ✅ Stakeholder approval obtained
- ✅ Rollback procedures documented and tested
- **Go/No-Go:** Enable production EventBridge rule if validation evidence satisfactory

**Decision Point 3: Declare Migration Complete (7 days post-cutover)**
- ✅ 1 week post-cutover with zero critical incidents
- ✅ New Lambda stable (error rate <1%)
- ✅ Team trained and comfortable with operations
- ✅ Documentation complete
- **Go/No-Go:** Archive legacy artifacts and close Epic 5

---

## Monitoring & Alerting Plan

**CloudWatch Alarms (Production):**
1. **Lambda Error Rate Alarm**
   - Metric: `AWS/Lambda/Errors`
   - Threshold: > 5% of invocations
   - Action: Telegram notification

2. **Lambda Duration Alarm**
   - Metric: `AWS/Lambda/Duration`
   - Threshold: > 240000 ms (4 minutes)
   - Action: Telegram notification

3. **Lambda Throttling Alarm**
   - Metric: `AWS/Lambda/Throttles`
   - Threshold: > 0
   - Action: Telegram notification

4. **DynamoDB Throttling Alarm**
   - Metric: `AWS/DynamoDB/UserErrors`
   - Threshold: > 5
   - Action: Telegram notification

**CloudWatch Dashboard:**
- Lambda invocations, errors, duration, concurrent executions
- DynamoDB read/write capacity utilization
- SENS API call counts (via custom metrics)
- SMS sent by type and store (via custom metrics)
- Telegram notification success rate

---

## Rollback Testing

**Pre-Deployment Validation:**
- Test EventBridge rule disable procedure
- Verify container redeployment from previous ECR image
- Test DynamoDB point-in-time recovery procedure
- Practice rollback communication and escalation

**Rollback SLA (Post-Cutover):**
- Detection: <10 minutes (monitoring alerts + manual observation)
- Decision: <10 minutes (PO approval)
- Execution: <15 minutes (disable EventBridge + assess/fix or redeploy)
- **Total: <35 minutes from issue detection to resolution**

**Note:** Without legacy Lambda fallback, rollback means:
1. Stop automation (disable EventBridge)
2. Deploy previous working container version, OR
3. Apply emergency hotfix to current version

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-18 | 1.0 | Epic created from PRD and architecture doc | Sarah (PO) |
| 2025-10-20 | 2.0 | Updated to validation-only strategy; legacy Lambda non-operational, removed parallel deployment (Story 5.3), updated rollback procedures | Sarah (PO) |
