# Code Review Checklist for Naver SMS Automation Refactoring

This checklist ensures code quality, security, and compliance with the refactoring roadmap.

## General Code Quality

- [ ] Code follows project coding standards (see `docs/architecture/coding-standards.md`)
- [ ] Functions have docstrings explaining purpose, args, returns, raises
- [ ] Comments explain "why", not "what" (code should be self-documenting)
- [ ] No debug print statements left in production code
- [ ] All variables have meaningful names
- [ ] Maximum function length: 50 lines (except tests/handlers)
- [ ] Maximum file length: 500 lines

## Security & Credentials Management

- [ ] **MANDATORY:** No hardcoded credentials in any source files
- [ ] **MANDATORY:** Secrets are retrieved from AWS Secrets Manager only
- [ ] **MANDATORY:** Environment variables are used for configuration only, not secrets
- [ ] No credentials in docstrings, comments, or examples
- [ ] Logging redaction filter active in Lambda handler (`setup_logging_redaction()`)
- [ ] No secret values logged at any log level (DEBUG, INFO, WARNING, ERROR)
- [ ] Private key files are not committed to version control
- [ ] `.env` and `.env.local` files added to `.gitignore`
- [ ] All unit tests use mocked/fixture credentials, not real secrets
- [ ] Security scans (bandit, detect-secrets) pass with no findings

## Testing

- [ ] Unit test coverage >80% (run: `pytest tests/unit/ --cov=src`)
- [ ] All existing tests pass (`pytest tests/ -v`)
- [ ] Tests use mocking (moto for AWS services)
- [ ] Tests use fixtures for data setup/teardown
- [ ] Integration tests skip cleanly when AWS credentials unavailable
- [ ] No test fixtures contain real credentials or sensitive data
- [ ] Test names clearly describe what is being tested

## AWS Integration

- [ ] Credentials fetched using boto3 Secrets Manager client
- [ ] Proper error handling for missing secrets (descriptive RuntimeError)
- [ ] Exponential backoff retry logic for transient failures
- [ ] Maximum retry attempts documented (default: 3)
- [ ] KMS key permissions documented if using custom key
- [ ] IAM role permissions follow principle of least privilege
- [ ] CloudTrail logging enabled for Secrets Manager access

## Documentation

- [ ] Local setup guide exists (`docs/dev/local-setup.md`)
- [ ] AWS CLI profile configuration documented
- [ ] IAM permission requirements documented
- [ ] Bootstrap script includes validation checks
- [ ] README includes link to local setup guide
- [ ] Secrets Manager usage documented in architecture
- [ ] Error messages are descriptive enough for debugging

## Python Code Standards

- [ ] Black formatting: `black src/ tests/ scripts/`
- [ ] isort import ordering: `isort src/ tests/`
- [ ] Flake8 linting: `flake8 src/ tests/`
- [ ] Type hints on function signatures
- [ ] No `import *` statements
- [ ] No global mutable state
- [ ] Exception handling: catch specific exceptions, not bare `except:`
- [ ] No `panic()` or `sys.exit()` in libraries (OK in scripts)

## File & Directory Structure

- [ ] New files placed in correct directories (see `docs/architecture/source-tree.md`)
- [ ] `__init__.py` files exist in all packages
- [ ] Imports use absolute paths (e.g., `from src.config.settings import...`)
- [ ] No circular imports
- [ ] Module names are lowercase with underscores (e.g., `naver_login.py`)
- [ ] Class names are PascalCase (e.g., `NaverAuthenticator`)
- [ ] Function names are snake_case (e.g., `get_naver_credentials()`)

## Git Hygiene

- [ ] Commits have descriptive messages (imperative mood, 50 char limit)
- [ ] No large binaries committed
- [ ] No IDE-specific files (use `.gitignore`)
- [ ] No temporary files or build artifacts
- [ ] No merge conflicts in PR
- [ ] Branch is up to date with main
- [ ] One logical change per commit

## Specific to Story 1.3 (Credentials Migration)

- [ ] **GATE 1:** `src/config/settings.py` exists and implements all three credential getters
  - `get_naver_credentials() → {username, password}`
  - `get_sens_credentials() → {access_key, secret_key, service_id}`
  - `get_telegram_credentials() → {bot_token, chat_id}`

- [ ] **GATE 2:** `src/main.py` uses configuration loader on cold start
  - Calls `setup_logging_redaction()` first
  - Uses `get_naver_credentials()` to initialize authenticator
  - No hardcoded credentials in file

- [ ] **GATE 3:** `scripts/bootstrap_env.sh` validates AWS setup
  - Checks AWS CLI installation
  - Validates credentials configured
  - Validates Secrets Manager access
  - Documents IAM policy requirements

- [ ] **GATE 4:** `docs/dev/local-setup.md` guides local development
  - Step-by-step AWS CLI profile setup
  - IAM user creation with minimal permissions
  - Environment variable configuration
  - Troubleshooting section included

- [ ] **GATE 5:** Security scans pass cleanly
  - `bandit -r src/ --exit-zero` → No HIGH/MEDIUM issues
  - `detect-secrets scan src/` → No credentials detected
  - Evidence captured in `VALIDATION.md`

- [ ] **GATE 6:** Tests use mock credentials only
  - `tests/unit/test_config.py` uses moto for Secrets Manager
  - `tests/integration/test_naver_auth_live.py` skips live tests by default
  - No real AWS credentials required for test suite
  - All tests pass: `pytest tests/ -v`

- [ ] **GATE 7:** Error messages are descriptive
  - Missing secret → "Secret 'X' not found in Secrets Manager"
  - Access denied → "Access denied to secret. Verify IAM permissions"
  - Invalid JSON → "Secret contains invalid JSON: ..."
  - Transient error → "Retrying in Xs (attempt N/3)"

- [ ] **GATE 8:** Logging redaction works
  - SecretRedactionFilter strips values before CloudWatch
  - Secret values never appear in CloudWatch Logs
  - Redacted values show as `***REDACTED***`
  - Works with log message, args tuple, args dict

- [ ] **GATE 9:** Acceptance criteria in VALIDATION.md
  - Story 1.3 section exists in VALIDATION.md
  - All AC items marked as ✅ or documented
  - Test results captured
  - Security scan evidence included

---

## Sign-Off

**Code Review Date:** _______________
**Reviewed By:** _______________
**All Checks Passed:** [ ] Yes [ ] No
**Comments:**

```


```

**Approved for Merge:** [ ] Yes [ ] No
**Next Steps:** _______________
