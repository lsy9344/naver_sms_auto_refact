# Epic 6: Post-MVP Enhancements

**Epic ID:** EPIC-6
**Status:** Draft
**Duration:** Week 5+ (ongoing)
**Dependencies:** Epic 5 (Successful Cutover)
**Risk Level:** Low (enhancements, not critical)

---

## Epic Overview

After successful production cutover, implement enhancement features that demonstrate the value of the new rule engine. These features validate that business users can now add functionality via configuration instead of code changes. This epic is OPTIONAL but demonstrates the ROI of the refactoring effort.

**Why This Epic:** Proves the business value - new features can be added via YAML configuration in minutes instead of code deployment in days.

---

## Epic Goals

1. ✅ Add example new rules from requierment.md (Korean requirements)
2. ✅ Implement Slack integration (new notification channel)
3. ✅ Add date-range filtering (new condition type)
4. ✅ Add multi-option filtering (new condition type)
5. ✅ Performance optimization if needed
6. ✅ Create rule management documentation for business users

---

## Success Criteria

- [ ] Example rules from requirements working via YAML only
- [ ] Slack notifications sent for configured events
- [ ] Date-range rules execute correctly
- [ ] Multi-option rules execute correctly
- [ ] Performance: Lambda execution <2 minutes (improved)
- [ ] Business user successfully adds rule without developer help

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status |
|----------|-------|----------|--------|--------|
| 6.1 | Implement Example Rules from Requirements | P1 | 1d | Draft |
| 6.2 | Add Slack Integration | P1 | 1.5d | Draft |
| 6.3 | Add Date-Range Condition Evaluator | P1 | 0.5d | Draft |
| 6.4 | Add Multi-Option Condition Evaluator | P2 | 0.5d | Draft |
| 6.5 | Performance Optimization | P2 | 1d | Draft |
| 6.6 | Create Rule Management Documentation | P1 | 0.5d | Draft |

**Total Estimated Effort:** 5 days

---

## Technical Context

### Example Rules from requierment.md (Korean Requirements)

**Original Korean Requirements:**
```
1. 조건, 액션을 손쉽게 추가/조합할 수 있게 구조를 변경해야 합니다.
예) a 매장 고객중 1 옵션을 선택한 사람들에게 aa포맷 문자를 전송
예) c 매장 고객중 예약시간 2시간 전 고객에게 bb포맷 문자 메세지 전송
예) 모든 매장 신규 예약 감지 시 cc 포맷 문자 메세지 전송
예) 특정 날짜 기간 내에 예약한 모든 고객 중 b 옵션을 2개이상 선택한 사람 리스트 슬랙으로 전송
```

**Translation:**
1. Easily add/combine conditions and actions
2. Example: Send "aa format" SMS to store A customers who selected option 1
3. Example: Send "bb format" SMS to store C customers 2 hours before reservation
4. Example: Send "cc format" SMS when new reservation detected (all stores)
5. Example: Send Slack list of customers who booked within specific date range AND selected 2+ b options

**Implementing as Rules:**

**Example Rule 1:** Store-specific option-based SMS
```yaml
  - name: "Store 1051707 Option Promotion"
    enabled: true
    conditions:
      - type: "store_id_matches"
        params:
          store_ids: ["1051707"]
      - type: "has_option_keyword"
        params:
          keywords: ["네이버"]  # Option 1
    actions:
      - type: "send_sms"
        params:
          template: "naver_option_promo"  # aa format (NEW template)
```

**Example Rule 2:** (Already exists - 2-hour reminder)

**Example Rule 3:** (Already exists - new booking confirmation)

**Example Rule 4:** Date range + multi-option + Slack
```yaml
  - name: "Holiday Event Customer List"
    enabled: true
    conditions:
      - type: "date_range"
        params:
          start: "2025-12-20"
          end: "2025-12-31"
      - type: "has_multiple_options"
        params:
          keywords: ["원본", "네이버"]  # b options
          min_count: 2
    actions:
      - type: "send_slack"
        params:
          channel: "#marketing"
          message: "Holiday booking: {{booking.name}} - {{booking.phone}} - {{booking.store_id}}"
```

### Slack Integration

**New Action Executor:**
```python
# src/rules/actions.py
async def send_slack(context: Dict, channel: str, message: str):
    """
    Send Slack notification using Slack Webhook or Bot API
    """
    slack_webhook_url = context['settings'].slack_webhook_url
    payload = {
        "channel": channel,
        "text": render_template(message, context)
    }
    response = requests.post(slack_webhook_url, json=payload)
    response.raise_for_status()
```

**Configuration:**
```yaml
# config/slack_config.yaml
slack:
  enabled: true
  webhook_url: ${SLACK_WEBHOOK_URL}  # From Secrets Manager
  default_channel: "#operations"
```

### New Condition Evaluators

**Date Range:**
```python
# src/rules/conditions.py
def date_range(context: Dict, start: str, end: str) -> bool:
    """
    Check if booking date is within specified range
    """
    booking_date = context['booking'].reserve_at.date()
    start_date = datetime.strptime(start, '%Y-%m-%d').date()
    end_date = datetime.strptime(end, '%Y-%m-%d').date()
    return start_date <= booking_date <= end_date
```

**Multi-Option:**
```python
# src/rules/conditions.py
def has_multiple_options(context: Dict, keywords: List[str], min_count: int) -> bool:
    """
    Check if booking has multiple option keywords
    """
    booking = context['booking']
    matched_count = sum(1 for keyword in keywords if keyword in str(booking.option))
    return matched_count >= min_count
```

### Performance Optimization Areas

**Potential Optimizations:**
1. **Rule Engine Caching:**
   - Cache compiled rules across Lambda invocations
   - Cache condition evaluators

2. **Parallel Rule Evaluation:**
   - Evaluate independent rules in parallel
   - Use asyncio for action execution

3. **Database Query Optimization:**
   - Batch DynamoDB queries
   - Use DynamoDB transactions for atomicity

4. **Naver API Optimization:**
   - Parallel fetching for multiple stores
   - Connection pooling for requests

**Target Performance:**
- Current: ~2-3 minutes
- Target: <2 minutes (33% improvement)

### References
- requierment.md: Lines 1-5 (Korean requirements for examples)
- Architecture Doc: Lines 1447-1454 (Phase 6: Enhancement)
- PRD: Section 6.2 (Out of Scope → Post-MVP)

---

## Epic Dependencies

### Upstream Dependencies
- **Epic 5:** Successful production cutover required
- **Epic 3:** Rule engine must support new condition/action types

### Downstream Dependencies
- None (this is the final epic)

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Slack API issues | Low | Low | Proper error handling, fallback to Telegram |
| Performance regression | Low | Medium | Load testing before production, optimize if needed |
| New rules break existing | Low | Medium | Validation, testing, rollback capability |
| Business user confusion | Medium | Low | Comprehensive documentation, examples |

---

## Acceptance Criteria (Epic Level)

1. **Example Rules from Requirements:**
   - All 4 example scenarios implemented as rules
   - Rules work correctly in production
   - Business user can modify rule parameters

2. **Slack Integration:**
   - Slack action executor implemented
   - Slack webhook configured in Secrets Manager
   - Test message sent successfully
   - Error handling for Slack API failures

3. **New Condition Evaluators:**
   - `date_range(start, end)` works correctly
   - `has_multiple_options(keywords, min_count)` works correctly
   - Unit tests pass (>80% coverage)

4. **Performance:**
   - Lambda execution: <2 minutes average
   - No timeouts or throttling
   - Memory usage: <512MB

5. **Documentation:**
   - Rule management guide for business users
   - Examples for all condition/action types
   - Troubleshooting guide
   - YAML syntax reference

6. **Validation:**
   - Business user successfully adds new rule
   - Rule deploys within 20 minutes (next Lambda execution)
   - Rule executes correctly
   - No code changes required

---

## Business User Rule Management Guide

**Topics to Cover:**

1. **Introduction**
   - What are rules and how do they work?
   - When to add/modify rules
   - When to ask for developer help

2. **Rule Anatomy**
   - YAML syntax basics
   - Conditions explained
   - Actions explained
   - Parameters and templating

3. **Available Conditions**
   - `booking_not_in_db` - detect new bookings
   - `time_before_booking(hours)` - time windows
   - `flag_not_set(flag)` - SMS sent flags
   - `current_hour(hour)` - time of day
   - `booking_status(status)` - status codes
   - `has_option_keyword(keywords)` - option detection
   - `store_id_matches(store_ids)` - store filtering
   - `date_range(start, end)` - date filtering
   - `has_multiple_options(keywords, min_count)` - multi-option

4. **Available Actions**
   - `send_sms(template, store_specific)` - send SMS
   - `create_db_record()` - create booking record
   - `update_flag(flag, value)` - update flags
   - `send_telegram(message)` - Telegram notification
   - `send_slack(channel, message)` - Slack notification
   - `log_event(message)` - CloudWatch logging

5. **Examples**
   - Copy-paste templates for common scenarios
   - How to combine conditions (AND logic)
   - Using templating in messages

6. **Testing**
   - How to validate YAML syntax
   - How to test rules before production
   - How to read logs

7. **Troubleshooting**
   - Common YAML errors
   - How to check if rule executed
   - How to rollback bad rules

---

## Testing Strategy for This Epic

**Unit Tests:**
- New condition evaluators
- New action executors
- Performance optimizations

**Integration Tests:**
- Example rules end-to-end
- Slack integration
- Date range filtering

**User Acceptance Testing:**
- Business user adds rule
- Business user modifies rule
- Business user validates rule execution

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-18 | 1.0 | Epic created from PRD and requirements | Sarah (PO) |
