# SMS Service Module Guide

Story 2.2 extracts the legacy `Sens_sms` implementation into `src/notifications/sms_service.py` while keeping request signatures, headers, and payloads byte-identical to the original behaviour.

## Module Overview

- Entry point class: `notifications.sms_service.SensSmsClient`
- Dependencies:
  - `config/sms_templates.yaml` – canonical SMS content
  - `config/stores.yaml` – store metadata and phone mappings
  - `config/settings.Settings` – loads SENS credentials (Secrets Manager or local override)
  - `utils.logger.get_logger` – structured logging with masking

### Public API

```python
client = SensSmsClient()
client.send_confirm_sms(phone, store_id=None)
client.send_guide_sms(store_id, phone)
client.send_event_sms(phone, store_id=None)
```

- `send_confirm_sms` – booking confirmation, same payload as legacy `send_confirm_sms`
- `send_guide_sms` – store-specific templates selected by `stores.yaml -> templates.guide`
- `send_event_sms` – event/review reminder identical to legacy implementation

Each method logs start/end events via the structured logger and masks phone numbers (`*******1234`) before emitting.

## Configuration Files

### `config/sms_templates.yaml`

- `templates.booking_confirm` – global confirmation template (`|` preserves trailing newline)
- `templates.event` – event/reminder template (`|-` removes trailing newline to match legacy bytes)
- `templates.guide.stores` – per-store guide templates
  - Uses `|2` for templates whose legacy variant ended with a newline
  - Uses `|-2` where the legacy string terminated without a newline
  - Content is character-for-character identical to `original_code/sens_sms.py`

### `config/stores.yaml`

```yaml
default:
  fromNumber: "<fallback phone>"
stores:
  "<store_id>":
    name: "<friendly name>"
    fromNumber: "<store caller ID>"
    templates:
      guide: "<key in sms_templates.guide.stores>"
```

- Default caller ID falls back to `SENS_DEFAULT_FROM` environment variable if provided
- Store names align with the locations referenced in legacy guide messages
- Special-case store `867589` retains the alternate caller ID (`01022392673`)

## Environment Overrides

- `SENS_DEFAULT_FROM` – overrides the default caller ID (preserves legacy behaviour)
- `SENS_FROM_MAP_JSON` – optional JSON of `{store_id: fromNumber}` applied at runtime
  - Invalid JSON triggers a warning and falls back to config values
- `SENS_ACCESS_KEY`, `SENS_SECRET_KEY`, `SENS_SERVICE_ID` – populate `Settings.load_sens_credentials` (Secrets Manager preferred)

## Adding or Updating Stores

1. **Add template content**
   - Append new entry under `templates.guide.stores` with exact message content
   - Choose `|2` (retain newline) or `|-2` (strip newline) to match legacy formatting requirements
2. **Register store metadata**
   - Add the store to `config/stores.yaml` with `fromNumber` and `templates.guide` key
3. **Update tests**
   - Extend `tests/fixtures/sens/legacy_payloads.json` with captured legacy payload
   - Add store ID to parametrised cases in `tests/unit/test_sms_service.py`

## Testing & Validation

- `pytest tests/unit/test_sms_service.py` – parity tests comparing headers/payloads against `legacy_payloads.json` fixtures (confirm, event, all guide templates)
- `bandit -r src/notifications/sms_service.py` – static analysis (no issues as of 2025-10-18)
- `detect-secrets scan src/notifications/sms_service.py` – no secret material detected (2025-10-18)

All parity tests must pass before deprecating `original_code/sens_sms.py`. The legacy module remains in place for regression comparison and emergency rollback references.
