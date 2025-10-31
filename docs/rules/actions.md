# Action Executors - Developer Guide

## Overview

Action executors are pure functions that encapsulate all side effects in the rule engine. They accept an `ActionContext` (immutable) and perform operations like sending SMS, updating the database, and sending notifications.

**Key Principle:** Executors are pure functions - they take input, perform side effects, and return nothing. All state is passed through immutable `ActionContext`.

## Quick Reference

| Executor | Purpose | Status |
|----------|---------|--------|
| `send_sms()` | Send SMS via SENS API | ✅ Implemented |
| `create_db_record()` | Create booking in DynamoDB | ✅ Implemented |
| `update_flag()` | Update SMS tracking flag | ✅ Implemented |
| `send_telegram()` | Send Telegram notification | ✅ Implemented |
| `send_slack()` | Send Slack notification | ✅ Implemented (Slack disabled by default) |
| `log_event()` | Write structured log | ✅ Implemented |

## ActionContext

All executors receive an `ActionContext` - an immutable dataclass containing all dependencies.

```python
@dataclass(frozen=True)
class ActionContext:
    booking: Booking                          # Current booking being processed
    settings_dict: Dict[str, Any]             # Runtime configuration
    db_repo: BookingRepository                # DynamoDB operations
    sms_service: SensSmsClient                # SENS SMS API client
    logger: StructuredLogger                  # Structured logger with redaction
```

### Why Immutable?

- **Thread-safe:** Multiple actions can reuse the same context safely
- **Testable:** No side effects from context mutation
- **Reliable:** Guarantees context isn't modified during execution

## Executor Functions

### 1. send_sms

Sends SMS through SENS API with template selection.

```python
def send_sms(
    context: ActionContext,
    template: str,
    store_specific: bool = False,
) -> None:
```

**Parameters:**
- `context`: ActionContext with booking and services
- `template`: "confirm", "guide", or "event"
- `store_specific`: If True, use store-specific guide template

**Examples:**
```python
# Send confirmation SMS
send_sms(context, template="confirm")

# Send store-specific guide
send_sms(context, template="guide", store_specific=True)

# Send event SMS
send_sms(context, template="event")
```

**Used In Rules:**
```yaml
actions:
  - type: "send_sms"
    params:
      template: "confirm"
```

### 2. create_db_record

Creates a new booking record in DynamoDB with initial SMS flags set to False.

```python
def create_db_record(
    context: ActionContext,
    booking_data: Optional[Dict[str, Any]] = None,
) -> None:
```

**Parameters:**
- `context`: ActionContext with booking and db_repo
- `booking_data`: Optional override dict (for testing)

**Schema Created:**
```
booking_num: Partition key "{biz_id}_{book_id}"
phone: Sort key "010-XXXX-XXXX"
name, booking_time: Customer info
confirm_sms, remind_sms, option_sms: Flags (all False initially)
```

**Used In Rules:**
```yaml
actions:
  - type: "create_db_record"
```

### 3. update_flag

Updates a single SMS tracking flag with idempotency.

```python
def update_flag(
    context: ActionContext,
    flag_name: str,
    flag_value: bool = True,
) -> None:
```

**Parameters:**
- `context`: ActionContext with booking and db_repo
- `flag_name`: "confirm_sms", "remind_sms", or "option_sms"
- `flag_value`: True or False (default: True)

**Idempotency:** If flag already set to desired value, skips update.

**Examples:**
```python
update_flag(context, flag_name="confirm_sms", flag_value=True)
update_flag(context, flag_name="remind_sms", flag_value=True)
update_flag(context, flag_name="option_sms", flag_value=True)
```

**Used In Rules:**
```yaml
actions:
  - type: "update_flag"
    params:
      flag_name: "confirm_sms"
      flag_value: true
```

### 4. send_telegram

Sends messages via Telegram webhook service.

```python
def send_telegram(
    context: ActionContext,
    message: str,
    template_params: Optional[Dict[str, str]] = None,
) -> None:
```

**Parameters:**
- `context`: ActionContext with logger
- `message`: Message text (supports template variables)
- `template_params`: Dict for variable substitution (optional)

**Used In Rules:**
```yaml
actions:
  - type: "send_telegram"
    params:
      message: "New booking from {{booking.name}}"
```

### 5. send_slack

Sends messages via Slack webhook service.

```python
def send_slack(
    context: ActionContext,
    message: str,
    template_params: Optional[Dict[str, str]] = None,
) -> None:
```

**Features:**
- **No-op if disabled:** Checks `settings_dict["slack_enabled"]` (defaults to False)
- **Safe:** Never fails if Slack is misconfigured

**Used In Rules:**
```yaml
actions:
  - type: "send_slack"
    params:
      message: "Booking event: {{booking.name}}"
```

### 6. log_event

Writes structured log entries with rule engine metadata.

```python
def log_event(
    context: ActionContext,
    rule_name: str,
    action_name: str,
    status: str,
    message: str,
) -> None:
```

**Parameters:**
- `context`: ActionContext with logger
- `rule_name`: Name of the rule
- `action_name`: Name of the action
- `status`: "success", "failure", "skipped", etc.
- `message`: Human-readable log message

**Output Format (JSON):**
```json
{
  "timestamp": "2025-10-20T14:00:00Z",
  "level": "INFO",
  "message": "SMS sent successfully",
  "context": {
    "rule": "New Booking Handler",
    "action": "send_sms",
    "booking_id": "1051707_12345",
    "status": "success"
  }
}
```

**Used In Rules:**
```yaml
actions:
  - type: "log_event"
    params:
      rule_name: "My Rule"
      action_name: "send_sms"
      status: "success"
      message: "SMS sent"
```

## Error Handling

All executors wrap exceptions in `ActionExecutionError` with context.

```python
@dataclass
class ActionExecutionError(Exception):
    executor_name: str                      # Which executor failed
    booking_id: str                         # Which booking
    original_error: Exception               # Original exception
    context_data: Dict[str, Any]            # Additional context
```

## Adding New Actions

To add a new action executor:

### 1. Create the Executor Function

```python
def my_new_action(
    context: ActionContext,
    required_param: str,
) -> None:
    """Brief description."""
    try:
        # Perform action
        context.logger.info("Action succeeded")
    except Exception as e:
        raise ActionExecutionError(
            executor_name="my_new_action",
            booking_id=context.booking.booking_num,
            original_error=e,
            context_data={"param": required_param},
        ) from e
```

### 2. Register in `register_actions()`

```python
def my_new_action_wrapper(rule_context: Dict[str, Any], **params: Any) -> None:
    booking = rule_context.get("booking")
    action_context = ActionContext(booking=booking, ...)
    my_new_action(action_context, **params)

engine.register_action("my_new_action", my_new_action_wrapper)
```

### 3. Update Rule YAML

```yaml
actions:
  - type: "my_new_action"
    params:
      required_param: "value"
```

## Testing

### Unit Tests

```python
def test_send_sms_confirm(action_context):
    send_sms(action_context, template="confirm")
    action_context.sms_service.send_confirm_sms.assert_called_once()
```

### Integration Tests

```python
def test_complete_workflow(booking, services_bundle):
    context = ActionContext(booking=booking, ...)
    create_db_record(context)
    send_sms(context, template="confirm")
    update_flag(context, "confirm_sms", True)
    
    record = services_bundle.db_repo.get_booking(...)
    assert record["confirm_sms"] is True
```

## Performance

- **Immutable Context:** O(1) copy via frozen dataclass
- **Idempotent Updates:** Skips unnecessary database writes
- **Error Isolation:** Errors don't cascade to other actions
