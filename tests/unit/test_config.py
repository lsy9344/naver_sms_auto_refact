"""
Unit tests for configuration loader (src/config/settings.py)

Comprehensive tests covering:
- Settings dataclass with all required fields
- Configuration loading with precedence (env > secrets > YAML > defaults)
- Thread-safe singleton caching and reload
- Sensitive field redaction for logging
- Validation with aggregated error messages
- Local file fallback for development
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest
from moto import mock_aws
import boto3
import yaml
from botocore.exceptions import ClientError

from src.config.settings import (
    Settings,
    SecretRedactionFilter,
    ConfigurationError,
    Store,
    get_settings,
    reload_settings,
    get_naver_credentials,
    get_sens_credentials,
    get_telegram_credentials,
    setup_logging_redaction,
    _settings_instance,
)


@pytest.fixture
def mock_secrets():
    """Fixture providing mock secret credentials."""
    return {
        "naver-sms-automation/naver-credentials": {
            "username": "test_user",
            "password": "test_pass123",
        },
        "naver-sms-automation/sens-credentials": {
            "access_key": "test_access_key_12345",
            "secret_key": "test_secret_key_67890",
            "service_id": "test_service_id",
        },
        "naver-sms-automation/telegram-credentials": {
            "bot_token": "test_bot_token_ABC123",
            "chat_id": "test_chat_id_XYZ789",
        },
    }


@pytest.fixture
def mock_stores_yaml():
    """Fixture providing mock stores YAML data."""
    return {
        "default": {"fromNumber": "01055814318"},
        "stores": {
            "1051707": {
                "name": "Test Store 1",
                "fromNumber": "01055814318",
                "templates": {"guide": "1051707"},
            },
            "867589": {
                "name": "Test Store 2",
                "fromNumber": "01022392673",
                "templates": {"guide": "867589"},
            },
        },
    }


@pytest.fixture
def aws_credentials():
    """Fixture for AWS credentials."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-2"


@pytest.fixture(autouse=True)
def cleanup_env():
    """Cleanup environment variables after each test."""
    yield
    # Remove all configuration-related env vars
    for key in list(os.environ.keys()):
        if any(
            x in key
            for x in [
                "NAVER",
                "SENS",
                "TELEGRAM",
                "AWS_REGION",
                "DYNAMODB",
                "USE_LOCAL_SECRETS",
                "LOCAL_SECRETS",
                "CONFIG_DIR",
            ]
        ):
            os.environ.pop(key, None)


class TestSecretRedactionFilter:
    """Tests for SecretRedactionFilter class."""

    def test_redaction_filter_initialization(self):
        """Test filter initializes without secrets."""
        filter_obj = SecretRedactionFilter()
        assert filter_obj.secrets == {}
        assert filter_obj.redacted_values == set()

    def test_redaction_filter_with_secrets(self):
        """Test filter extracts secret values for redaction."""
        secrets = {
            "password": "secret123",
            "api_key": "key456",
        }
        filter_obj = SecretRedactionFilter(secrets)
        assert "secret123" in filter_obj.redacted_values
        assert "key456" in filter_obj.redacted_values

    def test_redaction_filter_nested_secrets(self):
        """Test filter extracts values from nested structures."""
        secrets = {
            "database": {"password": "db_secret"},
            "api": {"keys": ["key1", "key2"]},
        }
        filter_obj = SecretRedactionFilter(secrets)
        assert "db_secret" in filter_obj.redacted_values
        assert "key1" in filter_obj.redacted_values
        assert "key2" in filter_obj.redacted_values

    def test_redaction_filter_redacts_message(self):
        """Test filter redacts secret from log message."""
        secrets = {"password": "secret123"}
        filter_obj = SecretRedactionFilter(secrets)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="User logged in with password: secret123",
            args=(),
            exc_info=None,
        )
        result = filter_obj.filter(record)
        assert result is True
        assert "***REDACTED***" in record.msg
        assert "secret123" not in record.msg

    def test_redaction_filter_ignores_short_strings(self):
        """Test filter doesn't redact very short strings."""
        secrets = {"x": "y", "a": "b"}
        filter_obj = SecretRedactionFilter(secrets)
        # Short values (length <= 3) are not added to redacted_values
        assert filter_obj.redacted_values == set()

    def test_redaction_filter_with_args_tuple(self):
        """Test filter redacts args tuple."""
        secrets = {"api_key": "key123"}
        filter_obj = SecretRedactionFilter(secrets)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="API call with %s",
            args=("key123",),
            exc_info=None,
        )
        result = filter_obj.filter(record)
        assert result is True
        assert record.args[0] == "***REDACTED***"

    def test_redact_value_password_full_mask(self):
        """Test password redaction shows full mask."""
        redacted = SecretRedactionFilter.redact_value(
            "naver_password", "Doolim01!@"
        )
        assert redacted == "****"
        assert "Doolim01!@" not in redacted

    def test_redact_value_key_last_four(self):
        """Test API key redaction shows last 4 chars."""
        redacted = SecretRedactionFilter.redact_value(
            "sens_access_key", "tpAFhfAWvpLqS5ve35Zw"
        )
        assert redacted == "****35Zw"
        assert "tpAFhfAWvpLqS5ve" not in redacted

    def test_redact_value_token_last_four(self):
        """Test token redaction shows last 4 chars."""
        redacted = SecretRedactionFilter.redact_value(
            "telegram_bot_token", "6657330606:AAFX9uYEwkcuuSpQORGpShFTSpG7e8GO1sg"
        )
        # Last 4 chars: O, 1, s, g
        assert redacted == "****O1sg"
        assert "AAFX9uYEwkcuuSpQORGpShFTSpG7e8" not in redacted

    def test_redact_value_short_strings(self):
        """Test short strings are not redacted."""
        redacted = SecretRedactionFilter.redact_value("key", "abc")
        assert redacted == "abc"


class TestSettingsDataclass:
    """Tests for Settings dataclass structure and defaults."""

    def test_settings_initialization(self):
        """Test Settings initializes with default values."""
        settings = Settings()
        assert settings.aws_region == "ap-northeast-2"
        assert settings.dynamodb_table_sms == "sms"
        assert settings.dynamodb_table_session == "session"
        assert settings.naver_username == ""
        assert settings.naver_password == ""
        assert settings.stores == {}
        assert settings.option_keywords == ["네이버", "인스타", "원본"]
        assert settings.rules == []

    def test_settings_with_values(self):
        """Test Settings can be initialized with values."""
        stores = {"1234": Store("1234", "Test", "010123", {"guide": "1234"})}
        settings = Settings(
            naver_username="user",
            naver_password="pass",
            stores=stores,
        )
        assert settings.naver_username == "user"
        assert settings.naver_password == "pass"
        assert settings.stores == stores

    def test_settings_repr_redacts_sensitive_fields(self):
        """Test Settings repr redacts sensitive fields."""
        settings = Settings(
            naver_username="user123",
            naver_password="password123",
            sens_access_key="key_abcd1234",
            telegram_bot_token="token_xyz9999",
        )
        repr_str = repr(settings)
        assert "****" in repr_str
        assert "password123" not in repr_str
        assert "key_abcd1234" not in repr_str
        assert "token_xyz9999" not in repr_str

    def test_settings_repr_shows_store_count(self):
        """Test Settings repr shows store count concisely."""
        stores = {
            "1": Store("1", "Store 1", "010123", {}),
            "2": Store("2", "Store 2", "010456", {}),
        }
        settings = Settings(stores=stores)
        repr_str = repr(settings)
        assert "[2 stores]" in repr_str


class TestSettingsSecretsManager:
    """Tests for Secrets Manager integration."""

    @mock_aws
    def test_get_secret_value_success(self, aws_credentials, mock_secrets):
        """Test successful secret retrieval from Secrets Manager."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = mock_secrets[
            "naver-sms-automation/naver-credentials"
        ]
        client.create_secret(
            Name="naver-sms-automation/naver-credentials",
            SecretString=json.dumps(secret_value),
        )

        result = Settings._get_secret_value(
            "naver-sms-automation/naver-credentials"
        )
        assert result == secret_value

    @mock_aws
    def test_get_secret_value_not_found(self, aws_credentials):
        """Test error when secret not found."""
        with pytest.raises(ConfigurationError) as exc_info:
            Settings._get_secret_value("nonexistent-secret")
        assert "not found in Secrets Manager" in str(exc_info.value)

    @mock_aws
    def test_get_secret_value_invalid_json(self, aws_credentials):
        """Test error when secret contains invalid JSON."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        client.create_secret(Name="bad-secret", SecretString="not-json-{invalid}")

        with pytest.raises(ConfigurationError) as exc_info:
            Settings._get_secret_value("bad-secret")
        assert "invalid JSON" in str(exc_info.value)


class TestSettingsConfigurationLoading:
    """Tests for configuration loading with precedence."""

    def test_load_credentials_from_environment_variables(self):
        """Test loading credentials from environment variables (highest priority)."""
        os.environ["NAVER_USERNAME"] = "env_user"
        os.environ["NAVER_PASSWORD"] = "env_pass"
        os.environ["SENS_ACCESS_KEY"] = "env_access_key"
        os.environ["SENS_SECRET_KEY"] = "env_secret_key"
        os.environ["SENS_SERVICE_ID"] = "env_service_id"
        os.environ["TELEGRAM_BOT_TOKEN"] = "env_bot_token"
        os.environ["TELEGRAM_CHAT_ID"] = "env_chat_id"

        creds = Settings._load_credentials_from_env_or_secrets()
        assert creds["naver"]["username"] == "env_user"
        assert creds["naver"]["password"] == "env_pass"
        assert creds["sens"]["access_key"] == "env_access_key"
        assert creds["telegram"]["bot_token"] == "env_bot_token"

    @mock_aws
    def test_load_credentials_from_secrets_manager(
        self, aws_credentials, mock_secrets
    ):
        """Test loading credentials from Secrets Manager."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        for secret_id, secret_value in mock_secrets.items():
            client.create_secret(
                Name=secret_id, SecretString=json.dumps(secret_value)
            )

        creds = Settings._load_credentials_from_env_or_secrets()
        assert creds["naver"]["username"] == "test_user"
        assert creds["sens"]["access_key"] == "test_access_key_12345"
        assert creds["telegram"]["bot_token"] == "test_bot_token_ABC123"

    def test_load_credentials_no_source_raises_error(self):
        """Test error when no credential source available."""
        with pytest.raises(ConfigurationError) as exc_info:
            Settings._load_credentials_from_env_or_secrets()
        assert "No configuration source found" in str(exc_info.value)

    def test_load_from_local_file_success(self):
        """Test loading secrets from local JSON file."""
        secrets = {
            "naver": {"username": "user", "password": "pass"},
            "sens": {
                "access_key": "key",
                "secret_key": "secret",
                "service_id": "svc",
            },
            "telegram": {"bot_token": "token", "chat_id": "chat"},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(secrets, f)
            temp_file = f.name

        try:
            result = Settings._load_from_local_file(temp_file)
            assert result == secrets
        finally:
            os.unlink(temp_file)

    def test_load_from_local_file_not_found(self):
        """Test error when local file not found."""
        with pytest.raises(ConfigurationError) as exc_info:
            Settings._load_from_local_file("/nonexistent/path/secrets.json")
        assert "not found" in str(exc_info.value)


class TestSettingsYAMLValidation:
    """Tests for YAML file loading and validation."""

    def test_validate_stores_success(self, mock_stores_yaml):
        """Test successful stores validation."""
        stores = Settings._validate_stores(mock_stores_yaml)
        assert len(stores) == 2
        assert stores["1051707"].name == "Test Store 1"
        assert stores["867589"].name == "Test Store 2"

    def test_validate_stores_missing_fields(self):
        """Test error when store missing required fields."""
        invalid_stores = {
            "stores": {
                "1234": {
                    "name": "Test",
                    # Missing 'fromNumber' and 'templates'
                }
            }
        }

        with pytest.raises(ConfigurationError) as exc_info:
            Settings._validate_stores(invalid_stores)
        assert "missing fields" in str(exc_info.value)

    def test_validate_stores_empty(self):
        """Test validation with empty stores."""
        empty_stores = {}
        result = Settings._validate_stores(empty_stores)
        assert result == {}

    def test_validate_stores_aggregated_errors(self):
        """Test aggregated error messages for multiple validation failures."""
        invalid_stores = {
            "stores": {
                "1": {"name": "Store 1"},  # Missing fields
                "2": {"templates": {}},  # Missing fields
            }
        }

        with pytest.raises(ConfigurationError) as exc_info:
            Settings._validate_stores(invalid_stores)
        error_msg = str(exc_info.value)
        # Both store errors should be in the message
        assert "Store '1'" in error_msg
        assert "Store '2'" in error_msg


class TestSettingsSingleton:
    """Tests for thread-safe singleton pattern."""

    def test_get_settings_creates_singleton(self):
        """Test get_settings creates singleton on first call."""
        # Reset singleton
        import src.config.settings as settings_module

        settings_module._settings_instance = None

        os.environ["NAVER_USERNAME"] = "test"
        os.environ["NAVER_PASSWORD"] = "test"
        os.environ["SENS_ACCESS_KEY"] = "test"
        os.environ["SENS_SECRET_KEY"] = "test"
        os.environ["SENS_SERVICE_ID"] = "test"
        os.environ["TELEGRAM_BOT_TOKEN"] = "test"
        os.environ["TELEGRAM_CHAT_ID"] = "test"

        settings1 = get_settings()
        settings2 = get_settings()

        # Should return same instance
        assert settings1 is settings2

    def test_reload_settings_creates_new_instance(self):
        """Test reload_settings creates new instance."""
        import src.config.settings as settings_module

        settings_module._settings_instance = None

        os.environ["NAVER_USERNAME"] = "test"
        os.environ["NAVER_PASSWORD"] = "test"
        os.environ["SENS_ACCESS_KEY"] = "test"
        os.environ["SENS_SECRET_KEY"] = "test"
        os.environ["SENS_SERVICE_ID"] = "test"
        os.environ["TELEGRAM_BOT_TOKEN"] = "test"
        os.environ["TELEGRAM_CHAT_ID"] = "test"

        settings1 = get_settings()
        settings2 = reload_settings()

        # Should be different instances (though same content)
        assert settings1 is not settings2

    def test_get_settings_thread_safety(self):
        """Test get_settings is thread-safe."""
        import src.config.settings as settings_module

        settings_module._settings_instance = None

        os.environ["NAVER_USERNAME"] = "test"
        os.environ["NAVER_PASSWORD"] = "test"
        os.environ["SENS_ACCESS_KEY"] = "test"
        os.environ["SENS_SECRET_KEY"] = "test"
        os.environ["SENS_SERVICE_ID"] = "test"
        os.environ["TELEGRAM_BOT_TOKEN"] = "test"
        os.environ["TELEGRAM_CHAT_ID"] = "test"

        results = []

        def load_settings():
            try:
                settings = get_settings()
                results.append(settings)
            except Exception as e:
                results.append(e)

        # Create multiple threads calling get_settings concurrently
        threads = [threading.Thread(target=load_settings) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # All threads should get the same instance
        assert len(results) == 5
        # All should be Settings instances (no exceptions)
        assert all(isinstance(r, Settings) for r in results)
        # All should be the same instance
        assert all(r is results[0] for r in results)


class TestSettingsModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_naver_credentials_function(self):
        """Test module-level get_naver_credentials function."""
        import src.config.settings as settings_module

        settings_module._settings_instance = None

        os.environ["NAVER_USERNAME"] = "test_user"
        os.environ["NAVER_PASSWORD"] = "test_pass"
        os.environ["SENS_ACCESS_KEY"] = "test"
        os.environ["SENS_SECRET_KEY"] = "test"
        os.environ["SENS_SERVICE_ID"] = "test"
        os.environ["TELEGRAM_BOT_TOKEN"] = "test"
        os.environ["TELEGRAM_CHAT_ID"] = "test"

        result = get_naver_credentials()
        assert result["username"] == "test_user"
        assert result["password"] == "test_pass"

    def test_get_sens_credentials_function(self):
        """Test module-level get_sens_credentials function."""
        import src.config.settings as settings_module

        settings_module._settings_instance = None

        os.environ["NAVER_USERNAME"] = "test"
        os.environ["NAVER_PASSWORD"] = "test"
        os.environ["SENS_ACCESS_KEY"] = "test_key"
        os.environ["SENS_SECRET_KEY"] = "test_secret"
        os.environ["SENS_SERVICE_ID"] = "test_svc"
        os.environ["TELEGRAM_BOT_TOKEN"] = "test"
        os.environ["TELEGRAM_CHAT_ID"] = "test"

        result = get_sens_credentials()
        assert result["access_key"] == "test_key"
        assert result["secret_key"] == "test_secret"
        assert result["service_id"] == "test_svc"

    def test_get_telegram_credentials_function(self):
        """Test module-level get_telegram_credentials function."""
        import src.config.settings as settings_module

        settings_module._settings_instance = None

        os.environ["NAVER_USERNAME"] = "test"
        os.environ["NAVER_PASSWORD"] = "test"
        os.environ["SENS_ACCESS_KEY"] = "test"
        os.environ["SENS_SECRET_KEY"] = "test"
        os.environ["SENS_SERVICE_ID"] = "test"
        os.environ["TELEGRAM_BOT_TOKEN"] = "token_123"
        os.environ["TELEGRAM_CHAT_ID"] = "chat_456"

        result = get_telegram_credentials()
        assert result["bot_token"] == "token_123"
        assert result["chat_id"] == "chat_456"
