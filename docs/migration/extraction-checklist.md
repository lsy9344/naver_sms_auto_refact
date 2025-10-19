# Extraction Checklist – Epic 2: Database and Configuration Separation

This checklist tracks the migration of legacy Lambda function operations into dedicated, testable modules. The goal is to extract core concerns (database, configuration, notifications, SMS rules) from the monolithic `lambda_function.py` into focused, reusable components.

---

## Story 2.1: Extract Authentication Module (COMPLETED)

- [x] Extract Naver login logic from lambda_function.py:1-50
- [x] Create `src/auth/naver_auth.py` with `NaverAuthenticator` class
- [x] Implement multi-factor retry logic with backoff
- [x] Add structured logging for authentication attempts
- [x] Unit tests: `tests/unit/test_naver_auth.py` (>70% coverage)
- [x] Integration tests with Naver API (mock or sandbox)
- [x] Documentation: `docs/auth/naver-auth-guide.md`
- [x] Code review and QA approval

**Lambda Removal:** ⏸ Pending until 2.4/2.5 integration

---

## Story 2.2: Extract SENS SMS Module (COMPLETED)

- [x] Extract SENS SMS sending from lambda_function.py:200-280
- [x] Create `src/notifications/sms_service.py` with `SmsService` class
- [x] Implement message templating and validation
- [x] Add retry logic for transient failures
- [x] Unit tests: `tests/unit/test_sms_service.py` (>70% coverage)
- [x] Integration tests with SENS API (mock or sandbox)
- [x] Documentation: `docs/notifications/sms-service-guide.md`
- [x] Code review and QA approval

**Lambda Removal:** ⏸ Pending until 2.4/2.5 integration

---

## Story 2.3: Extract DynamoDB Operations (IN PROGRESS)

- [x] Extract DynamoDB booking operations from lambda_function.py:66-81, 135-150
- [x] Create `src/database/dynamodb_client.py` with `BookingRepository` and `SessionRepository`
- [x] Implement all four repository methods:
  - [x] `get_booking(prefix, phone)` → replicates get_item
  - [x] `create_booking(record)` → replicates put_item
  - [x] `update_flag(prefix, phone, flag_name, value)` → replicates update_item
  - [x] `scan_unnotified_options()` → replicates scan with grouping
- [x] Create custom exception hierarchy: `src/database/exceptions.py`
- [x] Implement structured logging: `src/utils/logger.py`
- [x] Define domain models: `src/domain/booking.py`, `src/domain/session.py`
- [x] Unit tests with moto: `tests/unit/test_database_booking.py`, `tests/unit/test_database_session.py` (71% coverage)
- [x] Error handling for throttling, network, IAM failures
- [x] Documentation: `docs/database/dynamodb.md`
- [ ] **Code review and QA approval**
- [ ] Migration testing: Run legacy vs. new side-by-side on sample data

**Lambda Removal:** ⏸ Pending until 2.4/2.5 integration

---

## Story 2.4: Create Configuration Loader (BLOCKED on 1.4/1.5)

- [ ] Extract hardcoded table names, AWS region, retry config from lambda_function.py
- [ ] Create `src/config/settings.py` with Settings class
- [ ] Load from Secrets Manager (Story 1.4 provides credentials)
- [ ] Load from environment variables for dev/test
- [ ] Unit tests: `tests/unit/test_config.py` (>70% coverage)
- [ ] Integration with Story 1.4/1.5 (IAM, Secrets Manager)
- [ ] Documentation: `docs/config/settings-guide.md`

**Dependency:** Requires Story 1.4 (Secrets Manager) and 1.5 (IAM roles)

**Lambda Update:** Update lambda_function.py to use `src.config.settings.Settings` instead of hardcoded values

---

## Story 2.5: Refactor Lambda Entry Point (BLOCKED on 2.1–2.4)

- [ ] Update lambda_function.py to import and use:
  - [ ] `src.auth.NaverAuthenticator` (replace inline login)
  - [ ] `src.notifications.SmsService` (replace inline SMS sending)
  - [ ] `src.database.BookingRepository` (replace inline DynamoDB calls)
  - [ ] `src.config.Settings` (replace hardcoded config)
- [ ] Remove ~300 lines of extracted logic from lambda_function.py
- [ ] Update Lambda handler signature if needed
- [ ] Integration tests: `tests/integration/test_lambda_refactored.py`
- [ ] Performance testing (latency unchanged)
- [ ] Canary deployment to dev, staging, prod

**Dependency:** Requires Stories 2.1, 2.2, 2.3, 2.4 completed

**Timeline:** Estimated 1–2 sprints after 2.4

---

## Story 2.6: Unit Test Coverage and Refactor Patterns (OPTIONAL)

- [ ] Achieve >80% code coverage across all modules
- [ ] Refactor common patterns (retry logic, error handling, logging)
- [ ] Add integration tests for multi-module interactions
- [ ] Performance optimization (caching, batching)
- [ ] Documentation: `docs/testing/testing-patterns.md`

---

## Integration Timeline

```
Story 1.1–1.5 (Infrastructure):
  ├─ 1.1: AWS Setup
  ├─ 1.2: IAM Policies
  ├─ 1.3: Monitoring
  ├─ 1.4: Secrets Manager
  └─ 1.5: Terraform

Story 2.1–2.3 (Extraction – Parallel):
  ├─ 2.1: Auth ✓
  ├─ 2.2: SMS ✓
  └─ 2.3: Database (→ Code Review)

Story 2.4 (Config – Requires 1.4):
  └─ Blocker: Depends on Story 1.4

Story 2.5 (Integration – Requires 2.1–2.4):
  └─ Blocker: Depends on Stories 2.1, 2.2, 2.3, 2.4

Story 2.6 (Polish – Optional):
  └─ Nice-to-have after 2.5
```

---

## Lambda Function Removal Schedule

**Phase 1 (Q4 2025 – Post 2.1/2.2/2.3):**
- Run new modules in parallel with lambda_function.py (no changes to Lambda)
- Monitor logs and metrics
- Collect performance data

**Phase 2 (Q1 2026 – Post 2.4):**
- Update lambda_function.py to use extracted modules
- Deploy to dev/staging for integration testing
- Run side-by-side comparison for 1 week

**Phase 3 (Q1 2026 – Post 2.5):**
- Deploy refactored Lambda to production
- Enable canary (10% → 50% → 100%)
- Monitor error rates, latency, logs

**Phase 4 (Q1 2026 – Cleanup):**
- Archive original lambda_function.py
- Remove feature flags
- Update runbooks and training materials

---

## Definition of Done per Story

### Story 2.3 (Current)

- [x] All acceptance criteria implemented
- [x] Unit tests pass (40 tests, 71% coverage)
- [x] Error handling covers all scenarios
- [x] Structured logging in place
- [x] Domain models implemented and tested
- [ ] **Code review approved**
- [ ] **QA gate signed off**
- [ ] Migration testing completed
- [ ] Documentation complete

---

## Blockers and Risks

### Blockers

| Story | Blocker | Impact | Mitigation |
|-------|---------|--------|-----------|
| 2.4 | Story 1.4 not ready | Config module can't load credentials | Create mock Settings class, swap on 1.4 completion |
| 2.5 | Stories 2.1–2.4 not done | Can't integrate Lambda | Use feature flags to deploy modules independently |

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Data format mismatch between old/new | Medium | Lost/duplicate SMS sends | Regression testing with 1-week production sample |
| Breaking change in exception semantics | Medium | Integration failures | Match legacy None returns (AC-4a) exactly |
| Performance regression | Low | Lambda timeout or throttling | Load testing before canary deployment |

---

## Success Metrics

- [x] All extraction stories deliver >70% unit test coverage
- [x] Structured logging adopted across new modules
- [x] Zero production incidents during parallel running
- [ ] < 5% latency increase post-refactor (target: ±2%)
- [ ] All team members trained on new module architecture

---

## References

- **Epic 2 Overview:** `docs/epics/epic-2-database-config-separation.md`
- **Story 2.3 Detail:** `docs/stories/2.3.extract-dynamodb-operations.md`
- **Database Documentation:** `docs/database/dynamodb.md`
- **Testing Strategy:** `docs/testing/testing-strategy.md`
- **Architecture:** `docs/brownfield-architecture.md`

