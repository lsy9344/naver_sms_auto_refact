# Product Requirements Document (PRD)
## Naver SMS Automation - Brownfield Refactoring & Rule Engine Enhancement

**Version:** 1.0
**Status:** Draft
**Created:** 2025-10-18
**Owner:** Product Owner (Sarah)
**Project Type:** Brownfield Enhancement

---

## Executive Summary

This PRD outlines the refactoring and enhancement of the existing Naver SMS Automation system, transitioning from a monolithic AWS Lambda with hardcoded business rules to a flexible, rule-based architecture. The project addresses critical technical debt (Python 3.7 deprecation, Lambda Layer limitations) while enabling business users to easily configure SMS automation rules without code changes.

**Key Outcomes:**
- ✅ Flexible rule engine for condition/action composition
- ✅ Python 3.11+ runtime via ECR container deployment
- ✅ 100% preservation of existing functionality
- ✅ Reduced deployment complexity and improved maintainability

---

## 1. Problem Statement

### Current Pain Points

#### 1.1 Technical Debt (Critical)

**Python 3.7 Runtime Deprecated**
- AWS warning active: "The python3.7 runtime is no longer supported"
- Security updates no longer provided
- Forced migration timeline approaching

**Lambda Layer Management Complexity**
- ChromeDriver layer: 2GB+ size
- Selenium layer: ~50MB
- Difficult to update versions
- Slow cold starts (~3-5 seconds)

**Hardcoded Credentials**
- Naver login credentials in source code (lines 250-251)
- SENS API keys in source code (sens_sms.py:63-64)
- Telegram tokens exposed in version control
- Security risk and compliance violation

#### 1.2 Business Logic Inflexibility (High Priority)

**Cannot Add/Modify Rules Without Code Deployment**
- All conditions hardcoded in if/else statements (12 condition patterns identified)
- All actions hardcoded (9 action patterns identified)
- Store-specific logic scattered across files
- Adding new rule requires developer, code review, deployment

**Example Current Limitations:**
- Cannot send SMS to specific store customers with option A
- Cannot create date-range-based rules without code changes
- Cannot combine conditions flexibly (e.g., "store X AND option Y AND date range Z")
- Cannot send results to Slack without code modification

#### 1.3 Maintainability Issues

**Monolithic Code Structure**
- lambda_function.py: 449 lines containing all logic
- sens_sms.py: 619 lines with hardcoded templates
- No separation of concerns
- High coupling between components
- Difficult to test (0% test coverage)

---

## 2. Business Goals

### 2.1 Primary Goals

**G1: Enable Self-Service Rule Configuration**
- Business users can add/modify SMS automation rules via configuration files
- No developer involvement required for rule changes
- Rules can combine conditions and actions flexibly

**G2: Eliminate Technical Debt**
- Upgrade to Python 3.11+ (latest AWS Lambda supported runtime)
- Migrate from Lambda Layers to ECR container deployment
- Move credentials to AWS Secrets Manager
- Resolve all AWS deprecation warnings

**G3: Preserve 100% of Existing Functionality**
- All current SMS sent at same times with same content
- All integrations work identically (Naver, SENS, DynamoDB, Telegram)
- Zero customer disruption during migration
- Identical behavior validated through comparison testing

### 2.2 Secondary Goals

**G4: Improve System Maintainability**
- Modular code structure with clear separation of concerns
- >80% test coverage
- Comprehensive documentation
- Easier onboarding for new developers

**G5: Enable Future Enhancements**
- Data model supports future field expansion (booking data will grow)
- Notification abstraction supports Slack integration
- Rule engine extensible for new condition/action types
- Architecture supports additional stores without code changes

---

## 3. User Stories

### 3.1 Business User Stories

**US1: As a business operations manager, I want to create SMS rules via configuration files so that I can respond quickly to business needs without waiting for developer availability.**

Acceptance Criteria:
- Can add new rule to rules.yaml
- Can specify conditions (store, option, time window, etc.)
- Can specify actions (send SMS, update DB, notify Slack)
- Changes take effect on next Lambda execution (within 20 minutes)

**US2: As a store owner, I want to send targeted SMS to customers who selected specific options so that I can promote relevant services.**

Example: "Send Instagram guide SMS to customers at store 1051707 who selected '인스타' option"

Acceptance Criteria:
- Can filter by store ID
- Can filter by option keywords
- Can specify custom SMS template
- SMS sent within configured time window

**US3: As a marketing manager, I want to analyze SMS sending patterns so that I can optimize customer communication.**

Acceptance Criteria:
- CloudWatch dashboard shows SMS sent by type, store, time
- Can export data for analysis
- Monitoring alerts on anomalies

### 3.2 Developer/System Stories

**US4: As a developer, I want modular code structure so that I can maintain and extend the system easily.**

Acceptance Criteria:
- Clear module boundaries (auth, api, rules, notifications, database)
- Each module has unit tests (>80% coverage)
- Integration tests validate cross-module behavior
- Documentation explains module responsibilities

**US5: As a DevOps engineer, I want Infrastructure as Code so that I can deploy reliably and rollback safely.**

Acceptance Criteria:
- Terraform/CloudFormation templates for all AWS resources
- CI/CD pipeline automates deployment
- Rollback procedures documented per component
- Blue-green deployment capability

**US6: As a system administrator, I want comprehensive monitoring so that I can detect and resolve issues quickly.**

Acceptance Criteria:
- CloudWatch alarms for error rates, timeouts, throttling
- Structured logging for troubleshooting
- Dashboard with key metrics
- Telegram/Slack notifications for critical errors

---

## 4. Technical Requirements

### 4.1 Functional Requirements

**FR1: Rule Engine**
- Support condition composition (AND/OR logic)
- Support action chaining (multiple actions per rule)
- Load rules from YAML configuration
- Validate rules on startup
- Execute rules against booking data every 20 minutes

**FR2: Condition Types (Minimum)**

Must support these condition evaluators:
- `booking_not_in_db` - New booking detection
- `time_before_booking(hours)` - Time window checks
- `flag_not_set(flag_name)` - DB flag checks
- `current_hour(hour)` - Time-of-day checks
- `booking_status(status)` - Status code checks
- `has_option_keyword(keywords)` - Option detection
- `store_id_matches(store_ids)` - Store filtering
- `date_range(start, end)` - Date filtering (NEW)

**FR3: Action Types (Minimum)**

Must support these action executors:
- `send_sms(template, store_specific)` - SMS via SENS API
- `create_db_record()` - DynamoDB insert
- `update_flag(flag_name)` - DynamoDB update
- `send_telegram(message)` - Telegram notification
- `send_slack(message)` - Slack notification (NEW)
- `log_event(message)` - CloudWatch structured logging

**FR4: Preservation Requirements (CRITICAL)**

Must preserve 100% exactly:
- Naver login mechanism (Selenium + cookie caching)
- Naver Booking API integration (headers, authentication)
- SENS SMS API integration (signature generation, request format)
- SMS template content (all 10 templates character-for-character)
- Store-to-phone number mappings
- DynamoDB table schemas
- EventBridge 20-minute trigger interval
- Telegram notification integration

**FR5: Configuration Management**

- Move all hardcoded values to configuration:
  - Store list → stores.yaml
  - SMS templates → sms_templates.yaml
  - Rule definitions → rules.yaml
  - Option keywords → rules.yaml or stores.yaml
- Load configuration from files (not database for MVP)
- Validate configuration on Lambda startup
- Log configuration errors clearly

**FR6: Secrets Management**

- Move all credentials to AWS Secrets Manager:
  - Naver login (userid, password)
  - SENS API (access_key, secret_key, service_id)
  - Telegram bot (token, chat_id)
  - AWS credentials (if needed)
- No secrets in source code or environment variables
- Secrets cached during Lambda execution for performance

### 4.2 Non-Functional Requirements

**NFR1: Performance**
- Lambda execution time: <4 minutes (current ~2-3 minutes)
- Cold start time: <10 seconds (acceptable for 20-min interval)
- DynamoDB read/write latency: <100ms (current performance)
- SMS sending success rate: >99% (maintained)

**NFR2: Reliability**
- System uptime: 99.9% (3 nines)
- Error rate: <1% of executions
- Zero data loss (all SMS tracked in DynamoDB)
- Automatic retry for transient failures

**NFR3: Scalability**
- Support 8 stores (current) up to 20 stores (future)
- Handle 100+ bookings per execution (current ~10-50)
- Rule engine supports 50+ rules without performance degradation
- Data model supports 15+ booking fields (current 6)

**NFR4: Security**
- All credentials in AWS Secrets Manager
- IAM least-privilege principle
- Secrets rotation supported (not automatic for MVP)
- Audit logging for all configuration changes
- No PII in CloudWatch Logs

**NFR5: Maintainability**
- Code test coverage: >80%
- Documentation: All modules documented
- Configuration examples provided
- Troubleshooting runbook exists
- Code follows Python PEP 8 style

**NFR6: Deployability**
- Minimize downtime via controlled cutover with pre-validated artifacts
- Rollback capability within 5 minutes
- Automated deployment via CI/CD
- Infrastructure as Code (Terraform/CloudFormation)
- Environment parity (local dev matches production)

---

## 5. Success Criteria

### 5.1 Migration Success Criteria

**MSC1: Functional Parity (CRITICAL)**
- ✅ All existing SMS sent correctly (100% match in comparison testing)
- ✅ All DynamoDB updates identical
- ✅ All Telegram notifications identical
- ✅ No customer complaints or missed notifications
- ✅ Offline validation campaign achieves 100% parity with signed go/no-go approval

**MSC2: Technical Debt Elimination**
- ✅ Python 3.11+ runtime in production
- ✅ ECR container deployment working
- ✅ All credentials in Secrets Manager (zero in code)
- ✅ AWS deprecation warnings resolved
- ✅ Lambda Layer dependencies removed

**MSC3: Rule Engine Validation**
- ✅ All existing rules replicated in rules.yaml
- ✅ New rule can be added via YAML without code change
- ✅ Rule validation catches configuration errors
- ✅ Rule execution matches expected behavior in tests

**MSC4: Testing & Quality**
- ✅ >80% code coverage
- ✅ All unit tests passing
- ✅ All integration tests passing
- ✅ Comparison tests validate parity with old system
- ✅ Load testing confirms performance NFRs

**MSC5: Production Readiness**
- ✅ CloudWatch monitoring and alarms operational
- ✅ Rollback procedures documented and tested (cutover rehearsal + rollback drill)
- ✅ Runbook created for incident response
- ✅ Team trained on new system
- ✅ Zero production incidents during migration

### 5.2 Post-MVP Success Criteria

**Post-MSC1: Business Adoption**
- Business users successfully add/modify rules via YAML
- Average time to deploy new rule: <30 minutes (vs. days previously)
- Number of developer escalations: <1 per month

**Post-MSC2: System Health**
- Error rate: <0.5% (improved from baseline)
- Average execution time: <2 minutes (improved)
- Cost: No more than 10% increase (ECR vs. Layers)

---

## 6. MVP Scope Definition

### 6.1 IN SCOPE for MVP

**✅ Infrastructure Migration**
- Python 3.11+ runtime
- ECR container-based Lambda
- Secrets Manager for credentials
- CloudWatch Logs, basic dashboards
- GitHub Actions CI/CD pipeline

**✅ Code Refactoring**
- Modular architecture (auth, api, rules, notifications, database, config)
- Extract Naver login module (preserve 100%)
- Extract SENS SMS module (preserve logic, externalize templates)
- Extract DynamoDB operations
- Configuration loader (YAML files)
- Structured logging

**✅ Rule Engine (Core)**
- Rule engine core (evaluate conditions, execute actions)
- Condition evaluators for all existing patterns (8 types)
- Action executors for all existing actions (6 types)
- YAML-based rule configuration
- Rule validation on startup

**✅ Testing**
- Unit tests for all modules (>80% coverage)
- Integration tests for critical paths
- Comparison testing vs. old system
- Test infrastructure setup (pytest, mocks)

**✅ Deployment**
- Offline validation campaign with golden datasets
- Controlled cutover playbook with rapid rollback path
- Cutover procedure
- Rollback documentation

**✅ Documentation**
- Architecture documentation (already exists - brownfield-architecture.md)
- PRD (this document)
- Epic/Story definitions
- Runbook for common issues
- Configuration examples

### 6.2 OUT OF SCOPE for MVP (Post-MVP)

**❌ Advanced Rule Engine Features**
- UI for rule management (YAML editing sufficient)
- Complex OR logic (only AND for MVP)
- Rule scheduling (all rules evaluate every run)
- Rule dependencies (sequential execution)

**❌ Enhanced Notifications**
- Slack rich formatting (basic text messages only)
- Email notifications
- Push notifications

**❌ Advanced Analytics**
- Custom analytics dashboard
- Historical trend analysis
- Predictive analytics
- A/B testing for SMS templates

**❌ Performance Optimizations**
- Rule engine caching
- Parallel rule execution
- Database query optimization (unless needed)

**❌ Multi-Environment Setup**
- Staging environment (test in production-like setup initially)
- Multi-region deployment (single region sufficient)

**❌ Advanced Security**
- Automatic secrets rotation
- End-to-end encryption
- Advanced IAM policies beyond least-privilege

---

## 7. Constraints & Assumptions

### 7.1 Technical Constraints

**TC1: AWS Lambda Limits**
- Maximum execution time: 15 minutes (using 5 minutes currently)
- Maximum memory: 10GB (using 512MB currently)
- /tmp storage: 10GB (using minimal)
- Deployment package size: 10GB for container images

**TC2: DynamoDB**
- Current table schemas must be preserved (backward compatibility)
- On-demand capacity mode (no provisioned throughput planning needed)
- Single region: ap-northeast-2 (Seoul)

**TC3: SENS SMS API**
- Rate limits: Unknown (need to document from Naver Cloud)
- Message length: LMS max 2000 characters
- Signature algorithm: HMAC-SHA256 (must preserve exactly)

**TC4: Naver Platform**
- Login mechanism sensitive to bot detection (must preserve current approach)
- API endpoints may change (need monitoring/alerting)
- Session cookie TTL: Unknown (re-login on expiry)

### 7.2 Business Constraints

**BC1: Zero Downtime Requirement**
- Cannot stop SMS automation during migration
- Parallel deployment mandatory
- Rollback must be immediate (<5 minutes)

**BC2: Budget**
- No additional AWS costs >10% increase
- ECR storage costs minimal
- Secrets Manager: ~$0.40/secret/month
- Development time: 4-6 weeks

**BC3: Team Availability**
- 1 developer (AI agent)
- 1 product owner (occasional review)
- No dedicated QA team (automated testing)

### 7.3 Assumptions

**A1: Data Model Expansion**
- Booking data fields WILL expand in the future (from 6 to 10-15+ fields)
- New fields will be provided by business team
- Rule engine must support arbitrary field access

**A2: Naver Platform Stability**
- Login mechanism will remain compatible
- Booking API endpoints will remain stable (or minor changes)
- Cookie-based authentication will continue working

**A3: SMS Template Stability**
- Current SMS templates will not change during migration
- Template content is owned by business team
- Future template changes via configuration only

**A4: Store List Growth**
- Current 8 stores may grow to 20 stores
- New stores have same data model
- Store-specific configuration follows same pattern

---

## 8. Dependencies

### 8.1 External Dependencies

**D1: AWS Services**
- AWS Lambda (container runtime support)
- Amazon ECR (container registry)
- AWS Secrets Manager (credential storage)
- Amazon DynamoDB (data persistence)
- Amazon CloudWatch (logging, monitoring, alarms)
- AWS IAM (permissions)
- Amazon EventBridge (scheduled triggers)

**D2: Third-Party Services**
- Naver Login Platform (authentication)
- Naver Booking API (data source)
- Naver Cloud SENS (SMS sending)
- Telegram Bot API (notifications)

**D3: Development Tools**
- GitHub (source control)
- GitHub Actions (CI/CD)
- Docker (containerization)
- Python 3.11+ (runtime)

### 8.2 Internal Dependencies

**D4: Configuration Data**
- Store list and metadata (from business team)
- SMS templates (from business/marketing team)
- Rule definitions (from business team)

**D5: Testing Data**
- Production data snapshot (sanitized) for testing
- Sample booking data for unit tests
- Known edge cases from production

---

## 9. Risks & Mitigation

### 9.1 Critical Risks

**R1: Naver Login Breaks During Migration**
- **Probability:** Medium
- **Impact:** High (system stops working)
- **Mitigation:**
  - Preserve login code 100% (no changes)
  - Test login separately before integration
  - Monitor login success rate closely
  - Keep old Lambda as instant fallback

**R2: SMS Content Changes Unintentionally**
- **Probability:** Medium
- **Impact:** High (customer confusion, brand damage)
- **Mitigation:**
  - Character-by-character comparison of templates
  - Manual review of all templates
  - Test SMS to internal numbers before production
  - Comparison testing validates content

**R3: Data Loss During Migration**
- **Probability:** Low
- **Impact:** Critical (lost SMS history, duplicate sends)
- **Mitigation:**
  - No database schema changes for MVP
  - DynamoDB automatic backups enabled
  - Test with DynamoDB snapshots
  - Rollback procedures documented

**R4: Performance Degradation**
- **Probability:** Low
- **Impact:** Medium (timeout, missed notifications)
- **Mitigation:**
  - Load testing with realistic data
  - Monitor execution time continuously
  - Optimize rule engine if needed
  - Lambda timeout buffer (5min sufficient)

### 9.2 Medium Risks

**R5: Configuration Errors**
- **Probability:** High
- **Impact:** Low-Medium (specific rules fail)
- **Mitigation:**
  - YAML schema validation
  - Rule validation on startup
  - Error messages explain issues clearly
  - Rollback to previous config version

**R6: Incomplete Test Coverage**
- **Probability:** Medium
- **Impact:** Medium (undiscovered bugs)
- **Mitigation:**
  - >80% coverage requirement
  - Comparison testing for comprehensive validation
  - Offline validation campaign catches issues before go-live
  - Gradual cutover if issues found

**R7: Documentation Gaps**
- **Probability:** Medium
- **Impact:** Low (slows future changes)
- **Mitigation:**
  - Documentation as acceptance criteria
  - Code review checks for doc updates
  - Runbook created before cutover

---

## 10. Timeline & Milestones

### 10.1 High-Level Timeline

**Total Duration:** 6 weeks
**Start Date:** TBD (after PRD approval)
**Target Launch:** Week 6

### 10.2 Milestones

**Week 1: Planning & Infrastructure Setup**
- Epic 1: Infrastructure Setup
- Deliverables: ECR repo, Secrets Manager, credentials migrated, CloudWatch dashboards
- Gate: Infrastructure smoke tests pass

**Week 2: Code Extraction & Refactoring**
- Epic 2: Code Extraction
- Deliverables: Modular codebase, Naver/SENS modules extracted, config loader
- Gate: Unit tests pass (>50% coverage)

**Weeks 2-3: Rule Engine Implementation**
- Epic 3: Rule Engine
- Deliverables: Rule engine core, condition/action evaluators, rules.yaml
- Gate: Rule engine tests pass, existing rules replicated

**Week 3: Integration & Testing**
- Epic 4: Integration & Testing
- Deliverables: main.py handler, integration tests, Docker container
- Gate: Comparison tests pass (100% match with old system)

**Week 4: Deployment & Validation**
- Epic 5: Deployment
- Deliverables: ECR deployment, offline validation campaign, readiness evidence pack
- Gate: Validation suite reports 100% parity and risks signed off

**Week 5: Cutover & Monitoring**
- Epic 5 continued: Cutover
- Deliverables: Production traffic switched to new Lambda, legacy assets archived after verification window
- Gate: 1 week zero production incidents

**Week 6: Post-MVP Enhancements (Optional)**
- Epic 6: Enhancements
- Deliverables: Slack integration, example new rules, performance tuning
- Gate: Enhancement features working

### 10.3 Go/No-Go Decision Points

**Decision Point 1 (End of Week 1):** Infrastructure Ready?
- All AWS resources created
- Credentials migrated successfully
- Smoke tests pass
- **Go/No-Go:** Proceed to coding if infrastructure stable

**Decision Point 2 (End of Week 3):** Code Quality Acceptable?
- >80% test coverage achieved
- Comparison tests show 100% match
- Performance within NFRs
- **Go/No-Go:** Proceed to deployment if quality gates met

**Decision Point 3 (End of Week 4):** Production Deployment Safe?
- Offline validation campaign successful (100% parity, risks mitigated)
- Zero unresolved discrepancies
- Monitoring and rollback ready
- **Go/No-Go:** Cutover to new Lambda if validation passes

---

## 11. Stakeholders

| Role | Name | Responsibilities |
|------|------|------------------|
| **Product Owner** | Sarah (PO Agent) | Requirements, prioritization, acceptance |
| **Developer** | AI Development Agent | Implementation, testing, deployment |
| **Business Stakeholder** | User (sooyeol) | Final approval, business requirements |
| **System Administrator** | User (sooyeol) | AWS account access, production access |

---

## 12. Appendix

### 12.1 Reference Documents

- `docs/brownfield-architecture.md` - Comprehensive technical analysis (1970 lines)
- `requierment.md` - Original requirements (Korean)
- `current_lambda_inform.md` - Current AWS Lambda configuration
- `oroginal_code/lambda_function.py` - Current implementation (449 lines)
- `oroginal_code/sens_sms.py` - Current SMS module (619 lines)

### 12.2 Glossary

- **Brownfield:** Enhancing/refactoring existing system (vs. greenfield = new project)
- **SENS:** Naver Cloud Simple & Easy Notification Service (SMS API)
- **ECR:** Amazon Elastic Container Registry
- **IaC:** Infrastructure as Code (Terraform/CloudFormation)
- **Lambda Layer:** AWS Lambda dependency packaging mechanism (deprecated approach)
- **Rule Engine:** System that evaluates conditions and executes actions based on configuration

### 12.3 Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-18 | Sarah (PO) | Initial PRD created from requirements and architecture analysis |

---

**PRD Status:** ✅ READY FOR REVIEW

**Next Steps:**
1. Review and approve PRD
2. Create Epic & Story structure based on this PRD
3. Begin Epic 1 (Infrastructure Setup) implementation
