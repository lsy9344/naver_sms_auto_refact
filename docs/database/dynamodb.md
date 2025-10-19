# DynamoDB Schema and Usage Guide

## Overview

This document describes the DynamoDB tables used by the SMS automation system, their schemas, data validation rules, and setup instructions for local development.

---

## Table: `sms`

**Purpose:** Persistent storage of SMS booking records and flag tracking.

### Schema

| Attribute | Type | Role | Format | Example |
|-----------|------|------|--------|---------|
| `booking_num` | String | Partition Key (HASH) | `{biz_id}_{book_id}` | `1051707_12345` |
| `phone` | String | Sort Key (RANGE) | `010-XXXX-XXXX` | `010-1234-5678` |
| `name` | String | Required | Customer name | `Kim Soo` |
| `booking_time` | String | Required | `YYYY-MM-DD HH:MM:SS` | `2025-10-20 14:30:00` |
| `confirm_sms` | Boolean | Required | SMS sent flag | `true` \| `false` |
| `remind_sms` | Boolean | Required | 2-hour reminder sent | `true` \| `false` |
| `option_sms` | Boolean | Required | Event/option notification sent | `true` \| `false` |
| `option_time` | String | Optional | Reserved for future use | `""` (empty) or ISO8601 |
| `*` (extra fields) | Various | Optional | Dynamic fields for future expansion | `customer_id`, `visit_count`, etc. |

### Billing Mode

**PAY_PER_REQUEST** – Automatic scaling, ideal for variable workloads typical of Lambda functions.

### Indexes

**None currently defined.** Future requirements may add:
- Global Secondary Index (GSI) on `phone` + `booking_time` for scanning by customer or date range
- Obtain Epic-level approval before adding new indexes

### Data Validation Rules

1. **Partition Key (`booking_num`):**
   - Format: `{biz_id}_{book_id}` where `biz_id` and `book_id` are numeric
   - Example: `1051707_12345`
   - Enforced at application level in `src/domain/booking.py`

2. **Sort Key (`phone`):**
   - Format: `010-XXXX-XXXX` (Korean mobile number format)
   - Legacy code may use `010XXXXXXXX` (no hyphens) – normalized on write
   - Enforced at application level via `mask_phone()` utility

3. **Timestamps (`booking_time`):**
   - Format: `YYYY-MM-DD HH:MM:SS` (24-hour local time)
   - Stored as string for consistency with legacy system
   - Parsed by `scan_unnotified_options()` for time-window queries

4. **Boolean Flags (`confirm_sms`, `remind_sms`, `option_sms`):**
   - DynamoDB native Boolean type
   - Defaults to `false` for new bookings
   - Updated via `update_flag()` method

5. **Extra Fields:**
   - Supported for future expansion (customer_id, visit_count, booking_amount, etc.)
   - Stored as top-level attributes in DynamoDB item
   - No schema enforcement – validate at application layer

### TTL (Time-to-Live)

**Not currently enabled.** Historical bookings are retained indefinitely. Future stories may implement TTL for archival.

### Write Throughput Patterns

- **High volume during SMS processing windows** (e.g., 09:00–21:00 KST)
- **Bulk reads via `scan_unnotified_options()`** for finding bookings awaiting option SMS
- **Point updates to flags** (confirm_sms, remind_sms, option_sms)

---

## Table: `session`

**Purpose:** Cache Naver login session cookies for Selenium WebDriver reuse across Lambda invocations.

### Schema

| Attribute | Type | Role | Format | Example |
|-----------|------|------|--------|---------|
| `id` | String | Partition Key (HASH) | Single record identifier | `"1"` |
| `cookies` | String | Cookie data | JSON array of cookie objects | `[{"name":"NID_AUT","value":"..."}]` |

### Design Notes

- **Single-record design:** Stores only one session (id='1') in current implementation
- **Future expansion:** If multi-user support is needed, change partition key to include user ID
- **Upsert semantics:** `save_session()` overwrites existing session (no merge)

### Data Validation Rules

1. **Session ID (`id`):**
   - Currently fixed to `"1"`
   - Used for deterministic key pattern in Lambda functions

2. **Cookies (`cookies`):**
   - Stored as JSON string of Selenium WebDriver cookie objects
   - Each cookie object has: `name`, `value`, optionally `domain`, `path`, `httpOnly`, `expires`
   - Example:
     ```json
     [
       {
         "name": "NID_AUT",
         "value": "abc123...",
         "domain": ".naver.com",
         "path": "/",
         "httpOnly": true
       },
       {
         "name": "NID_SES",
         "value": "def456...",
         "domain": ".naver.com",
         "path": "/",
         "httpOnly": true
       }
     ]
     ```

### TTL (Time-to-Live)

**Not currently enabled.** Sessions are retained until explicitly deleted via `delete_session()`. Production deployments may implement TTL for security.

### Lifetime Management

- **Created:** First successful Naver login (by automation script)
- **Updated:** When re-login succeeds (cookie refresh)
- **Deleted:** When session expires or login fails, triggering re-authentication

---

## Local Development Setup

### Using LocalStack (Docker)

LocalStack provides a local mock of AWS services including DynamoDB.

1. **Install Docker** (if not already installed)
   ```bash
   # macOS: brew install docker
   # Windows/Linux: Download from docker.com
   ```

2. **Start LocalStack**
   ```bash
   docker run -it -p 4566:4566 localstack/localstack:latest
   ```

3. **Create tables via AWS CLI**
   ```bash
   # Set endpoint URL for LocalStack
   export AWS_ENDPOINT_URL=http://localhost:4566

   # Create 'sms' table
   aws dynamodb create-table \
     --table-name sms \
     --attribute-definitions \
       AttributeName=booking_num,AttributeType=S \
       AttributeName=phone,AttributeType=S \
     --key-schema \
       AttributeName=booking_num,KeyType=HASH \
       AttributeName=phone,KeyType=RANGE \
     --billing-mode PAY_PER_REQUEST \
     --region ap-northeast-2 \
     --endpoint-url $AWS_ENDPOINT_URL

   # Create 'session' table
   aws dynamodb create-table \
     --table-name session \
     --attribute-definitions \
       AttributeName=id,AttributeType=S \
     --key-schema \
       AttributeName=id,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region ap-northeast-2 \
     --endpoint-url $AWS_ENDPOINT_URL
   ```

4. **Run tests against LocalStack**
   ```bash
   export AWS_ENDPOINT_URL=http://localhost:4566
   python -m pytest tests/unit/test_database_booking.py -v
   ```

### Using Moto (In-Memory Mock)

Moto is used in unit tests for fast, isolated testing without external services.

```python
from moto import mock_aws
import boto3

@mock_aws
def test_example():
    dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
    dynamodb.create_table(
        TableName="sms",
        KeySchema=[
            {"AttributeName": "booking_num", "KeyType": "HASH"},
            {"AttributeName": "phone", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "booking_num", "AttributeType": "S"},
            {"AttributeName": "phone", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    # ... test code ...
```

---

## Developer Usage Examples

### Get a Booking

```python
from src.database.dynamodb_client import BookingRepository

repo = BookingRepository(table_name="sms")
booking = repo.get_booking("1051707_12345", "010-1234-5678")

if booking:
    print(f"Customer: {booking['name']}")
    print(f"Confirm SMS sent: {booking['confirm_sms']}")
else:
    print("Booking not found")
```

### Create a Booking

```python
booking_data = {
    "booking_num": "1051707_12345",
    "phone": "010-1234-5678",
    "name": "Kim Soo",
    "booking_time": "2025-10-20 14:30:00",
    "confirm_sms": False,
    "remind_sms": False,
    "option_sms": False,
    "option_time": "",
}

try:
    success = repo.create_booking(booking_data)
    if success:
        print("Booking created")
except DynamoDBException as e:
    print(f"Failed to create booking: {e}")
```

### Update a Flag

```python
try:
    success = repo.update_flag(
        "1051707_12345",
        "010-1234-5678",
        "confirm_sms",
        True
    )
    if success:
        print("Flag updated")
except ThrottlingError as e:
    print("DynamoDB throttled – implement retry logic")
```

### Scan for Unnotified Options

```python
unnotified = repo.scan_unnotified_options()
for biz_id, time_window in unnotified.items():
    print(f"Store {biz_id}: option SMS window {time_window['start_time']} to {time_window['end_time']}")
```

### Get Session

```python
from src.database.dynamodb_client import SessionRepository

repo = SessionRepository(table_name="session")
session = repo.get_session()

if session:
    cookies = session.get_cookies_list()
    print(f"Found {len(cookies)} cookies")
    for cookie in cookies:
        print(f"  - {cookie['name']}")
else:
    print("No active session")
```

### Save Session

```python
import json

new_cookies = json.dumps([
    {"name": "NID_AUT", "value": "token123"},
    {"name": "NID_SES", "value": "session456"},
])

try:
    success = repo.save_session(new_cookies)
    if success:
        print("Session saved")
except NetworkError as e:
    print(f"Network error: {e}")
```

---

## Error Handling

The database module raises domain-specific exceptions:

| Exception | Cause | Action |
|-----------|-------|--------|
| `DynamoDBException` | Generic DynamoDB error | Retry or escalate |
| `ThrottlingError` | Provisioned throughput exceeded | Implement backoff and retry |
| `NetworkError` | Connection failure (timeout, DNS) | Check network/infrastructure, retry |
| `PermissionError` | IAM credentials insufficient | Check IAM policy, contact admin |

Example error handling:

```python
from src.database.exceptions import ThrottlingError, NetworkError, PermissionError

try:
    booking = repo.get_booking(prefix, phone)
except ThrottlingError:
    # Implement exponential backoff
    time.sleep(2 ** attempt)
except NetworkError:
    # Log and alert infrastructure team
    logger.error("Network error", error=str(e))
except PermissionError:
    # Alert security team
    logger.error("IAM permission denied", error=str(e))
```

---

## Monitoring and Logging

All database operations emit structured JSON logs to CloudWatch:

```json
{
  "timestamp": "2025-10-20T14:30:00Z",
  "level": "INFO",
  "message": "Booking retrieved successfully",
  "operation": "get_booking",
  "context": {
    "booking_num": "1051707_12345",
    "phone_masked": "010-****-5678"
  },
  "duration_ms": 45.23
}
```

**Searchable fields in CloudWatch Insights:**
- `operation`: get_booking, create_booking, update_flag, scan_unnotified_options, etc.
- `context.phone_masked`: Masked phone for privacy (last 4 digits only)
- `duration_ms`: Query latency
- `error`: Error details if operation failed

---

## Integration Checklist

Before deploying to production, verify:

- [ ] Local DynamoDB tables created with correct schemas
- [ ] Unit tests pass: `pytest tests/unit/test_database_*.py`
- [ ] Coverage > 70%: `pytest --cov=src/database`
- [ ] Integration tests pass: `pytest tests/integration/` (if applicable)
- [ ] Static analysis clean: `black`, `flake8`, `mypy`
- [ ] Secrets Manager credentials configured (Story 1.4)
- [ ] CloudWatch log group created
- [ ] Monitoring dashboard configured (Story 1.5)
- [ ] Runbook updated for on-call team

---

## References

- **Story:** `docs/stories/2.3.extract-dynamodb-operations.md`
- **Domain Models:** `src/domain/booking.py`, `src/domain/session.py`
- **Repository Implementation:** `src/database/dynamodb_client.py`
- **Exception Hierarchy:** `src/database/exceptions.py`
- **Logging Utility:** `src/utils/logger.py`
- **Unit Tests:** `tests/unit/test_database_booking.py`, `tests/unit/test_database_session.py`
- **Architecture:** `docs/brownfield-architecture.md` (section on DynamoDB, line 1350–1450)

