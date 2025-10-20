"""
Unit tests for configuration loader (src/config/settings.py)

Tests covering:
- SecretRedactionFilter for logging
- Settings class for credential management
- Secrets Manager integration
- Local file fallback for development
"""

import json
import logging
import os
import tempfile
from unittest.mock import patch

import pytest
from moto import mock_aws
import boto3
from botocore.exceptions import ClientError

from src.config.settings import (
    Settings,
    SecretRedactionFilter,
    ConfigurationError,
    get_naver_credentials,
    get_sens_credentials,
    get_telegram_credentials,
    setup_logging_redaction,
    NAVER_SECRET_ID,
    SENS_SECRET_ID,
    TELEGRAM_SECRET_ID,
    USE_LOCAL_SECRETS,
    LOCAL_SECRETS_FILE,
)


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


class TestSettingsInitialization:
    """Tests for Settings class initialization."""

    def test_settings_initialization_default_region(self):
        """Test Settings initializes with default region."""
        settings = Settings()
        assert settings.region_name == "ap-northeast-2"
        assert settings.rules == []
        assert settings.rules_schema == {}
        assert settings._secrets_cache == {}

    def test_settings_initialization_custom_region(self):
        """Test Settings initializes with custom region."""
        settings = Settings(region_name="us-east-1")
        assert settings.region_name == "us-east-1"

    def test_settings_lazy_initializes_secrets_client(self):
        """Test Settings lazily initializes secrets client."""
        settings = Settings()
        assert settings.secrets_client is None
        client = settings._get_secrets_client()
        assert client is not None
        # Second call should return same client
        assert settings._get_secrets_client() is client


class TestSecretsManagerIntegration:
    """Tests for Secrets Manager integration."""

    @mock_aws
    def test_get_secret_value_success(self, aws_credentials):
        """Test successful secret retrieval from Secrets Manager."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = {"username": "test_user", "password": "test_pass123"}
        client.create_secret(
            Name=NAVER_SECRET_ID,
            SecretString=json.dumps(secret_value),
        )

        result = Settings._get_secret_value(NAVER_SECRET_ID)
        assert result == secret_value

    @mock_aws
    def test_get_secret_value_not_found(self, aws_credentials):
        """Test error when secret not found."""
        with pytest.raises(RuntimeError) as exc_info:
            Settings._get_secret_value("nonexistent-secret")
        assert "not found" in str(exc_info.value)

    @mock_aws
    def test_get_secret_value_invalid_json(self, aws_credentials):
        """Test error when secret contains invalid JSON."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        client.create_secret(Name="bad-secret", SecretString="not-json-{invalid}")

        with pytest.raises(RuntimeError) as exc_info:
            Settings._get_secret_value("bad-secret")
        assert "invalid JSON" in str(exc_info.value)


class TestCredentialsLoading:
    """Tests for credential loading functions."""

    @mock_aws
    def test_load_naver_credentials_fallback_on_secrets_manager_empty(self, aws_credentials):
        """Test loading Naver credentials falls back to Secrets Manager."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = {"username": "sm_user", "password": "sm_pass"}
        client.create_secret(Name=NAVER_SECRET_ID, SecretString=json.dumps(secret_value))
        os.environ["NAVER_USERNAME"] = ""
        os.environ["NAVER_PASSWORD"] = ""

        result = Settings.load_naver_credentials()
        assert result["username"] == "sm_user"
        assert result["password"] == "sm_pass"

    @mock_aws
    def test_load_naver_credentials_success_from_secrets_manager(self, aws_credentials):
        """Test loading Naver credentials from Secrets Manager."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = {"username": "sm_user", "password": "sm_pass"}
        client.create_secret(Name=NAVER_SECRET_ID, SecretString=json.dumps(secret_value))

        result = Settings.load_naver_credentials()
        assert result == secret_value

    @mock_aws
    def test_load_sens_credentials_success(self, aws_credentials):
        """Test loading SENS credentials."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = {
            "access_key": "test_access_key",
            "secret_key": "test_secret_key",
            "service_id": "test_service_id",
        }
        client.create_secret(Name=SENS_SECRET_ID, SecretString=json.dumps(secret_value))

        result = Settings.load_sens_credentials()
        assert result == secret_value

    @mock_aws
    def test_load_sens_credentials_missing_keys(self, aws_credentials):
        """Test error when SENS credentials missing required keys."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = {"access_key": "test_key"}  # Missing secret_key and service_id
        client.create_secret(Name=SENS_SECRET_ID, SecretString=json.dumps(secret_value))

        with pytest.raises(RuntimeError) as exc_info:
            Settings.load_sens_credentials()
        assert "missing required keys" in str(exc_info.value)

    @mock_aws
    def test_load_telegram_credentials_success(self, aws_credentials):
        """Test loading Telegram credentials."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = {"bot_token": "test_bot_token", "chat_id": "test_chat_id"}
        client.create_secret(Name=TELEGRAM_SECRET_ID, SecretString=json.dumps(secret_value))

        result = Settings.load_telegram_credentials()
        assert result == secret_value


class TestLocalFileLoading:
    """Tests for local file fallback."""

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

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(secrets, f)
            temp_file = f.name

        try:
            result = Settings._load_from_local_file(temp_file)
            assert result == secrets
        finally:
            os.unlink(temp_file)

    def test_load_from_local_file_not_found(self):
        """Test error when local file not found."""
        with pytest.raises(RuntimeError) as exc_info:
            Settings._load_from_local_file("/nonexistent/path/secrets.json")
        assert "not found" in str(exc_info.value)

    def test_load_from_local_file_invalid_json(self):
        """Test error when local file contains invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not-valid-json{invalid}")
            temp_file = f.name

        try:
            with pytest.raises(RuntimeError) as exc_info:
                Settings._load_from_local_file(temp_file)
            assert "invalid JSON" in str(exc_info.value)
        finally:
            os.unlink(temp_file)


class TestRulesLoading:
    """Tests for rules loading from YAML configuration."""

    def test_load_rules_success(self):
        """Test loading rules from valid YAML and schema."""
        # Create temp schema file
        schema = {
            "type": "object",
            "properties": {"rules": {"type": "array"}},
            "required": ["rules"],
        }
        rules_config = {"rules": [{"id": "test", "conditions": [], "actions": []}]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as schema_file:
            json.dump(schema, schema_file)
            schema_path = schema_file.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as rules_file:
            import yaml

            yaml.dump(rules_config, rules_file)
            rules_path = rules_file.name

        try:
            settings = Settings()
            settings.load_rules(rules_path, schema_path)
            assert settings.rules == [{"id": "test", "conditions": [], "actions": []}]
        finally:
            os.unlink(schema_path)
            os.unlink(rules_path)

    def test_load_rules_file_not_found(self):
        """Test error when rules file not found."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            schema_path = f.name

        try:
            settings = Settings()
            with pytest.raises(FileNotFoundError):
                settings.load_rules("/nonexistent/rules.yaml", schema_path)
        finally:
            os.unlink(schema_path)


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_get_naver_credentials_function_exists(self):
        """Test get_naver_credentials function exists and is callable."""
        assert callable(get_naver_credentials)

    def test_get_sens_credentials_function_exists(self):
        """Test get_sens_credentials function exists and is callable."""
        assert callable(get_sens_credentials)

    def test_get_telegram_credentials_function_exists(self):
        """Test get_telegram_credentials function exists and is callable."""
        assert callable(get_telegram_credentials)

    def test_setup_logging_redaction_function_exists(self):
        """Test setup_logging_redaction function exists and is callable."""
        assert callable(setup_logging_redaction)
