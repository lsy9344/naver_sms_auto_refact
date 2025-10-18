# Epic 2: Code Extraction & Modularization

**Epic ID:** EPIC-2
**Status:** Draft
**Duration:** Week 2 (5 days)
**Dependencies:** Epic 1 (Infrastructure Setup)
**Risk Level:** Medium-High (touching critical Naver login code)

---

## Epic Overview

Extract monolithic `lambda_function.py` (449 lines) and `sens_sms.py` (619 lines) into modular components with clear separation of concerns. **CRITICAL:** Naver login mechanism must be preserved 100% exactly as-is. SENS API logic must be preserved while externalizing templates.

**Why This Epic:** Cannot implement rule engine without modular architecture. Current monolithic structure prevents testing and maintainability.

---

## Epic Goals

1. ✅ Extract Naver login module (PRESERVE 100% - lines 260-301)
2. ✅ Extract SENS SMS API module (preserve logic, externalize templates)
3. ✅ Extract DynamoDB operations into database module
4. ✅ Create configuration loader for YAML files
5. ✅ Implement structured logging (replace print statements)
6. ✅ Achieve >50% test coverage for extracted modules

---

## Success Criteria

- [ ] Naver login works identically (cookie caching, retry logic, exact timing)
- [ ] SENS SMS API sends messages with same signatures and headers
- [ ] All SMS templates externalized to sms_templates.yaml
- [ ] DynamoDB operations abstracted and testable
- [ ] Configuration loader reads stores.yaml, rules.yaml
- [ ] Structured logging to CloudWatch (JSON format)
- [ ] Unit tests pass with >50% coverage

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status |
|----------|-------|----------|--------|--------|
| 2.1 | Extract Naver Login Module | P0 | 1.5d | Draft |
| 2.2 | Extract SENS SMS Module | P0 | 1.5d | Draft |
| 2.3 | Extract DynamoDB Operations | P0 | 1d | Draft |
| 2.4 | Create Configuration Loader | P0 | 0.5d | Draft |
| 2.5 | Implement Structured Logging | P1 | 0.5d | Draft |

**Total Estimated Effort:** 5 days

---

## Technical Context

### Preservation Requirements (CRITICAL)

**Must preserve 100% exactly:**
- **Naver Login (lambda_function.py:260-301):**
  - JavaScript credential injection (lines 274-276)
  - Random delays with `uniform()` (lines 275-279)
  - Cookie validation via URL check (line 298)
  - Recursive retry on failure (line 300)
  - Chrome options (lines 229-248)

- **SENS API (sens_sms.py):**
  - Signature generation (lines 79-85): HMAC-SHA256 algorithm
  - Request headers (lines 69-74): exact format
  - Store-to-phone mapping (lines 15-24)
  - API endpoint URLs

**Can refactor:**
- SMS templates → move to sms_templates.yaml
- Template selection logic → use config lookup
- DynamoDB operations → abstract into client
- Print statements → structured logging

### Module Structure

```
src/
├── auth/
│   └── naver_login.py        # Lines 229-301 EXACT COPY
├── api/
│   └── naver_booking.py      # get_items(), count_items()
├── notifications/
│   └── sms_service.py        # Refactored from sens_sms.py
├── database/
│   ├── dynamodb_client.py    # DynamoDB operations
│   └── session_manager.py    # Session cookie management
├── config/
│   ├── settings.py           # Configuration loader
│   └── __init__.py
└── utils/
    ├── logger.py             # Structured logging
    └── date_utils.py         # format_date() function
```

### References
- Architecture Doc: Lines 1418-1424 (Phase 2: Code Extraction)
- Architecture Doc: Lines 469-506 (Naver Login Preservation)
- Architecture Doc: Lines 508-554 (SENS API Preservation)
- Architecture Doc: Lines 927-1000 (Module Structure)
- PRD: Section 4.1 FR4 (Preservation Requirements)

---

## Epic Dependencies

### Upstream Dependencies
- **Epic 1:** Secrets Manager must exist for config loader

### Downstream Dependencies
- **Epic 3 (Rule Engine):** Needs modular actions (SMS, DB updates)
- **Epic 4 (Integration):** Needs all modules to integrate

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Naver login breaks | Medium | Critical | Extract as-is, zero modifications, test separately |
| SENS signature invalid | Low | High | Preserve algorithm exactly, test with real API |
| Templates lose content | Low | High | Character-by-character comparison in tests |
| Module coupling issues | Medium | Medium | Clear interfaces, integration tests |

---

## Acceptance Criteria (Epic Level)

1. **Naver Login Module:**
   - Successfully logs in using cached cookies
   - Falls back to fresh login on cookie expiry
   - Saves cookies to DynamoDB session table
   - Passes isolated unit tests

2. **SENS SMS Module:**
   - Sends SMS with valid signatures
   - Templates loaded from sms_templates.yaml
   - Store-to-phone mapping from stores.yaml
   - All 10 templates content identical

3. **DynamoDB Module:**
   - get_item(), put_item(), update_item() work
   - Handles `sms` and `session` tables
   - Proper error handling

4. **Configuration Loader:**
   - Reads YAML files from config/ directory
   - Loads secrets from Secrets Manager
   - Validates configuration schema
   - Caches config during Lambda execution

5. **Structured Logging:**
   - JSON format logs to CloudWatch
   - Log levels: DEBUG, INFO, WARNING, ERROR
   - Includes context (booking_id, store_id, etc.)

---

## Testing Strategy for This Epic

**Unit Tests:**
- Test Naver login with mocked Selenium
- Test SENS signature generation with known inputs
- Test DynamoDB client with moto (AWS mocking)
- Test config loader with sample YAML files

**Integration Tests:**
- Naver login with real credentials (test account)
- SENS SMS send to test phone number
- DynamoDB with local DynamoDB Docker

**Comparison Tests:**
- Compare SENS API requests (headers, signature) with original
- Compare SMS content character-by-character

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-18 | 1.0 | Epic created from PRD and architecture doc | Sarah (PO) |
