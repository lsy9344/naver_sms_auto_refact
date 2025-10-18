# Epic 1: Infrastructure Setup

**Epic ID:** EPIC-1
**Status:** Draft
**Duration:** Week 1 (5 days)
**Dependencies:** None
**Risk Level:** Low

---

## Epic Overview

Set up the foundational AWS infrastructure required for the refactored system. This epic focuses on creating AWS resources (ECR, Secrets Manager, CloudWatch) and migrating credentials from source code to secure storage. This is a prerequisite for all subsequent development work.

**Why This Epic:** Cannot deploy containerized Lambda or secure credentials without proper infrastructure in place.

---

## Epic Goals

1. ✅ Create ECR repository for container images
2. ✅ Set up AWS Secrets Manager for all credentials
3. ✅ Migrate all hardcoded credentials to Secrets Manager
4. ✅ Set up CloudWatch Log Groups and basic dashboards
5. ✅ Establish Infrastructure as Code (IaC) for reproducibility
6. ✅ Validate infrastructure with smoke tests

---

## Success Criteria

- [ ] ECR repository accessible and ready for image pushes
- [ ] All credentials moved to Secrets Manager (zero in code)
- [ ] CloudWatch dashboards displaying basic metrics
- [ ] IaC templates (Terraform/CloudFormation) created and tested
- [ ] Smoke tests confirm infrastructure accessibility
- [ ] Documentation updated with infrastructure details

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status |
|----------|-------|----------|--------|--------|
| 1.1 | Create ECR Repository | P0 | 0.5d | Draft |
| 1.2 | Setup Secrets Manager | P0 | 1d | Draft |
| 1.3 | Migrate Credentials to Secrets Manager | P0 | 1d | Draft |
| 1.4 | Setup CloudWatch Logging & Dashboards | P0 | 1.5d | Draft |
| 1.5 | Create Infrastructure as Code (IaC) | P1 | 1d | ✅ Ready for Development |

**Total Estimated Effort:** 5 days

---

## Technical Context

### Current State Issues
- Python 3.7 Lambda using Lambda Layers (chromedriver + selenium)
- Credentials hardcoded in source code (security risk):
  - Naver login: `lambda_function.py:250-251`
  - SENS API keys: `sens_sms.py:63-64`
  - Telegram bot token: `lambda_function.py:439`
- No centralized monitoring dashboards
- Manual AWS resource management

### Target State
- ECR-based Lambda container (Python 3.11+)
- All credentials in AWS Secrets Manager
- CloudWatch dashboards for monitoring
- Infrastructure as Code for reliable deployment

### References
- Architecture Doc: Lines 1410-1417 (Phase 1: Infrastructure Setup)
- Architecture Doc: Lines 686-710 (Hardcoded Credentials)
- PRD: Section 4.1 FR6 (Secrets Management)

---

## Epic Dependencies

### Upstream Dependencies
- None (this is the first epic)

### Downstream Dependencies
- **Epic 2 (Code Extraction):** Requires Secrets Manager for config loader
- **Epic 4 (Integration & Testing):** Requires ECR for container deployment
- **Epic 5 (Deployment):** Requires all infrastructure components

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AWS permissions issues | Medium | High | Validate IAM permissions before starting |
| Secrets Manager costs | Low | Low | <$5/month for ~10 secrets |
| ECR storage costs | Low | Low | <$1/month for container images |
| IaC complexity | Medium | Medium | Start with simple CloudFormation/Terraform |

---

## Acceptance Criteria (Epic Level)

1. ECR repository created in `ap-northeast-2` region
2. Secrets stored in Secrets Manager:
   - `naver-sms-automation/naver-credentials`
   - `naver-sms-automation/sens-credentials`
   - `naver-sms-automation/telegram-credentials`
3. CloudWatch Log Group: `/aws/lambda/naver-sms-automation`
4. CloudWatch Dashboard: `naver-sms-automation-dashboard`
5. IaC template can recreate all resources from scratch
6. Zero credentials remaining in source code

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-18 | 1.0 | Epic created from PRD and architecture doc | Sarah (PO) |
| 2025-10-19 | 1.1 | Updated CloudWatch Log Group name to `/aws/lambda/naver-sms-automation` (aligns with refactored project naming convention, updated during Story 1.4 validation) | Sarah (PO) |
| 2025-10-19 | 1.2 | Story 1.5 validation complete: tool choice locked to Terraform, AC tightened, critical gaps resolved, dev notes enriched with provider versions and IAM details, 4-phase task structure established, story promoted to Ready for Development | Sarah (PO) |
