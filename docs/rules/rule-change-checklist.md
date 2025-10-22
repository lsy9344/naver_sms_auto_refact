# Rule Change Checklist

**Version:** 1.0  
**Effective Date:** 2025-10-24  
**Purpose:** Standardized process for enabling, disabling, or modifying SMS/Slack automation rules safely

---

## Overview

This checklist ensures all rule changes follow a consistent, safe process:
1. **Pre-Change:** Review, backup, and get approval
2. **Change:** Edit configuration and test
3. **Post-Change:** Monitor execution and validate results

**Why This Matters:**
- Prevents accidental SMS/Slack message floods
- Ensures customer data privacy (PII masking)
- Provides rollback capability if issues occur
- Creates audit trail for compliance

---

## Change Severity Levels

Assess change severity to determine checklist depth:

### Severity: LOW 🟢
- **Changes:** Enable/disable existing rule (no param changes)
- **Time:** 30 minutes
- **Example:** Temporarily disable a rule for testing
- **Approval:** Self-review only
- **Testing:** CloudWatch log verification only

### Severity: MEDIUM 🟡
- **Changes:** Modify rule parameters (channel, keywords, dates)
- **Time:** 2-4 hours
- **Example:** Change Slack channel from #ops to #marketing
- **Approval:** Manager review required
- **Testing:** Full test suite + staging validation

### Severity: HIGH 🔴
- **Changes:** Add new rule or major condition/action changes
- **Time:** 1-2 days
- **Example:** Add new Slack digest rule
- **Approval:** Manager + Tech Lead review
- **Testing:** Full regression + stakeholder sign-off

---

## Phase 1: Pre-Change (Preparation)

### Step 1.1: Document the Change

**Action Items:**

- [ ] Write brief description of what will change
- [ ] Document why the change is needed (business reason)
- [ ] Identify affected customers/stakeholders
- [ ] List expected outcomes (metrics, behavior changes)

**Example Documentation:**

```markdown
## Change: Enable Holiday Event Customer List Rule

**What:** Enable "Holiday Event Customer List" rule in production
**Why:** Marketing team needs customer list for holiday campaign (12/20-12/31)
**Who:** 50-100 customers with multiple options during holiday period
**Expected:** 1-2 Slack messages per day to #marketing channel
**Duration:** Active from 2025-12-20 to 2025-12-31 only
```

### Step 1.2: Review the Change

**For LOW Severity:**
- [ ] Read rule configuration carefully
- [ ] Verify all template variables are correct
- [ ] Check Slack channel name (with # prefix)
- [ ] Verify enabled/disabled flag will be set correctly

**For MEDIUM/HIGH Severity:**
- [ ] Review complete rule definition
- [ ] Check all conditions and parameters
- [ ] Verify no syntax errors
- [ ] Confirm all action definitions are correct
- [ ] Validate Slack template matches available templates
- [ ] Check PII protection (use `phone_masked`, not `phone`)

**Self-Check Questions:**

```
□ Is the rule name descriptive and unique?
□ Does the description explain what the rule does?
□ Do ALL conditions make sense (AND logic)?
□ Are action parameters correct?
□ Is the Slack channel spelled correctly (with #)?
□ Does the template use phone_masked instead of phone?
□ Will this impact the correct customer segment?
□ Have I verified condition types exist?
□ Have I verified action types exist?
```

### Step 1.3: Create Backup

**Action Items:**

```bash
# Create timestamped backup
cp config/rules.yaml config/rules.yaml.backup.$(date +%Y%m%d_%H%M%S)

# Optional: backup Slack templates if modified
cp config/slack_templates.yaml config/slack_templates.yaml.backup.$(date +%Y%m%d_%H%M%S)

# Verify backup exists
ls -la config/rules.yaml.backup.*
```

**Verification:**
- [ ] Backup file created successfully
- [ ] Backup contains current rules
- [ ] Backup timestamp recorded

**Document Backup Location:**
```
Backup created: 2025-10-24_14:30:45
Location: config/rules.yaml.backup.20251024_143045
Backed up by: John Doe
```

### Step 1.4: Request Approval (MEDIUM/HIGH only)

**Approval Checklist:**

For MEDIUM severity changes:
- [ ] Manager reviewed the change
- [ ] Manager confirmed customer impact is acceptable
- [ ] Manager approved the timeline
- [ ] Written approval in Slack or email

For HIGH severity changes:
- [ ] Manager reviewed and approved
- [ ] Tech Lead reviewed rule logic
- [ ] Tech Lead verified no breaking changes
- [ ] Product Owner confirmed business value
- [ ] Written approval in ticket or email

**Approval Template:**

```
FROM: <Your Name>
TO: <Manager Name>
SUBJECT: Approval Needed - Enable Holiday Event Customer List Rule

CHANGE: Enable "Holiday Event Customer List" rule (12/20-12/31)
IMPACT: ~75 SMS messages to #marketing channel
TESTING: Tested in staging, all validations pass
APPROVAL: Manager sign-off required

Manager Response:
[ ] Approved - Proceed with change
[ ] Approved with conditions: ...
[ ] Rejected - Reason: ...

Signature: _______________  Date: __________
```

---

## Phase 2: Make the Change

### Step 2.1: Edit Configuration

**Location:** `config/rules.yaml`

**IMPORTANT:** Edit with care - syntax errors will break all rules

**Step-by-step:**

1. Open `config/rules.yaml` in your text editor
2. Find the rule you're modifying (or add new rule)
3. Make ONLY the intended change
4. **DO NOT** modify other rules or sections
5. **DO NOT** delete or add unintended content

**Example Change:**

```yaml
# BEFORE
- name: "Holiday Event Customer List"
  enabled: false  # ← Change this to true
  description: "..."

# AFTER
- name: "Holiday Event Customer List"
  enabled: true  # ← Changed to true
  description: "..."
```

**Checklist:**

- [ ] Only intended rule was modified
- [ ] No other rules were accidentally changed
- [ ] YAML indentation preserved (2 spaces per level)
- [ ] No accidental deletions
- [ ] File ends with newline

### Step 2.2: Validate YAML Syntax

**Action Items:**

```bash
# Validate YAML and print rules summary
python scripts/print_rules.py
```

**Expected Output:**
```
Rules Configuration:

✓ File: config/rules.yaml
✓ Total rules: 15
✓ Enabled: 13
✓ Disabled: 2

Rule List:
1. [ENABLED] Expert Correction Slack Digest
2. [ENABLED] Holiday Event Customer List  ← Your change
3. [ENABLED] New Booking Confirmation
...
```

**If Validation Fails:**

```
✗ YAML Syntax Error at line 42
  Unexpected character in mapping
```

**Recovery:**
1. Restore backup: `cp config/rules.yaml.backup config/rules.yaml`
2. Review YAML syntax rules (2-space indentation, colons, quotes)
3. Edit again more carefully
4. Re-run validation

**Document Validation Result:**

- [ ] Validation command executed
- [ ] Output shows expected rule state
- [ ] No errors in output
- [ ] Validation date/time recorded: ___________

### Step 2.3: Run Local Testing (MEDIUM/HIGH only)

**Action Items:**

**For Slack-related changes:**

```bash
# Set environment variables for testing
export SLACK_ENABLED=true

# Run schema validation
pytest tests/unit/test_rules_schema.py -v

# Run Slack integration tests
pytest tests/integration/test_slack_integration.py -v
```

**Expected Results:**
```
test_rules_yaml_conforms_to_schema PASSED
test_slack_integration PASSED
======================== 8 passed in 2.15s =========================
```

**For all changes:**

```bash
# Run regression tests
pytest tests/integration/test_rules_regression.py -v --tb=short
```

**Expected Results:**
```
test_booking_001_new_confirmation PASSED
test_booking_002_reminder_sms PASSED
test_booking_006_date_range_within PASSED
...
======================== 14 passed in 8.45s =========================
```

**If Tests Fail:**

1. Read error message carefully
2. Identify which test failed
3. Review your rule change
4. Fix the issue
5. Re-run tests

**Document Test Results:**

- [ ] All schema validation tests passed
- [ ] All Slack tests passed (if applicable)
- [ ] All regression tests passed
- [ ] Test execution date/time: ___________
- [ ] Test environment: Development/Staging

---

## Phase 3: Deployment to Production

### Step 3.1: Commit Configuration Change

**Action Items:**

```bash
# Review changes before committing
git status
git diff config/rules.yaml

# Stage the change
git add config/rules.yaml

# Commit with descriptive message
git commit -m "Enable Holiday Event Customer List rule for marketing campaign

- Rule active 2025-12-20 to 2025-12-31
- Targets customers with 2+ options selected
- Slack delivery to #marketing channel
- Staging tests: all passed
- Approval: [Manager Name] on 2025-10-24"

# Push to repository
git push origin main
```

**Verification:**
- [ ] Changes committed with descriptive message
- [ ] Commit pushed to main branch
- [ ] Commit hash recorded: ___________

### Step 3.2: Monitor Initial Execution

**First Lambda Execution (20-minute cycle):**

```bash
# Watch CloudWatch for your rule execution
# Go to AWS Console → CloudWatch → Log Groups → /aws/lambda/naver-sms-automation

# Search for your rule name
# Filter: "Holiday Event Customer List"

# Expected entries in logs:
# [INFO] Rule: Holiday Event Customer List
# [INFO] Conditions checked: ...
# [INFO] Actions executed: ...
# [INFO] Status: success
```

**Checklist:**

- [ ] Lambda executed within 20 minutes of deployment
- [ ] Log entries contain your rule name
- [ ] Status shows "success" (not "error")
- [ ] Expected action executed (Slack sent, SMS sent, etc.)
- [ ] No error messages in logs
- [ ] Monitoring time: 10-15 minutes after execution

**Document First Execution:**

```
First Execution Results:
- Timestamp: 2025-10-24 14:50:00 UTC
- Status: SUCCESS
- Bookings processed: 5
- Slack messages sent: 1 to #marketing
- No errors detected
```

---

## Phase 4: Post-Change Monitoring & Validation

### Step 4.1: Active Monitoring (First 24 Hours)

**Monitoring Schedule:**

| Time | Action | Check |
|------|--------|-------|
| 0 min | Enable rule | Lambda ready |
| 20 min | First execution | Logs show success |
| 1 hour | Check results | Slack/SMS sent correctly |
| 4 hours | Trend check | No errors, expected volume |
| 24 hours | Full review | Customer feedback none, metrics normal |

**What to Monitor in CloudWatch:**

```json
✓ Rule execution count (should match expected frequency)
✓ No error messages with your rule name
✓ Action execution status (all "success")
✓ Processing time (should be <1 second)
✓ Slack delivery status (if applicable)
```

**Red Flags to Watch For:**

```
❌ Error messages in logs
❌ Rule not executing (no log entries)
❌ Same customer getting duplicate messages
❌ Slack messages with wrong content/format
❌ Abnormal execution frequency
❌ Database errors related to your rule
```

**Monitoring Checklist:**

- [ ] Checked logs 20 minutes after deployment
- [ ] Checked logs 1 hour after deployment
- [ ] Checked logs 4 hours after deployment
- [ ] Checked logs at 24 hours
- [ ] No errors detected
- [ ] Expected behavior confirmed
- [ ] Customer feedback collected (if applicable)

**Document Monitoring Results:**

```
24-Hour Monitoring Report:

✅ 0-20 min: Lambda ready, rule deployed
✅ 20 min: First execution successful, 5 bookings matched
✅ 1 hour: 1 Slack message sent to #marketing with 5 customers
✅ 4 hours: 2nd execution successful, 3 bookings matched
✅ 24 hours: Normal execution pattern, no errors

Customer Feedback: None received
Performance: Normal (execution time 200-300ms)
```

### Step 4.2: Validate Against Acceptance Criteria

**Checklist:**

- [ ] Rule executes at expected frequency (every 20 minutes)
- [ ] Conditions correctly identify matching bookings
- [ ] Actions execute in order (SMS sends before Slack, etc.)
- [ ] Slack messages include all required data
- [ ] Phone numbers are masked (PII protection)
- [ ] No customer received duplicate messages
- [ ] No unexpected side effects on other rules
- [ ] CloudWatch logs are clear and helpful

**Verification Script (if provided):**

```bash
# Run post-deployment validation
python scripts/validate_rule_change.py \
  --rule-name "Holiday Event Customer List" \
  --expected-matches 75 \
  --expected-slacks 2 \
  --date-range "2025-12-20:2025-12-31"
```

### Step 4.3: Stakeholder Sign-Off (HIGH severity only)

**Communication:**

```
TO: Marketing Team
SUBJECT: Rule Deployment Complete - Holiday Event Customer List

The "Holiday Event Customer List" rule has been successfully deployed and tested.

Status: ✅ LIVE
Activation Date: 2025-10-24
Active Period: 2025-12-20 to 2025-12-31

Expected Behavior:
- 1-2 Slack messages per day to #marketing
- Contains customers with 2+ options selected
- Includes masked phone numbers for privacy

Monitoring: Active for 24 hours, no issues detected

Questions? Contact: ops-team@company.com
```

**Approval Sign-Off:**

- [ ] Stakeholder verified rule is working
- [ ] Stakeholder confirmed business outcome is met
- [ ] Written approval received
- [ ] Date/time recorded: ___________

---

## Phase 5: Ongoing Maintenance

### Step 5.1: Weekly Monitoring

**Weekly Checklist:**

- [ ] Rule still executing (check recent logs)
- [ ] No sustained error patterns
- [ ] Execution frequency normal
- [ ] No customer complaints
- [ ] Slack messages appearing as expected
- [ ] Performance metrics stable

### Step 5.2: Rule Modification

**If You Need to Modify:**

1. **Go back to Phase 1** (Pre-Change)
2. Create new backup with new timestamp
3. Make only the intended change
4. Run validation again
5. Test in staging if possible
6. Follow monitoring procedures again

**DO NOT:** Make multiple changes at once without testing each change.

### Step 5.3: Permanent Disabling

**If Rule Should Be Permanently Off:**

1. Change `enabled: false`
2. Test (should not execute)
3. Commit with explanation
4. Leave in config (for history)
5. Document why in commit message

**DO NOT:** Delete rules from config - disable instead.

---

## Emergency Rollback Procedure

**Use this if rule causes critical issues (e.g., message flood, wrong customers):**

### Immediate Actions (First 5 Minutes)

```bash
# Option 1: Disable the rule immediately (fastest)
# Edit config/rules.yaml and change:
# enabled: true  →  enabled: false

# Then validate and commit
python scripts/print_rules.py
git add config/rules.yaml
git commit -m "ROLLBACK: Disable [rule name] due to critical issue"
git push
```

**OR**

```bash
# Option 2: Restore from backup (if rule is severely broken)
cp config/rules.yaml.backup config/rules.yaml
python scripts/print_rules.py
git add config/rules.yaml
git commit -m "ROLLBACK: Restore config to backup due to critical issue"
git push
```

### Post-Rollback Actions

- [ ] Rule disabled or reverted
- [ ] Validation confirms revert was successful
- [ ] Incident documented with timestamp
- [ ] Root cause analysis started
- [ ] Stakeholders notified
- [ ] Team meeting scheduled to review issue

**Rollback Notification Template:**

```
INCIDENT: Rule Change Rollback

Rule: [Rule Name]
Change Date: [Date]
Rollback Date: [Date]
Reason: [Specific issue - e.g., message flood]

Actions Taken:
✓ Rule disabled immediately
✓ Configuration reverted to stable state
✓ Lambda redeployed with previous config

Status: Back to normal operation
Impact: No customer-facing issues
Next Steps: Root cause analysis ongoing
```

---

## Troubleshooting Guide

### Problem: Rule not executing

**Checklist:**

```
□ Is enabled: true in the config?
□ Does the rule appear in print_rules.py output?
□ Are all conditions met for test data?
□ Is Lambda running? (Check CloudWatch)
□ Are booking records being created? (Check DynamoDB)
```

**Solution:**
1. Enable rule in config
2. Run validation: `python scripts/print_rules.py`
3. Check CloudWatch logs for condition evaluation
4. Test with sample data

### Problem: Slack messages not appearing

**Checklist:**

```
□ Is Slack enabled? (SLACK_ENABLED env var)
□ Is channel name spelled correctly (with #)?
□ Does bot have permission to post to channel?
□ Is template name spelled correctly?
□ Are template variables correct?
```

**Solution:**
1. Verify channel name in rule config
2. Check Slack workspace permissions
3. Run Slack integration test: `pytest tests/integration/test_slack_integration.py`
4. Check CloudWatch for template rendering errors

### Problem: Duplicate messages to same customer

**Checklist:**

```
□ Is there a flag check to prevent duplicates?
□ Is the flag being set after action?
□ Are multiple rules matching same booking?
□ Is rule executing multiple times?
```

**Solution:**
1. Add `flag_not_set` condition if needed
2. Add `update_flag` action after action
3. Disable other rules that might match
4. Test with sample booking data

### Problem: Wrong customers receiving messages

**Checklist:**

```
□ Do all conditions correctly identify target customers?
□ Are keywords spelled correctly in condition?
□ Is date_range using correct dates?
□ Are you testing with correct sample data?
□ Is condition using correct logic (all must match)?
```

**Solution:**
1. Review rule conditions carefully
2. Test conditions with sample data
3. Print rules to verify config loaded
4. Check CloudWatch for condition evaluation details

---

## Document Template: Rule Change Record

**Use this to document your change:**

```markdown
# Rule Change Record

**Date:** 2025-10-24
**Changed By:** John Doe
**Manager Approval:** Jane Smith
**Severity:** [LOW / MEDIUM / HIGH]

## Change Description
[What rule was changed and why]

## Configuration Changes
- Rule: [Rule Name]
- Modification: [What changed]
- Previous: [Old config]
- New: [New config]

## Testing Results
- [ ] YAML validation: PASSED
- [ ] Schema validation: PASSED
- [ ] Slack tests: PASSED (if applicable)
- [ ] Regression tests: PASSED
- Test date/time: ___________

## Deployment
- Commit hash: ___________
- Deployed by: ___________
- Deployment time: ___________

## Monitoring (First 24 Hours)
- [ ] 20-min check: ✅ PASSED
- [ ] 1-hour check: ✅ PASSED
- [ ] 4-hour check: ✅ PASSED
- [ ] 24-hour check: ✅ PASSED

## Final Status
✅ COMPLETED - Rule working as expected
- Execution frequency: Normal
- Customer impact: As expected
- Performance: Normal
- No errors detected

**Sign-Off:** John Doe, 2025-10-24 16:30 UTC
```

---

## Reference Links

- **Rule Management Guide:** `docs/epics/epic-6-post-mvp-enhancements.md#business-user-rule-management-guide`
- **Slack Integration:** `docs/testing/slack-integration.md`
- **Rules Configuration:** `docs/rules/rules-config.md`
- **Testing Guide:** `docs/testing/rule-engine-tests.md`
- **CloudWatch Logs:** AWS Console → CloudWatch → Log Groups → `/aws/lambda/naver-sms-automation`

---

## Questions or Issues?

**Need Help?**
- Slack: #operations-rules
- Email: dev-team@company.com
- GitHub: File issue with label `rule-management`

**Checklist Version:** 1.0 (2025-10-24)
**Last Updated:** 2025-10-24
**Maintained By:** Operations + Development Team
