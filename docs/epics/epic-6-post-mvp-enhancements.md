# Epic 6: Post-MVP Enhancements

**Epic ID:** EPIC-6
**Status:** In Progress (Stories 6.2-6.4 Done, 6.1 In Progress)
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

- [x] Example rules from requirements working via YAML only
- [x] Slack notifications sent for configured events
- [x] Date-range rules execute correctly
- [x] Multi-option rules execute correctly
- [ ] Performance: Lambda execution <2 minutes (improved)
- [ ] Business user successfully adds rule without developer help

---

## Stories in This Epic

| Story ID | Title | Priority | Effort | Status | Planned Order |
|----------|-------|----------|--------|--------|---------------|
| 6.2 | Add Slack Integration | P1 | 1.5d | Done | 1 |
| 6.3 | Add Date-Range Condition Evaluator | P1 | 0.5d | Done | 2 |
| 6.4 | Add Multi-Option Condition Evaluator | P2 | 0.5d | Done | 3 |
| 6.1 | Implement Example Rules from Requirements | P1 | 1d | In Progress | 4 |
| 6.6 | Create Rule Management Documentation | P1 | 0.5d | Pending | 5 |
| 6.5 | Performance Optimization | P2 | 1d | Pending | 6 |

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

---

## Business User Rule Management Guide

### 1. Introduction

**What are rules?**

Rules are configuration-driven instructions that automatically process bookings and send notifications. Instead of waiting for developers to code new features, operations teams can now add new rules by editing `config/rules.yaml`.

**How do rules work?**

1. New booking arrives → Lambda processes it
2. System checks all enabled rules in order
3. For each rule: Does every condition match? (AND logic)
4. If yes: Execute all actions in order
5. Move to next rule

**When to add/modify rules:**

- Add new customer notification types
- Change notification timing or channels
- Create seasonal or marketing rules
- Adjust SMS template assignments
- Send alerts to operations Slack

**When to ask for developer help:**

- Need a completely new condition type (we have date_range, option matching, time windows, status codes)
- Need a new action type (we have SMS, Slack, Telegram, database updates, logging)
- YAML validation errors (developers debug syntax)
- Tests fail after your changes

---

### 2. Rule Anatomy

```yaml
rules:
  - name: "Rule Display Name"                 # Human-readable name
    description: "What this rule does"        # Purpose statement
    enabled: true                              # true = active, false = disabled
    conditions:                                # ALL must be true (AND logic)
      - type: "condition_type_1"
        params:
          param_key: "param_value"
      - type: "condition_type_2"
        params:
          param_key: "param_value"
    actions:                                   # Execute IN ORDER
      - type: "action_type_1"
        params:
          param_key: "param_value"
      - type: "action_type_2"
        params:
          param_key: "param_value"
```

**Templating in Messages:**

When writing messages in actions, use `{{ }}` brackets for substitution:

- `{{ booking.name }}` → Customer name
- `{{ booking.phone_masked }}` → Masked phone (010-****-5678)
- `{{ booking.pro_edit_count }}` → Number of edits
- `{{ booking.reserve_at }}` → Reservation datetime
- `{{ booking.status }}` → Booking status code

---

### 3. Available Conditions

#### New Conditions (Story 6.1+)

**`date_range`** - Check if booking is within a date window

```yaml
params:
  start_date: "YYYY-MM-DD"    # First day to match (inclusive)
  end_date: "YYYY-MM-DD"      # Last day to match (inclusive)
```

**Use case:** Holiday promotions, seasonal rules, blackout dates

**Example:**

```yaml
conditions:
  - type: "date_range"
    params:
      start_date: "2025-12-20"
      end_date: "2025-12-31"
```

---

**`has_multiple_options`** - Check if booking has multiple option keywords

```yaml
params:
  keywords: ["keyword1", "keyword2"]  # List of keywords to search for
  min_count: 1                          # Minimum matches required
```

**Use case:** Target customers who selected premium options, multi-service bookings

**Example:**

```yaml
conditions:
  - type: "has_multiple_options"
    params:
      keywords: ["전문가 보정"]  # Korean: "premium", "correction"
      min_count: 1
```

---

#### Existing Conditions

**`booking_not_in_db`** - Detect new bookings not yet processed

```yaml
params: {}  # No parameters
```

---

**`has_option_keyword`** - Check for specific option keywords

```yaml
params:
  keywords: ["keyword1", "keyword2"]  # Match ANY of these keywords
```

---

**`time_before_booking`** - Check if booking is within N hours

```yaml
params:
  hours: 2  # Hours before reservation
```

---

**`current_hour`** - Check if it's a specific hour of day (0-23)

```yaml
params:
  hour: 20  # 8 PM in 24-hour format
```

---

**`booking_status`** - Check booking status code

```yaml
params:
  status: "RC08"  # Completed booking
```

---

**`flag_not_set`** - Check if SMS flag is not sent yet

```yaml
params:
  flag: "remind_sms"  # confirm_sms, remind_sms, option_sms
```

---

### 4. Available Actions

#### New Actions (Story 6.2+)

**`send_slack`** - Send Slack notification to channel

```yaml
params:
  template_name: "template_key"  # From config/slack_templates.yaml
  channel: "#operations"         # Slack channel (with #)
  template_params:               # Variables for template
    bookings: "{{ ... }}"        # See below
```

**Available Slack Templates:**

- `expert_correction_digest` - Lists bookings with expert correction selections
  - Variables: `bookings` (list of booking objects)
  - Outputs: Customer name, masked phone, correction count

- `holiday_event_customer_list` - Lists bookings from promotion period
  - Variables: `bookings` (list of booking objects)
  - Outputs: Customer name, masked phone, reservation date

**Example:**

```yaml
actions:
  - type: "send_slack"
    params:
      template_name: "expert_correction_digest"
      channel: "#operations"
      template_params:
        bookings: "{{ bookings_with_expert_correction }}"
```

---

#### Existing Actions

**`send_sms`** - Send SMS via SENS API

```yaml
params:
  template: "confirmation"  # confirmation, guide, event
  store_specific: false     # Use store-specific template?
```

---

**`create_db_record`** - Create booking in database

```yaml
params: {}  # No parameters
```

---

**`update_flag`** - Update SMS sent flag

```yaml
params:
  flag: "confirm_sms"  # confirm_sms, remind_sms, option_sms
  value: true          # true or false
```

---

**`send_telegram`** - Send Telegram notification

```yaml
params:
  message: "Notification text with {{ booking.name }} substitution"
```

---

**`log_event`** - Write to CloudWatch logs

```yaml
params:
  rule_name: "Rule Name"
  action_name: "Action Name"
  status: "success"    # success, failure, skipped
  message: "What happened"
```

---

### 5. Example Rules from Story 6.1

#### Rule: Expert Correction Slack Digest

**Purpose:** Daily digest of bookings with expert correction requests

**Triggers:** When booking contains "전문가 보정" (expert correction) keyword

**Delivery:** Slack notification to #operations with masked phone

```yaml
- name: "Expert Correction Slack Digest"
  description: "Send daily digest of expert correction requests to operations"
  enabled: true
  conditions:
    - type: "has_option_keyword"
      params:
        keywords: ["전문가 보정"]  # Expert correction in Korean
  actions:
    - type: "send_slack"
      params:
        template_name: "expert_correction_digest"
        channel: "#operations"
        template_params:
          bookings: "{{ bookings_with_expert_correction }}"
```

**To enable/disable:**

```yaml
enabled: true   # Turns rule on
enabled: false  # Turns rule off (no Slack notification sent)
```

**To modify channel:**

```yaml
channel: "#your-channel-name"  # Any Slack channel your bot has access to
```

---

#### Rule: Holiday Event Customer List

**Purpose:** Collect customers with multiple options during holiday period for marketing

**Triggers:** Booking during specific date range AND customer selected 2+ options

**Delivery:** Slack notification to #marketing with customer list

```yaml
- name: "Holiday Event Customer List"
  description: "Collect multi-option customers during holidays for marketing campaigns"
  enabled: false  # Disabled by default - enable during holiday periods
  conditions:
    - type: "date_range"
      params:
        start_date: "2025-12-20"  # Start of holiday period
        end_date: "2025-12-31"    # End of holiday period
    - type: "has_multiple_options"
      params:
        keywords: ["인스타", "네이버"]  # Keywords to match (Korean)
        min_count: 1               # Must match 1+ keywords
  actions:
    - type: "send_slack"
      params:
        template_name: "holiday_event_customer_list"
        channel: "#marketing"
        template_params:
          bookings: "{{ bookings_in_date_range }}"
```

**To enable for a specific holiday:**

1. Update `start_date` and `end_date`
2. Update `keywords` if needed
3. Change `enabled: false` to `enabled: true`
4. Wait for next Lambda execution (every 20 minutes)

**To disable after holiday:**

```yaml
enabled: false  # Rule stops executing immediately
```

---

### 6. Testing Your Changes

**Before making changes:**

1. Backup current `config/rules.yaml`
2. Make a test copy with different rule names

**To validate YAML syntax:**

```bash
# Ask developers to run:
python -m yaml config/rules.yaml
```

**To test a rule:**

1. Set `enabled: true` on your test rule
2. Wait for next Lambda execution (cron runs every 20 minutes)
3. Check CloudWatch logs in AWS Console
4. Look for log entries with your rule name

**How to read logs:**

```json
{
  "timestamp": "2025-10-22T14:30:00Z",
  "level": "INFO",
  "message": "Expert Correction Slack Digest executed",
  "operation": "send_slack",
  "context": {
    "booking_id": "store123_booking456",
    "rule_name": "Expert Correction Slack Digest",
    "status": "success"
  }
}
```

---

### 7. Troubleshooting

**Problem: "YAML syntax error"**

- Check: Indentation (2 spaces per level)
- Use online YAML validator: `yamllint.com`
- Compare with working rules in config/rules.yaml

**Problem: "Rule isn't triggering"**

- Check: Is `enabled: true`?
- Check: Do ALL conditions match? (AND logic)
- Check: Is Lambda running? (Check CloudWatch logs)
- Check: Are booking records being created? (DynamoDB)

**Problem: "Slack message not appearing"**

- Check: Is Slack enabled in settings?
- Check: Is channel name correct (starts with #)?
- Check: Do you have permission to post to that channel?
- Check: Template variables are correct

**To rollback bad rules:**

1. Restore backup: `cp config/rules.yaml.backup config/rules.yaml`
2. Or manually disable: `enabled: false`
3. Wait for next Lambda execution
4. Ask developers to verify in CloudWatch logs

**Emergency: Disable all custom rules**

```yaml
# In config/rules.yaml, add at the very top:
rules:
  # Keep only Rule 1-3 (original system rules)
  # Comment out or delete all Story 6.1 rules
  # Wait for next Lambda execution
```

---

### 8. Operations Checklist

**Before enabling new rule in production:**

- [ ] Rule has been tested in staging environment
- [ ] All conditions have been verified to match test bookings
- [ ] Slack channel exists and bot has access
- [ ] Channel name is spelled correctly (with #)
- [ ] Template variables match available booking fields
- [ ] No syntax errors in YAML
- [ ] `enabled: false` initially, then enable only when ready
- [ ] Backup of `config/rules.yaml` created
- [ ] Team notified about new rule activation
- [ ] CloudWatch logs monitored for 1 hour after activation

**When modifying existing rules:**

- [ ] Backup current `config/rules.yaml`
- [ ] Make one change at a time
- [ ] Test before making next change
- [ ] Document what changed and why
- [ ] Leave `enabled: false` until testing complete
- [ ] Get approval from team before enabling

**Contact developer if:**

- [ ] Need to add completely new condition type
- [ ] Need to add completely new action type
- [ ] YAML validation fails
- [ ] Rule works but produces unexpected output
- [ ] Slack integration not working after verification
- [ ] Need to modify rule engine behavior

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-22 | 2.0 | Story 6.1 complete - Added example rules and business user guide | James (Dev) |
| 2025-10-18 | 1.0 | Epic created from PRD and requirements | Sarah (PO) |
