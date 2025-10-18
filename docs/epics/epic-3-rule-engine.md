# Epic 3: Rule Engine Implementation

**Epic ID:** EPIC-3
**Status:** Draft
**Duration:** Weeks 2-3 (7 days)
**Dependencies:** Epic 2 (Code Extraction)
**Risk Level:** Medium

---

## Epic Overview

Implement the core rule engine that evaluates conditions and executes actions based on YAML configuration. This is the PRIMARY BUSINESS REQUIREMENT - enabling flexible rule composition without code changes. All existing hardcoded business logic (12 conditions, 9 actions) must be replicated as rule engine components.

**Why This Epic:** This is the core value proposition - business users can configure rules via YAML instead of waiting for developer code changes.

---

## Epic Goals

1. ✅ Implement rule engine core (load, validate, evaluate, execute)
2. ✅ Implement all 8 condition evaluator types
3. ✅ Implement all 6 action executor types
4. ✅ Create rules.yaml matching current behavior 100%
5. ✅ Validate rule engine output matches old system exactly
6. ✅ Achieve >80% test coverage for rule engine

---

## Success Criteria

- [ ] Rule engine loads rules from rules.yaml
- [ ] All existing conditions replicated (12 patterns → 8 evaluator types)
- [ ] All existing actions replicated (9 patterns → 6 executor types)
- [ ] rules.yaml produces identical SMS sends as old system
- [ ] New rule can be added via YAML only (no code change)
- [ ] Rule validation catches configuration errors
- [ ] >80% test coverage for rule engine modules

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status |
|----------|-------|----------|--------|--------|
| 3.1 | Implement Rule Engine Core | P0 | 2d | Draft |
| 3.2 | Implement Condition Evaluators | P0 | 2d | Draft |
| 3.3 | Implement Action Executors | P0 | 2d | Draft |
| 3.4 | Create rules.yaml Configuration | P0 | 0.5d | Draft |
| 3.5 | Unit Tests for Rule Engine | P0 | 0.5d | Draft |

**Total Estimated Effort:** 7 days

---

## Technical Context

### Current Hardcoded Business Logic

**12 Condition Patterns → 8 Evaluator Types:**

| Current Condition | New Evaluator Type | Code Location |
|-------------------|-------------------|---------------|
| `db_response is None` | `booking_not_in_db` | lambda_function.py:138 |
| `reserve_at - timedelta(hours=2) <= now < reserve_at` | `time_before_booking(hours)` | lambda_function.py:139 |
| `db_response['confirm_sms'] == False` | `flag_not_set('confirm_sms')` | lambda_function.py:162 |
| `db_response['remind_sms'] == False` | `flag_not_set('remind_sms')` | lambda_function.py:160 |
| `reserve_at > datetime.now()` | (combined with time_before_booking) | lambda_function.py:160 |
| `reserve_at - now < timedelta(hours=2)` | `time_before_booking(hours=2)` | lambda_function.py:161 |
| `datetime.now().hour == 20` | `current_hour(hour=20)` | lambda_function.py:177 |
| `db_response['option_sms'] == False` | `flag_not_set('option_sms')` | lambda_function.py:189 |
| `i['option'] == True` | `has_option_keyword()` | lambda_function.py:189 |
| `booking_status == 'RC03'` | `booking_status('RC03')` | lambda_function.py:332 |
| `booking_status == 'RC08'` | `booking_status('RC08')` | get_complete_items() |
| Keywords in option_keyword_list | `has_option_keyword(['네이버','인스타','원본'])` | lambda_function.py:255,364 |

**9 Action Patterns → 6 Executor Types:**

| Current Action | New Executor Type | Code Location |
|----------------|------------------|---------------|
| `send_sms(phone, 1)` | `send_sms(template='confirmation')` | lambda_function.py:152,164 |
| `send_sms(phone, 2, biz_id)` | `send_sms(template='guide', store_specific=true)` | lambda_function.py:156,168 |
| `send_sms(phone, 3)` | `send_sms(template='event')` | lambda_function.py:191 |
| `sms_table.put_item(Item=...)` | `create_db_record()` | lambda_function.py:150 |
| `update_item(..., 'confirm_sms')` | `update_flag('confirm_sms')` | lambda_function.py:163 |
| `update_item(..., 'remind_sms')` | `update_flag('remind_sms')` | lambda_function.py:167 |
| `update_item(..., 'option_sms')` | `update_flag('option_sms')` | lambda_function.py:190 |
| `results.append(message)` | (handled by rule engine logging) | lambda_function.py:153,157,173,192,195 |
| `requests.post(telegram_url, ...)` | `send_telegram(message)` | lambda_function.py:439,444 |

### Rule Engine Architecture

```python
# src/rules/engine.py
class RuleEngine:
    def __init__(self, rules_config: List[RuleConfig]):
        self.rules = rules_config
        self.condition_evaluators = {}  # Registry
        self.action_executors = {}      # Registry

    def register_condition(self, name: str, evaluator: Callable)
    def register_action(self, name: str, executor: Callable)
    def evaluate_rule(self, rule: RuleConfig, context: Dict) -> bool
    def execute_rule(self, rule: RuleConfig, context: Dict)
    def process_booking(self, booking: Booking) -> List[ActionResult]
```

### Example rules.yaml

```yaml
rules:
  - name: "New Booking Confirmation"
    enabled: true
    conditions:
      - type: "booking_not_in_db"
    actions:
      - type: "create_db_record"
      - type: "send_sms"
        params:
          template: "confirmation"
      - type: "send_telegram"
        params:
          message: "Confirmation SMS sent to {{booking.phone}}"

  - name: "Two Hour Reminder"
    enabled: true
    conditions:
      - type: "time_before_booking"
        params:
          hours: 2
      - type: "flag_not_set"
        params:
          flag: "remind_sms"
    actions:
      - type: "send_sms"
        params:
          template: "guide"
          store_specific: true
      - type: "update_flag"
        params:
          flag: "remind_sms"
          value: true
```

### References
- Architecture Doc: Lines 1425-1430 (Phase 3: Rule Engine Implementation)
- Architecture Doc: Lines 1070-1165 (Rule Engine Design)
- Architecture Doc: Lines 394-465 (Current Conditions/Actions Mapping)
- PRD: Section 4.1 FR1-FR3 (Rule Engine Requirements)
- requierment.md: Lines 1-5 (Original Korean requirements)

---

## Epic Dependencies

### Upstream Dependencies
- **Epic 2:** Needs SMS service, DB client, config loader modules

### Downstream Dependencies
- **Epic 4 (Integration):** Rules integrated into main Lambda handler
- **Epic 6 (Enhancements):** New rules added (Slack, date ranges)

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Rule engine too slow | Low | Medium | Profile and optimize, <100ms per rule acceptable |
| Complex OR logic needed | Medium | Low | Start with AND only, defer OR to post-MVP |
| Rule validation incomplete | Medium | Medium | Comprehensive schema validation, unit tests |
| Conditions don't match old logic | Medium | High | Comparison testing, side-by-side execution |

---

## Acceptance Criteria (Epic Level)

1. **Rule Engine Core:**
   - Loads rules from rules.yaml
   - Validates rule schema on startup
   - Evaluates all conditions (AND logic)
   - Executes all actions in sequence
   - Handles errors gracefully (log, continue to next rule)

2. **Condition Evaluators (8 types):**
   - `booking_not_in_db` - checks DynamoDB
   - `time_before_booking(hours)` - time window check
   - `flag_not_set(flag)` - DB flag check
   - `current_hour(hour)` - time-of-day check
   - `booking_status(status)` - status code check
   - `has_option_keyword(keywords)` - option detection
   - `store_id_matches(store_ids)` - store filtering
   - `date_range(start, end)` - date filtering (NEW)

3. **Action Executors (6 types):**
   - `send_sms(template, store_specific)` - SENS API
   - `create_db_record()` - DynamoDB insert
   - `update_flag(flag, value)` - DynamoDB update
   - `send_telegram(message)` - Telegram notification
   - `send_slack(message)` - Slack notification (NEW)
   - `log_event(message)` - CloudWatch logging

4. **rules.yaml:**
   - Replicates all 3 current rule patterns:
     - New Booking Confirmation (C1 → A4, A1, optional A2)
     - Late Reminder (C3+C4+C5+C6 → A1, A5, A2, A6)
     - Evening Event SMS (C7+C11+C8+C9 → A3, A7)
   - Validates against schema
   - Well-documented with comments

5. **Testing:**
   - Unit tests for each condition evaluator
   - Unit tests for each action executor
   - Integration tests for rule engine
   - Comparison tests: old system vs. new rules

---

## Testing Strategy for This Epic

**Unit Tests:**
- Each condition evaluator with various inputs
- Each action executor with mocked services
- Rule engine with sample rules
- Rule validation with invalid YAML

**Integration Tests:**
- Full rule evaluation with real context
- Action execution with real services (test mode)
- Error handling (malformed rules, missing config)

**Comparison Tests:**
- Same booking data through old and new systems
- Compare SMS sends, DB updates, notifications
- 100% match required

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-18 | 1.0 | Epic created from PRD and architecture doc | Sarah (PO) |
