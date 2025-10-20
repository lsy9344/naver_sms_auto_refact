# Rules Configuration Guide

**Version:** 1.0  
**Last Updated:** 2025-10-19  
**Author:** Development Team

---

## Section 1: File Structure Explanation

### Overview

The SMS automation system uses a declarative YAML-based rule engine to define when and how SMS messages are sent. All rules are centrally configured in `src/config/rules.yaml` and validated against `src/config/rules.schema.json`.

### YAML Structure

#### Root Level

```yaml
rules:
  - name: "Rule Name"
    enabled: true
    ...
```

- **`rules`** (required): Array of rule definitions
  - Each element defines one automation rule
  - Rules are evaluated sequentially; all matching rules execute
  - Disabled rules are skipped during evaluation

#### Rule Object Structure

```yaml
- name: "Rule Name"
  enabled: true
  description: "What this rule does"
  tags: ["tag1", "tag2"]
  priority: "high"
  notes: "Implementation notes"
  conditions:
    - type: "condition_type"
      params: {...}
  actions:
    - type: "action_type"
      params: {...}
```

**Required Fields:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Unique rule identifier | `"New Booking Confirmation"` |
| `enabled` | boolean | Enable/disable rule without deletion | `true` or `false` |
| `conditions` | array | Conditions that must all be true (AND logic) | See conditions section |
| `actions` | array | Actions to execute when conditions met | See actions section |

**Optional Fields:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `description` | string | Human-readable explanation | `"Send confirmation SMS for new bookings"` |
| `tags` | array | Categorization tags | `["core", "confirmation"]` |
| `priority` | string | Priority level: `high`, `medium`, `low` | `"high"` |
| `notes` | string | Implementation or configuration notes | `"Requires valid SENS API key"` |

### Condition Types

Conditions use **AND logic** - ALL conditions must be true for the rule to match.

#### 1. `booking_not_in_db`

Checks if booking is new (not yet in DynamoDB).

```yaml
conditions:
  - type: "booking_not_in_db"
```

**Parameters:** None

**Example Use Case:** Trigger confirmation SMS for new bookings

---

#### 2. `time_before_booking`

Checks if current time is within X hours before booking time.

```yaml
conditions:
  - type: "time_before_booking"
    params:
      hours: 2
```

**Parameters:**

| Name | Type | Range | Default | Description |
|------|------|-------|---------|-------------|
| `hours` | integer | 0-168 | 2 | Hours before booking |

**Example Use Case:** Send reminder SMS 2 hours before appointment

---

#### 3. `flag_not_set`

Checks if a DynamoDB flag is false (SMS not yet sent).

```yaml
conditions:
  - type: "flag_not_set"
    params:
      flag: "remind_sms"
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `flag` | string | Flag name in DynamoDB booking record |

**Example Use Case:** Prevent duplicate reminder SMS

**Common Flags:**
- `remind_sms` - 2-hour reminder already sent
- `option_sms` - Option/event SMS already sent
- `confirm_sms` - Confirmation SMS already sent

---

#### 4. `current_hour`

Checks if current hour matches specified value (0-23).

```yaml
conditions:
  - type: "current_hour"
    params:
      hour: 20
```

**Parameters:**

| Name | Type | Range | Description |
|------|------|-------|-------------|
| `hour` | integer | 0-23 | Specific hour to match |

**Example Use Case:** Send promotional SMS at 8 PM (hour 20)

---

#### 5. `booking_status`

Checks if booking status matches expected value.

```yaml
conditions:
  - type: "booking_status"
    params:
      status: "confirmed"
```

**Parameters:**

| Name | Type | Valid Values | Description |
|------|------|--------------|-------------|
| `status` | string | `confirmed`, `pending`, `cancelled` | Expected booking status |

**Example Use Case:** Only send SMS for confirmed bookings

---

#### 6. `has_option_keyword`

Checks if booking has one of the specified option keywords.

```yaml
conditions:
  - type: "has_option_keyword"
    params:
      keywords: ["네이버", "인스타", "원본"]
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `keywords` | array of strings | Keywords to match against booking options |

**Example Use Case:** Send special SMS only for bookings with Naver/Instagram referral

---

#### 7. `has_multiple_options`

Checks if booking has at least a minimum number of matching option keywords (Story 6.4).

```yaml
conditions:
  - type: "has_multiple_options"
    params:
      keywords: ["네이버", "인스타", "원본"]
      min_count: 2
```

**Parameters:**

| Name | Type | Range | Description |
|------|------|-------|-------------|
| `keywords` | array of strings | min 1 | Keywords to match against booking options |
| `min_count` | integer | 1+ | Minimum number of keywords that must match |

**Behavior:**
- Counts each option keyword only once even if multiple keywords match within it
- Each option in the booking contributes a maximum of 1 to the match count
- Returns True only when match count >= min_count
- Returns False if booking has no option_keywords
- Returns False if keywords list is empty or invalid

**Example Use Case:** Holiday promo requiring customers to select multiple specific options

```yaml
# Send holiday SMS only for bookings with 2+ special options selected
conditions:
  - type: "has_multiple_options"
    params:
      keywords: ["네이버 Pay", "원본 방식", "프리미엄"]
      min_count: 2
actions:
  - type: "send_sms"
    params:
      template: "custom_promotion"
```

---

#### 8. `date_range`

Checks if booking falls within a specific calendar date range (Story 6.3).

```yaml
conditions:
  - type: "date_range"
    params:
      start_date: "2025-10-19"
      end_date: "2025-10-21"
```

**Parameters:**

| Name | Type | Format | Description |
|------|------|--------|-------------|
| `start_date` | string | YYYY-MM-DD | Range start date (inclusive) |
| `end_date` | string | YYYY-MM-DD | Range end date (inclusive) |

**Behavior:**
- Compares booking's `reserve_at` date (not time) against the range
- Range is inclusive: both start and end dates match
- Supports both naive and timezone-aware datetime objects
- Returns False if `reserve_at` is missing or invalid
- Returns False if dates cannot be parsed

**Example Use Case:** Send promotional SMS only for bookings within campaign dates

```yaml
# Thanksgiving promotion: Oct 19-21
conditions:
  - type: "date_range"
    params:
      start_date: "2025-10-19"
      end_date: "2025-10-21"
actions:
  - type: "send_sms"
    params:
      template: "custom_promotion"
```

---

#### Future Condition Types (Disabled Templates)

The following condition types are defined in schema but not yet implemented:

- `store_id_matches` - Filter by store ID

These are included in the rules template as disabled examples for future enhancement.

### Action Types

Actions are executed **sequentially** when conditions are met. Errors in one action don't prevent others from executing.

#### 1. `send_sms`

Send SMS via SENS API.

```yaml
actions:
  - type: "send_sms"
    params:
      template: "confirmation"
      store_specific: false
```

**Parameters:**

| Name | Type | Valid Values | Required | Description |
|------|------|--------------|----------|-------------|
| `template` | string | `confirmation`, `guide`, `event`, `custom_promotion` | Yes | SMS template name |
| `store_specific` | boolean | `true`, `false` | No | Use store-specific message variants |

**Template Messages:**
- `confirmation` - New booking confirmation
- `guide` - Booking reminder with instructions
- `event` - Event/option promotion
- `custom_promotion` - Custom promotional message

---

#### 2. `create_db_record`

Create new booking record in DynamoDB SMS tracking table.

```yaml
actions:
  - type: "create_db_record"
```

**Parameters:** None

**Effect:** Inserts booking into `sms_tracking` table with initial flags (all false)

---

#### 3. `update_flag`

Update SMS status flag in DynamoDB record.

```yaml
actions:
  - type: "update_flag"
    params:
      flag: "remind_sms"
      value: true
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `flag` | string | Flag name to update |
| `value` | boolean | New flag value |

**Effect:** Prevents duplicate SMS for same booking

---

#### 4. `send_telegram`

Send notification to Telegram.

```yaml
actions:
  - type: "send_telegram"
    params:
      message: "[SMS] Confirmation sent to customer"
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `message` | string | Notification message (max 4096 chars) |

---

#### 5. `send_slack` (Future)

Send notification to Slack. Currently disabled in template rules.

```yaml
actions:
  - type: "send_slack"
    params:
      channel: "#sms-automation"
      message: "SMS sent to customer"
```

---

#### 6. `log_event` (Future)

Log event to CloudWatch. Currently disabled in template rules.

```yaml
actions:
  - type: "log_event"
    params:
      event_type: "sms_sent"
```

---

## Section 2: Editing Guidelines for Rule Authors

### How to Enable/Disable Existing Rules

**To disable a rule temporarily** (without deleting):

```yaml
- name: "Two-Hour Reminder"
  enabled: false  # Change from true to false
  ...
```

**To enable a rule:**

```yaml
- name: "Slack Notification (Template)"
  enabled: true  # Change from false to true
  ...
```

- **Benefits of this approach:** 
  - No code deployment needed
  - Easy rollback by changing `enabled: false` back to `true`
  - Audit trail preserved in Git history

### How to Add New Rule

**Step 1:** Copy the template structure

```yaml
- name: "New Rule Name"
  enabled: true
  description: "What this rule does"
  tags: ["new", "feature"]
  priority: "medium"
  conditions:
    - type: "booking_not_in_db"
  actions:
    - type: "send_sms"
      params:
        template: "confirmation"
```

**Step 2:** Update fields

- **`name`**: Unique identifier (must not duplicate existing rules)
- **`description`**: Clear explanation of when/why rule triggers
- **`conditions`**: List conditions that must all be true
- **`actions`**: List actions to execute in order

**Step 3:** Test configuration

```bash
python scripts/print_rules.py
```

Should show your new rule in the output without errors.

**Step 4:** Commit and deploy

```bash
git add src/config/rules.yaml
git commit -m "Add new rule: [rule name]"
```

### How to Modify Rule Conditions

**Example: Adjust reminder timing from 2 hours to 3 hours**

Before:
```yaml
- name: "Two-Hour Reminder"
  conditions:
    - type: "time_before_booking"
      params:
        hours: 2  # Change this
```

After:
```yaml
- name: "Two-Hour Reminder"  # Or rename to "Three-Hour Reminder"
  conditions:
    - type: "time_before_booking"
      params:
        hours: 3  # Updated
```

**Example: Add additional condition (AND logic)**

Before:
```yaml
conditions:
  - type: "time_before_booking"
    params:
      hours: 2
```

After:
```yaml
conditions:
  - type: "time_before_booking"
    params:
      hours: 2
  - type: "booking_status"  # New condition
    params:
      status: "confirmed"
```

### How to Modify Rule Actions

**Example: Add Telegram notification to existing rule**

Before:
```yaml
actions:
  - type: "send_sms"
    params:
      template: "confirmation"
```

After:
```yaml
actions:
  - type: "send_sms"
    params:
      template: "confirmation"
  - type: "send_telegram"  # New action
    params:
      message: "[SMS] Confirmation sent"
```

**Example: Remove action**

Simply delete the action from the array.

### Common Rule Modification Examples

#### Example 1: Add Rule to Send SMS to Specific Store Only

```yaml
- name: "Store 1051707 Special Promotion"
  enabled: true
  description: "Send promotional SMS to customers at store 1051707"
  tags: ["promotion", "store-specific"]
  priority: "low"
  conditions:
    - type: "store_id_matches"
      params:
        store_ids: [1051707]
    - type: "booking_status"
      params:
        status: "confirmed"
  actions:
    - type: "send_sms"
      params:
        template: "custom_promotion"
```

#### Example 2: Add Rule for Date Range Filtering

```yaml
- name: "November Promotion"
  enabled: true
  description: "November promotional SMS"
  tags: ["promotion", "seasonal"]
  conditions:
    - type: "date_range"
      params:
        start_date: "2025-11-01"
        end_date: "2025-11-30"
    - type: "booking_status"
      params:
        status: "confirmed"
  actions:
    - type: "send_sms"
      params:
        template: "custom_promotion"
```

#### Example 3: Disable Problematic Rule

```yaml
- name: "Evening Option SMS"
  enabled: false  # Disabled due to high opt-out rate
  description: "Send option-related SMS at 8 PM"
  ...
```

---

## Section 3: Testing Workflow

### Quick Local Validation

Before deploying rule changes:

```bash
# 1. Verify YAML syntax and schema
python scripts/print_rules.py

# 2. Run schema validation tests
python -m pytest tests/unit/test_rules_schema.py -v

# 3. Run full test suite
python -m pytest tests/ -v
```

### Interpretation of Test Results

**Schema Validation (`test_rules_schema.py`):**
- ✅ All 15 tests pass = Rules are valid
- ❌ Tests fail = Invalid YAML or schema violation
  - Check error message for which field is invalid
  - Verify against valid examples above

**Example Failure:**
```
FAILED test_invalid_action_type: 'invalid_action' is not one of ['send_sms', 'create_db_record', ...]
```
→ Fix: Use valid action type from the list

### Deployment Checklist

Before committing:

- [ ] `python scripts/print_rules.py` runs without errors
- [ ] Total rules count is expected
- [ ] New/modified rules appear in the summary
- [ ] All condition/action types are recognized
- [ ] Schema validation tests pass
- [ ] No duplicate rule names
- [ ] Git diff shows only intended changes

### Rollback Procedure

If deployed rules cause issues:

**Option 1: Disable problematic rule** (fastest)

```yaml
- name: "Problematic Rule"
  enabled: false  # Disable immediately
```

**Option 2: Revert to previous version**

```bash
git revert HEAD  # Revert last commit
git push        # Deploy previous version
```

---

## Section 4: Versioning and Change Log

### Versioning Strategy

Use semantic versioning for rules configuration:

- **Major (v1.x)**: Breaking rule changes (e.g., remove core rule)
- **Minor (v1.1)**: New rules or safe rule enhancements
- **Patch (v1.0.1)**: Parameter adjustments, bug fixes

### Change Log Format

Add entries to top of `rules.yaml`:

```yaml
# Change Log
# Version 1.1 - 2025-10-20
#   - Added: Store-specific rule for store 1051707
#   - Modified: Increased reminder time from 2h to 3h
#   - Disabled: Evening option SMS (high opt-out rate)
#   - Author: dev-team
#   - Commit: a1b2c3d
#
# Version 1.0 - 2025-10-19
#   - Initial deployment with 3 core rules
#   - Author: dev-team
#   - Commit: 1a2b3c4

rules:
  ...
```

### Auditability

Track changes with Git:

```bash
git log --oneline src/config/rules.yaml
# Shows all commits affecting rules

git show <commit>
# Shows exact changes made in that commit

git blame src/config/rules.yaml
# Shows who last changed each line
```

---

## Section 5: Common Troubleshooting

### Issue: "Rule not executing"

**Symptoms:** SMS not being sent even though conditions seem met

**Diagnosis Steps:**

1. Check rule is enabled:
   ```yaml
   enabled: true  # Should be true
   ```

2. Verify condition parameters match expectations:
   ```yaml
   - type: "time_before_booking"
     params:
       hours: 2  # Is this correct?
   ```

3. Check flag status:
   - If using `flag_not_set`, ensure flag was previously set correctly
   - Verify flag name matches DynamoDB column name

4. Check rule order:
   - Rules are evaluated sequentially
   - If another rule already handled the booking, flags may be set

**Solution:** Use `python scripts/print_rules.py` to verify rule configuration

---

### Issue: "Wrong SMS sent"

**Symptoms:** Customer receives SMS from wrong template

**Root Cause:** Template parameter mismatch

**Fix:**

```yaml
# Wrong
- type: "send_sms"
  params:
    template: "comfirmation"  # Typo

# Correct
- type: "send_sms"
  params:
    template: "confirmation"
```

Valid templates: `confirmation`, `guide`, `event`, `custom_promotion`

---

### Issue: "Duplicate SMS sent"

**Symptoms:** Customer receives same SMS twice

**Root Cause:** Missing or not working `update_flag` action

**Fix:** Ensure flag update action follows SMS action

```yaml
actions:
  - type: "send_sms"
    params:
      template: "guide"
  - type: "update_flag"  # This prevents duplicate
    params:
      flag: "remind_sms"
      value: true
```

---

### Issue: "Schema validation error on deploy"

**Symptoms:** Deployment fails with validation error

**Solution:**

1. Run local validation:
   ```bash
   python scripts/print_rules.py
   ```

2. Read error message carefully:
   - Identify which rule has the problem
   - Identify which field is invalid

3. Compare with examples in Section 1

4. Run tests:
   ```bash
   python -m pytest tests/unit/test_rules_schema.py -v
   ```

---

## Appendix: Full Rule Example

```yaml
# Complete, valid rule example
- name: "Store-Specific Promotion"
  enabled: true
  description: "Send promotional SMS to store 1051707 during November"
  tags: ["promotion", "store-specific", "seasonal"]
  priority: "medium"
  notes: "Requires promotional SMS template configured in SENS"
  conditions:
    - type: "date_range"
      params:
        start_date: "2025-11-01"
        end_date: "2025-11-30"
    - type: "store_id_matches"
      params:
        store_ids: [1051707]
    - type: "booking_status"
      params:
        status: "confirmed"
    - type: "flag_not_set"
      params:
        flag: "promo_sms"
  actions:
    - type: "send_sms"
      params:
        template: "custom_promotion"
        store_specific: true
    - type: "update_flag"
      params:
        flag: "promo_sms"
        value: true
    - type: "send_telegram"
      params:
        message: "[SMS] Promotional SMS sent to store 1051707"
```

---

## Need Help?

**For rule configuration questions:**
- Check Section 1 for syntax reference
- Review examples in Section 2
- Look at troubleshooting in Section 5

**For technical issues:**
- Run validation: `python scripts/print_rules.py`
- Check logs: `tail -f logs/lambda.log`
- Review pull request: `git show <commit>`

**For feature requests:**
- Propose new condition/action type
- File issue with use case
- Submit PR with implementation
