# Comparison Testing Framework - Developer Guide

**Story 4.2: Implement Comparison Testing Framework**  
**Status:** ✅ Complete  
**Last Updated:** 2025-10-19

## Overview

The Comparison Testing Framework validates functional parity between the legacy and refactored Lambda implementations by replaying production-equivalent workloads through both systems and comparing outputs.

**Key Goals:**
- Guarantee functional parity before traffic migration
- Surface regressions rapidly and automatically
- Maintain >80% test coverage throughout refactoring
- Enable safe, data-driven rollout decisions

---

## Quick Start

### Run Comparison Tests

```bash
# Run all comparison tests
make comparison-test

# Run specific edge case tests
pytest tests/comparison/test_output_parity.py::TestOutputParity::test_parity_new_booking_confirmation -v

# Run all tests including comparison
make test-all

# Run with verbose output
pytest tests/comparison/test_output_parity.py -v --tb=short
```

### View Results

```bash
# Open aggregate summary (after running tests)
cat tests/comparison/results/SUMMARY.md

# View detailed JSON results
cat tests/comparison/results/{booking_id}.json | python -m json.tool

# View markdown diff report
cat tests/comparison/results/{booking_id}.md
```

### Refresh Fixtures

```bash
# Regenerate all fixtures with masking validation
make comparison-refresh

# Or directly run the script
python scripts/comparison/refresh_comparison_dataset.py

# Validate without refreshing
python scripts/comparison/refresh_comparison_dataset.py --validate-only
```

---

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                  Comparison Test Framework                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ComparisonFactory                                          │
│  ├─ Loads production_bookings.json                         │
│  ├─ Builds scenario contexts                               │
│  ├─ Normalizes booking data                                │
│  └─ Provides edge case filtering                           │
│                                                             │
│  ParityValidator                                            │
│  ├─ Executes legacy handler                                │
│  ├─ Executes refactored handler                            │
│  ├─ Wraps with deterministic settings                      │
│  ├─ Validates determinism                                  │
│  └─ Validates idempotency                                  │
│                                                             │
│  OutputNormalizer                                           │
│  ├─ Canonicalizes SMS outputs                              │
│  ├─ Normalizes DynamoDB records                            │
│  ├─ Normalizes Telegram messages                           │
│  └─ Ensures stable ordering                                │
│                                                             │
│  DiffReporter                                               │
│  ├─ Compares canonical outputs                             │
│  ├─ Generates JSON artifacts                               │
│  ├─ Generates markdown summaries                           │
│  └─ Produces aggregate reports                             │
│                                                             │
│  test_output_parity.py (pytest suite)                      │
│  ├─ Parametrized tests by edge case                        │
│  ├─ Aggregate parity validation                            │
│  ├─ Masking enforcement                                    │
│  └─ Determinism validation                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
production_bookings.json
    ↓
ComparisonFactory.build_scenario_contexts()
    ↓
ParityValidator.compare_scenario()
    ├→ execute_legacy_handler()
    │   └→ original_code/lambda_function.py
    │
    └→ execute_refactored_handler()
        └→ src/main.py
            ↓
OutputNormalizer.canonicalize_all_outputs()
    ├→ normalize_sms_outputs()
    ├→ normalize_dynamodb_outputs()
    ├→ normalize_telegram_outputs()
    └→ normalize_action_results()
        ↓
DiffReporter.compare_outputs()
    ├→ _compare_lists()
    ├→ _compare_dicts()
    └→ generate mismatch list
        ↓
DiffReporter.write_reports()
    ├→ {booking_id}.json (structured diff)
    ├→ {booking_id}.md (readable summary)
    └→ SUMMARY.md (aggregate)
```

---

## Fixtures & Test Data

### Fixture Files

```
tests/fixtures/
├── production_bookings.json
│   └─ 15 synthetic booking scenarios
│      └─ 6 edge cases + additional coverage
│
├── production_expected_outputs.json
│   └─ Expected action sequences for each scenario
│
└── dataset_manifest.json
    └─ Version, checksums, validation status
```

### Edge Cases Covered

#### Case 1: New Booking Confirmation
- **Scenario:** Booking not yet in DynamoDB
- **Expected Actions:** create_db_record + send_sms(confirm) + send_telegram
- **Test IDs:** case1_new_booking_001, case1b_new_with_option

#### Case 2: Two-Hour Reminder
- **Scenario:** Booking within 2-hour window + remind_sms not sent
- **Expected Actions:** send_sms(guide) + update_flag(remind_sms)
- **Test IDs:** case2_two_hour_001

#### Case 3: Option Keyword at 8 PM
- **Scenario:** Current hour=20:00 + option keyword + option_sms not sent
- **Expected Actions:** send_sms(event) + update_flag(option_sms)
- **Test IDs:** case3_option_8pm_001, case3b_option_8pm_002, case3c_option_8pm_003
- **Non-Match:** case2c_no_option_match (keyword not in allowed list)

#### Case 4: Cookie Expiry
- **Scenario:** Session cookies expired
- **Expected Actions:** Selenium login + cookie save + booking processing
- **Test IDs:** case4_cookie_refresh_001, case4b_cookie_refresh_002

#### Case 5: Empty Booking Response
- **Scenario:** No bookings returned from API
- **Expected Actions:** Handle gracefully, no errors
- **Test IDs:** case5_empty_response

#### Case 6: High-Volume Processing
- **Scenario:** 50+ bookings in batch
- **Expected Actions:** Deterministic processing, no state leakage
- **Test IDs:** case6_volume_001, case6_volume_002, case6_volume_050

### Adding New Scenarios

**1. Update fixtures:**

```json
{
  "scenario": "CASE X: Description",
  "booking_id": "casex_scenario_001",
  "biz_id": 1051707,
  "book_id": "BKxxxxxxx",
  "customer_phone": "010xxxxxxxx",
  "customer_name": "Test User",
  "booking_time": "2025-10-19T14:00:00",
  "status": "confirmed",
  "option": null,
  "db_record": null,
  "notes": "Scenario description for testing"
}
```

**2. Add expected output:**

```json
"casex_scenario_001": {
  "scenario": "CASE X: Description",
  "expected_actions": [
    {"action_type": "...", "success": true}
  ],
  "expected_sms_count": 1,
  "parity_check_points": [...]
}
```

**3. Run refresh:**

```bash
make comparison-refresh
```

**4. Verify in tests:**

```bash
pytest tests/comparison/test_output_parity.py -v
```

---

## Running Tests

### Local Development

```bash
# Run all comparison tests
pytest tests/comparison/test_output_parity.py -v

# Run specific test class
pytest tests/comparison/test_output_parity.py::TestOutputParity -v

# Run specific parametrized test
pytest tests/comparison/test_output_parity.py::TestOutputParity::test_parity_new_booking_confirmation -v

# Run with coverage
pytest tests/comparison/test_output_parity.py --cov=src --cov-report=html

# Run with detailed output
pytest tests/comparison/test_output_parity.py -vv --tb=long
```

### Interpreting Results

#### Success Output

```
====================== 15 PASSED in 0.45s =======================

✅ All scenarios match between implementations
✅ No critical mismatches detected
✅ All fixtures validated
✅ Masking enforcement passed
```

#### Failure Output

```
FAILED tests/comparison/test_output_parity.py::TestOutputParity::test_all_scenarios_parity

Parity validation failed with critical mismatches:
  - case1_new_booking_001: 2 critical mismatches
  - case3_option_8pm_001: 1 critical mismatch
```

### Viewing Detailed Results

**1. Check aggregate summary:**

```bash
cat tests/comparison/results/SUMMARY.md
```

**2. View specific booking diff:**

```bash
cat tests/comparison/results/case1_new_booking_001.md
```

**3. Inspect JSON artifact:**

```bash
python -m json.tool tests/comparison/results/case1_new_booking_001.json
```

---

## Fixture Refresh Workflow

### Step 1: Prepare

```bash
# Verify current fixtures are valid
python scripts/comparison/refresh_comparison_dataset.py --validate-only

# Review existing fixtures
head -20 tests/fixtures/production_bookings.json
```

### Step 2: Refresh

```bash
# Refresh all fixtures with masking validation
make comparison-refresh

# Script will:
# 1. Load/export booking data
# 2. Apply masking rules
# 3. Validate no PII leakage
# 4. Generate checksums
# 5. Write fresh fixtures
# 6. Clean up temporary files
```

### Step 3: Validate

```bash
# Run full test suite
make test-all

# Or just comparison tests
make comparison-test

# Run masking validation
pytest tests/comparison/test_output_parity.py::TestOutputParity::test_masking_enforcement -v
```

### Step 4: Commit

```bash
# Review changes
git diff tests/fixtures/

# Stage fixtures
git add tests/fixtures/

# Commit with message
git commit -m "chore: refresh comparison fixtures with new edge cases"

# Push
git push origin Epic2
```

---

## Diff Output Interpretation

### Mismatch Report Structure

```markdown
# Comparison Report: case1_new_booking_001

**Status:** FAIL  
**Total Mismatches:** 2  
  - Critical: 1
  - Warnings: 1

## Mismatches

### SMS

🚨 **[0].phone** [CRITICAL]
  - Legacy: `01012345678`
  - Refactored: `010-1234-5678`
  - Phone number format differs

⚠️ **[1].timestamp** [WARNING]
  - Legacy: `2025-10-19T14:00:00`
  - Refactored: `2025-10-19T14:00:00.000Z`
  - Timestamp precision differs (acceptable)
```

### Severity Levels

**CRITICAL (🚨):**
- Booking phone number mismatch
- SMS type mismatch (confirm vs guide vs event)
- DynamoDB flag values differ
- Action execution order differs
- Action count mismatch

**WARNING (⚠️):**
- Timestamp formatting differences
- Optional field presence
- Message content differences (not behavioral)

### Common Mismatches & Fixes

#### Issue: Phone Number Format

**Symptom:**
```
Legacy: 01012345678
Refactored: 010-1234-5678
```

**Fix:** Normalize phone format in OutputNormalizer.normalize_sms_outputs()

```python
def normalize_phone(phone):
    # Remove dashes and spaces
    return phone.replace("-", "").replace(" ", "")
```

#### Issue: Timestamp Precision

**Symptom:**
```
Legacy: 2025-10-19T14:00:00
Refactored: 2025-10-19T14:00:00.000Z
```

**Fix:** Normalize to ISO format (acceptable warning)

#### Issue: Flag Value Type

**Symptom:**
```
Legacy: true (boolean)
Refactored: 1 (integer)
```

**Fix:** Ensure boolean casting in DynamoDB normalization

```python
"confirm_sms": bool(record.get("confirm_sms"))
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File:** `.github/workflows/comparison-tests.yml`

**Triggers:**
- Push to main or Epic2 branches
- Pull requests (automatic)
- Manual trigger (workflow_dispatch)

**Jobs:**
1. **comparison-parity** - Runs comparison test suite
2. **security-check** - Validates no PII in fixtures
3. **coverage** - Generates coverage report

### CI Workflow

```
1. Checkout code
   ↓
2. Load fixtures
   ├─ Verify files exist
   ├─ Parse JSON
   └─ Count bookings
   ↓
3. Run comparison tests
   ├─ test_all_scenarios_parity
   ├─ test_fixture_validation
   └─ test_masking_enforcement
   ↓
4. Generate reports
   ├─ JSON artifacts
   ├─ Markdown summaries
   └─ Coverage report
   ↓
5. Upload artifacts
   ├─ Results (30 day retention)
   └─ Coverage (codecov)
   ↓
6. Comment on PR
   └─ Summary of results
   ↓
7. Fail if critical issues
   └─ Blocks merge
```

### Reading CI Logs

**1. Find job output:**

```
GitHub Actions → comparison-tests workflow → comparison-parity job
```

**2. Check test results:**

```bash
# See parametrized test results
2025-10-19 21:45:00 test_parity_new_booking_confirmation[case1_new_booking_001] PASSED
2025-10-19 21:45:01 test_parity_two_hour_reminder[case2_two_hour_001] PASSED
...
```

**3. Download artifacts:**

```bash
# Click "Artifacts" section
# Download comparison-results.zip
# Extract and review:
tests/comparison/results/
├── SUMMARY.md
└── *.json
```

---

## Troubleshooting

### Tests Pass Locally But Fail in CI

**Cause:** Mocked services behave differently in CI environment

**Solution:**
```bash
# Ensure all fixtures are committed
git add tests/fixtures/
git commit -m "Fix: commit fixtures before CI"

# Run tests in CI container
docker run -it $(docker build -q .) pytest tests/comparison/
```

### Masking Validation Fails

**Cause:** Fixtures contain raw PII

**Solution:**
```bash
# Run validation script
python scripts/comparison/refresh_comparison_dataset.py

# Check for patterns
grep -r "01[0-9]" tests/fixtures/*.json

# Fix: regenerate with masking
make comparison-refresh
```

### Determinism Test Fails

**Cause:** Handler produces different outputs on repeat executions

**Solution:**
1. Check for timestamp dependencies
2. Verify random seed injection
3. Ensure mocked services are deterministic

```python
# In test
scenario["current_time"] = "2025-10-19T14:00:00"  # Fixed time
```

### Fixture Loading Fails

**Cause:** JSON syntax error in fixtures

**Solution:**
```bash
# Validate JSON
python -m json.tool tests/fixtures/production_bookings.json

# Fix syntax errors (missing commas, quotes, etc.)

# Re-run tests
make comparison-test
```

### High Coverage Regression

**Cause:** New code not tested by comparison suite

**Solution:**
1. Add new scenario to fixtures
2. Define expected outputs
3. Refresh fixtures
4. Re-run tests

---

## Escalation Procedures

### When Comparison Tests Fail

#### Step 1: Identify Issue Type

```bash
# Read failure message
# Check if CRITICAL or WARNING

# If CRITICAL (red flag):
#   → Blocks deployment
#   → Requires investigation
#   → Notify maintainers

# If WARNING (proceed with caution):
#   → May be acceptable
#   → Document decision
#   → Proceed with approval
```

#### Step 2: Investigate

```bash
# Review detailed diff
cat tests/comparison/results/{booking_id}.md

# Compare JSON artifacts
diff \
  <(jq .canonical_outputs.legacy tests/comparison/results/{booking_id}.json) \
  <(jq .canonical_outputs.refactored tests/comparison/results/{booking_id}.json)

# Check legacy vs refactored code
git diff original_code/ -- src/
```

#### Step 3: Resolve

**For Behavioral Differences:**
```bash
# Fix refactored code to match legacy behavior
vim src/main.py

# Re-run tests
make comparison-test
```

**For Test Data Issues:**
```bash
# Update fixture
vim tests/fixtures/production_bookings.json

# Refresh all fixtures
make comparison-refresh

# Re-run tests
make comparison-test
```

**For Intentional Improvements:**
```bash
# Update expected outputs to reflect new behavior
vim tests/fixtures/production_expected_outputs.json

# Document change in VALIDATION.md
vim VALIDATION.md

# Create PR with justification
git commit -m "feat: update expected outputs for SMS template improvement"
```

#### Step 4: Notify

```bash
# If PR is blocked:
# 1. Post comment on GitHub PR explaining issue
# 2. Link to comparison results
# 3. Request review from maintainer

# Template:
# "Comparison test failure detected:
#  - Booking: case1_new_booking_001
#  - Issue: Phone number format mismatch
#  - Status: CRITICAL
#  - See: tests/comparison/results/case1_new_booking_001.md"
```

---

## Performance Tuning

### Test Execution Time

```
Baseline: ~2-3 seconds for full suite

To speed up:
1. Run parametrized tests in parallel
   pytest -n auto tests/comparison/

2. Skip masking checks in development
   pytest -m "not masking"

3. Cache fixture loading
   (already implemented in ComparisonFactory)
```

### Reducing CI Time

```yaml
# In .github/workflows/comparison-tests.yml

# Use caching
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}

# Parallelize jobs
comparison-parity:
  runs-on: ubuntu-latest

security-check:
  runs-on: ubuntu-latest

coverage:
  runs-on: ubuntu-latest
  # All run in parallel!
```

---

## Best Practices

### Writing Scenarios

1. **One concept per scenario**
   ```bash
   # Good: One edge case
   case1_new_booking_001
   
   # Bad: Multiple concepts mixed
   case_new_booking_with_option_and_error
   ```

2. **Clear naming**
   ```bash
   # Good
   case3_option_8pm_001
   
   # Bad
   booking_3
   ```

3. **Document intent**
   ```json
   "notes": "Test option SMS trigger at exactly 20:00 (8 PM)"
   ```

### Maintaining Fixtures

1. **Keep fixtures versioned**
   ```bash
   git log --oneline tests/fixtures/
   ```

2. **Update VALIDATION.md when fixtures change**
   ```bash
   # After refresh
   make comparison-refresh
   
   # Update evidence in VALIDATION.md
   vim VALIDATION.md
   
   # Commit together
   git add tests/fixtures/ VALIDATION.md
   git commit -m "chore: refresh fixtures with latest edge cases"
   ```

3. **Review diffs before committing**
   ```bash
   git diff tests/fixtures/
   # Verify no accidental data changes
   ```

---

## Support & Resources

### Documentation

- **Architecture:** `docs/brownfield-architecture.md`
- **Rule Engine:** `docs/testing/rule-engine-tests.md`
- **Validation:** `VALIDATION.md` (this story's section)

### Key Files

```
tests/comparison/
├── comparison_factory.py     # Fixture loading
├── output_normalizer.py      # Output canonicalization
├── diff_reporter.py          # Diff generation
├── parity_validator.py       # Handler execution
└── test_output_parity.py     # Pytest suite

tests/fixtures/
├── production_bookings.json
├── production_expected_outputs.json
└── dataset_manifest.json

scripts/comparison/
└── refresh_comparison_dataset.py   # Fixture refresh
```

### Contact

- **Questions?** Check VALIDATION.md or inline code comments
- **Issues?** Create GitHub issue with comparison test tag
- **PRs?** Link to comparison results in PR description

---

**Last Updated:** 2025-10-19  
**Status:** ✅ Complete & Ready for Production
