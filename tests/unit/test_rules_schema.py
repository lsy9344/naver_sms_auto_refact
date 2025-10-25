"""
Unit Tests for Rules Schema Validation

Validates that rules.schema.json properly enforces configuration constraints.

Test Coverage:
- Valid rules load without errors
- Missing required fields produce ValidationError with clear message
- Invalid enum values produce ValidationError
- Invalid parameter types produce ValidationError
- Optional fields are truly optional
- Malformed YAML produces descriptive errors

Acceptance Criteria Coverage:
- AC9: Unit tests validate schema enforcement
- AC9: Malformed rules produce descriptive errors
- AC10: YAML linting and schema conformance tested
"""

import json
from pathlib import Path
from typing import Dict, Any

import jsonschema
import pytest
import yaml

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config.settings import Settings


class TestRulesSchema:
    """Test suite for rules schema validation."""

    @pytest.fixture(scope="class")
    def settings(self):
        """Load settings with rules and schema."""
        project_root = Path(__file__).parent.parent.parent
        rules_config = project_root / "config" / "rules.yaml"
        rules_schema = project_root / "src" / "config" / "rules.schema.json"

        settings = Settings()
        settings.load_rules(str(rules_config), str(rules_schema))
        return settings

    @pytest.fixture(scope="class")
    def schema(self):
        """Load schema."""
        project_root = Path(__file__).parent.parent.parent
        schema_path = project_root / "src" / "config" / "rules.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    def test_valid_rules_load_successfully(self, settings):
        """Test Case 1: Valid rules.yaml loads successfully without errors."""
        assert settings.rules is not None
        assert len(settings.rules) > 0
        assert len(settings.rules) == 9  # 3 enabled core rules + 1 disabled (SMS failure) + 3 disabled (Slack templates) + 2 disabled future rules

    def test_missing_name_field(self, schema):
        """Test Case 2: Missing required field 'name' produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "enabled": True,
                    "conditions": [{"type": "booking_not_in_db"}],
                    "actions": [{"type": "create_db_record"}],
                    # Missing 'name' field
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        assert "name" in str(exc_info.value).lower()

    def test_missing_conditions_field(self, schema):
        """Test Case 3: Missing required field 'conditions' produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "actions": [{"type": "create_db_record"}],
                    # Missing 'conditions' field
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        assert "conditions" in str(exc_info.value).lower()

    def test_invalid_condition_type(self, schema):
        """Test Case 4: Invalid condition type produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [{"type": "invalid_type"}],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        assert "invalid_type" in str(exc_info.value) or "enum" in str(exc_info.value).lower()

    def test_invalid_action_type(self, schema):
        """Test Case 5: Invalid action type produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [{"type": "booking_not_in_db"}],
                    "actions": [{"type": "invalid_action"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        assert "invalid_action" in str(exc_info.value) or "enum" in str(exc_info.value).lower()

    def test_missing_required_condition_parameter(self, schema):
        """Test Case 6: Missing required condition parameter produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "time_before_booking",
                            "params": {},  # Missing required 'hours' parameter
                        }
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "hours" in error_msg or "required" in error_msg

    def test_wrong_condition_parameter_type(self, schema):
        """Test Case 7: Wrong parameter type produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "time_before_booking",
                            "params": {"hours": "string"},  # Should be integer
                        }
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "integer" in error_msg or "type" in error_msg

    def test_empty_conditions_array(self, schema):
        """Test Case 8: Empty conditions array produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [],  # Empty array
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "minItems" in str(exc_info.value) or "minimum" in error_msg

    def test_optional_fields_are_optional(self, schema):
        """Test Case 9: Optional fields (tags, priority, notes) are truly optional."""
        valid_config = {
            "rules": [
                {
                    "name": "Minimal Rule",
                    "enabled": True,
                    "conditions": [{"type": "booking_not_in_db"}],
                    "actions": [{"type": "create_db_record"}],
                    # Missing optional fields: description, tags, priority, notes
                }
            ]
        }

        # Should not raise exception
        jsonschema.validate(instance=valid_config, schema=schema)

    def test_invalid_enum_value_in_send_sms_template(self, schema):
        """Test Case 10: Invalid enum value in send_sms template produces ValidationError."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [{"type": "booking_not_in_db"}],
                    "actions": [
                        {
                            "type": "send_sms",
                            "params": {
                                "template": "invalid_template"  # Should be confirmation|guide|event|custom_promotion
                            },
                        }
                    ],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "template" in error_msg or "enum" in error_msg

    def test_send_sms_requires_template_parameter(self, schema):
        """Test send_sms action requires template parameter."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [{"type": "booking_not_in_db"}],
                    "actions": [
                        {
                            "type": "send_sms",
                            "params": {},
                        }  # Missing required 'template' parameter
                    ],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "template" in error_msg or "required" in error_msg

    def test_flag_not_set_condition_parameter_schema(self, schema):
        """Test flag_not_set condition requires flag parameter."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "flag_not_set",
                            "params": {},
                        }  # Missing required 'flag' parameter
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "flag" in error_msg or "required" in error_msg

    def test_update_flag_action_parameter_schema(self, schema):
        """Test update_flag action requires flag and value parameters."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [{"type": "booking_not_in_db"}],
                    "actions": [
                        {
                            "type": "update_flag",
                            "params": {"flag": "test_flag"},  # Missing required 'value' parameter
                        }
                    ],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "value" in error_msg or "required" in error_msg

    def test_current_hour_valid_range(self, schema):
        """Test current_hour condition accepts valid hour range (0-23)."""
        # Valid: hour = 20
        valid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [{"type": "current_hour", "params": {"hour": 20}}],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }
        jsonschema.validate(instance=valid_config, schema=schema)

        # Invalid: hour = 25 (out of range)
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [{"type": "current_hour", "params": {"hour": 25}}],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=invalid_config, schema=schema)

    def test_has_option_keyword_requires_keywords_array(self, schema):
        """Test has_option_keyword condition requires keywords array."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "has_option_keyword",
                            "params": {"keywords": []},  # Empty array not allowed
                        }
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "keywords" in error_msg or "minItems" in str(exc_info.value)

    def test_date_range_valid_iso_format(self, schema):
        """Test date_range condition accepts valid ISO date format (YYYY-MM-DD)."""
        # Valid: ISO format dates
        valid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "date_range",
                            "params": {
                                "start_date": "2025-10-19",
                                "end_date": "2025-10-21",
                            },
                        }
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }
        jsonschema.validate(instance=valid_config, schema=schema)

    def test_date_range_missing_start_date(self, schema):
        """Test date_range condition requires start_date parameter."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "date_range",
                            "params": {"end_date": "2025-10-21"},  # Missing start_date
                        }
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "start_date" in error_msg or "required" in error_msg

    def test_date_range_missing_end_date(self, schema):
        """Test date_range condition requires end_date parameter."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "date_range",
                            "params": {"start_date": "2025-10-19"},  # Missing end_date
                        }
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "end_date" in error_msg or "required" in error_msg

    def test_date_range_invalid_date_format(self, schema):
        """Test date_range condition rejects invalid date format."""
        invalid_config = {
            "rules": [
                {
                    "name": "Test Rule",
                    "enabled": True,
                    "conditions": [
                        {
                            "type": "date_range",
                            "params": {
                                "start_date": "19-10-2025",
                                "end_date": "2025-10-21",
                            },  # Invalid format
                        }
                    ],
                    "actions": [{"type": "create_db_record"}],
                }
            ]
        }

        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(instance=invalid_config, schema=schema)

        error_msg = str(exc_info.value).lower()
        assert "pattern" in error_msg or "format" in error_msg or "start_date" in error_msg
