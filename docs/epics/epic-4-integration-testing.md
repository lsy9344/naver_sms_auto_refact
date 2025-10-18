# Epic 4: Integration & Testing

**Epic ID:** EPIC-4
**Status:** Draft
**Duration:** Week 3 (5 days)
**Dependencies:** Epic 2 (Code Extraction), Epic 3 (Rule Engine)
**Risk Level:** High (validates everything works together)

---

## Epic Overview

Integrate all modules into a cohesive Lambda function, create the Docker container, and perform comprehensive testing to ensure 100% functional parity with the old system. This epic is CRITICAL for validating that refactoring preserved all functionality.

**Why This Epic:** Integration failures are the highest risk in brownfield refactoring. Comprehensive testing prevents production incidents.

---

## Epic Goals

1. ✅ Create new main.py Lambda handler integrating all modules
2. ✅ Implement comparison testing framework
3. ✅ Achieve 100% output parity with old system
4. ✅ Build Docker container for ECR deployment
5. ✅ Test container locally with Lambda Runtime Interface Emulator
6. ✅ Achieve >80% overall test coverage

---

## Success Criteria

- [ ] main.py handler integrates all modules cleanly
- [ ] Comparison tests pass with 100% match (SMS, DB, Telegram)
- [ ] Docker container builds successfully (<10GB)
- [ ] Container runs locally and processes bookings correctly
- [ ] >80% code coverage across all modules
- [ ] Performance: Lambda execution <4 minutes
- [ ] Zero regressions compared to old system

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status |
|----------|-------|----------|--------|--------|
| 4.1 | Create main.py Lambda Handler | P0 | 1d | Draft |
| 4.2 | Implement Comparison Testing Framework | P0 | 1.5d | Draft |
| 4.3 | Build Docker Container | P0 | 1d | Draft |
| 4.4 | Integration Testing | P0 | 1d | Draft |
| 4.5 | Performance Testing & Optimization | P1 | 0.5d | Draft |

**Total Estimated Effort:** 5 days

---

## Technical Context

### New Lambda Handler Structure

```python
# src/main.py
def lambda_handler(event, context):
    """
    New Lambda handler replacing oroginal_code/lambda_function.py
    """
    # 1. Load configuration
    settings = Settings.load()

    # 2. Authenticate with Naver
    session_mgr = SessionManager(dynamodb_client)
    cached_cookies = session_mgr.get_cookies()
    authenticator = NaverAuthenticator(settings.naver_username, settings.naver_password)
    cookies = authenticator.login(cached_cookies)
    if cookies != cached_cookies:
        session_mgr.save_cookies(cookies)

    # 3. Fetch bookings
    api_session = authenticator.get_session()
    booking_api = NaverBookingAPI(api_session)
    bookings = booking_api.get_confirmed_bookings(settings.stores)
    completed_bookings = booking_api.get_completed_bookings(settings.stores)

    # 4. Process bookings through rule engine
    rule_engine = RuleEngine(settings.rules)
    setup_rule_engine(rule_engine, sms_service, db_client, telegram_service)

    results = []
    for booking in bookings:
        context = build_context(booking, db_client)
        rule_results = rule_engine.process_booking(context)
        results.extend(rule_results)

    # 5. Send summary notification
    telegram_service.send_summary(results)

    return {'statusCode': 200, 'body': json.dumps(results)}
```

### Comparison Testing Strategy

**Goal:** Prove refactored system produces IDENTICAL outputs

**Approach:**
1. Capture production inputs/outputs from old Lambda (1 week of data)
2. Replay same inputs through new Lambda
3. Compare outputs:
   - SMS sent (phone, template, content)
   - DynamoDB writes (records created/updated)
   - Telegram messages

**Test Data:**
- Sanitize real production data (mask phone numbers, names)
- Include edge cases:
  - Booking within 2-hour window
  - Booking with option keywords
  - Booking at exactly 8 PM (event SMS trigger)
  - Cookie expiry scenario
  - Empty booking list

### Docker Container Structure

```dockerfile
FROM public.ecr.aws/lambda/python:3.11

# Install Chrome + ChromeDriver
RUN yum install -y wget unzip && \
    wget https://chrome-for-testing.storage.googleapis.com/121.0.6167.85/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip -d /opt && \
    wget https://chrome-for-testing.storage.googleapis.com/121.0.6167.85/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip -d /opt && \
    yum clean all

# Set binary paths
ENV CHROME_BIN=/opt/chrome-linux64/chrome
ENV CHROMEDRIVER_BIN=/opt/chromedriver-linux64/chromedriver

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/
COPY config/ ${LAMBDA_TASK_ROOT}/config/

# Lambda handler
CMD ["main.lambda_handler"]
```

### References
- Architecture Doc: Lines 1431-1438 (Phase 4: Integration & Testing)
- Architecture Doc: Lines 1036-1050 (Dockerfile Structure)
- Architecture Doc: Lines 1683-1713 (Comparison Testing Strategy)
- PRD: Section 5.1 MSC1 (Functional Parity Success Criteria)

---

## Epic Dependencies

### Upstream Dependencies
- **Epic 1:** ECR repository for container
- **Epic 2:** All modules (auth, api, sms, db, config)
- **Epic 3:** Rule engine

### Downstream Dependencies
- **Epic 5 (Deployment):** Needs tested container image

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Integration bugs | High | High | Comprehensive integration tests, comparison testing |
| Container too large | Low | Medium | Multi-stage build, minimize layers |
| Performance regression | Low | Medium | Load testing, profiling, optimization |
| Test data insufficient | Medium | Medium | Capture 1 week of production data |
| ChromeDriver issues in container | Medium | High | Test locally first, match versions exactly |

---

## Acceptance Criteria (Epic Level)

1. **main.py Handler:**
   - Integrates all modules cleanly
   - Follows same flow as old lambda_handler
   - Handles errors gracefully (no crashes)
   - Returns structured response

2. **Comparison Testing:**
   - Framework compares SMS, DB, Telegram outputs
   - 100% match on test dataset (minimum 100 bookings)
   - Reports discrepancies clearly
   - Test coverage includes all edge cases

3. **Docker Container:**
   - Builds successfully (<10GB)
   - Contains Python 3.11 runtime
   - Chrome + ChromeDriver installed and working
   - All dependencies installed
   - Config files included
   - Runs locally with RIE (Runtime Interface Emulator)

4. **Integration Tests:**
   - End-to-end test: login → fetch → process → notify
   - All modules interact correctly
   - Secrets loaded from Secrets Manager
   - Configuration loaded from YAML
   - Database operations work

5. **Performance:**
   - Lambda execution: <4 minutes
   - Cold start: <10 seconds
   - Memory usage: <512MB
   - No timeouts or throttling

6. **Test Coverage:**
   - Overall coverage: >80%
   - Unit tests: >80% per module
   - Integration tests: critical paths covered
   - All comparison tests passing

---

## Testing Strategy for This Epic

**Integration Tests:**
- Full Lambda handler execution with test data
- Naver login + API fetch + rule processing
- Error scenarios (API down, DB unavailable)

**Comparison Tests:**
- Old vs. new system with same inputs
- Character-by-character SMS content comparison
- DynamoDB record comparison (all fields)
- Telegram message comparison

**Container Tests:**
- Build test (docker build succeeds)
- Local execution test (docker run with RIE)
- Smoke test (invoke with test event)

**Performance Tests:**
- Load test with 100 bookings
- Memory profiling
- Execution time profiling
- Cold start timing

---

## Test Data Requirements

**Must Capture from Production:**
- Naver API booking responses (sanitized)
- DynamoDB state before/after execution
- SMS that were sent (content, recipients)
- Telegram notifications

**Synthetic Test Data:**
- Booking with all fields populated
- Booking with minimal fields
- Booking with option keywords
- Booking within 2-hour window
- Booking at exactly 8 PM

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-18 | 1.0 | Epic created from PRD and architecture doc | Sarah (PO) |
