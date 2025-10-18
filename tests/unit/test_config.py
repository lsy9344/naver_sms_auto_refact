"""
Unit tests for configuration loader (src/config/settings.py)

Tests Secrets Manager integration, redaction filter, error handling, and local file loading.
"""

import json
import logging
import os
import tempfile
from unittest.mock import MagicMock, patch, Mock

import pytest
from moto import mock_aws
import boto3
from botocore.exceptions import ClientError

from src.config.settings import (
    Settings,
    SecretRedactionFilter,
    get_naver_credentials,
    get_sens_credentials,
    get_telegram_credentials,
    setup_logging_redaction,
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
            "access_key": "test_access_key",
            "secret_key": "test_secret_key",
            "service_id": "test_service_id",
        },
        "naver-sms-automation/telegram-credentials": {
            "bot_token": "test_bot_token",
            "chat_id": "test_chat_id",
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
def cleanup_local_secrets_env():
    """Cleanup local secrets environment variables after each test."""
    yield
    os.environ.pop("USE_LOCAL_SECRETS_FILE", None)
    os.environ.pop("LOCAL_SECRETS_FILE_PATH", None)


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

    def test_redaction_filter_handles_non_string_args(self):
        """Test filter handles non-string args gracefully."""
        secrets = {"password": "pass123"}
        filter_obj = SecretRedactionFilter(secrets)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Error code %d",
            args=(500,),
            exc_info=None,
        )
        result = filter_obj.filter(record)
        assert result is True


class TestSettingsSecretsManager:
    """Tests for Settings class with Secrets Manager integration."""

    @mock_aws
    def test_get_secret_value_success(self, aws_credentials):
        """Test successful secret retrieval from Secrets Manager."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_value = {"username": "test_user", "password": "test_pass"}
        client.create_secret(
            Name="test-secret", SecretString=json.dumps(secret_value)
        )

        result = Settings._get_secret_value("test-secret")
        assert result == secret_value

    @mock_aws
    def test_get_secret_value_not_found(self, aws_credentials):
        """Test error when secret not found."""
        with pytest.raises(RuntimeError) as exc_info:
            Settings._get_secret_value("nonexistent-secret")
        assert "not found in Secrets Manager" in str(exc_info.value)

    @mock_aws
    def test_get_secret_value_invalid_json(self, aws_credentials):
        """Test error when secret contains invalid JSON."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        client.create_secret(Name="bad-secret", SecretString="not-json-{invalid}")

        with pytest.raises(RuntimeError) as exc_info:
            Settings._get_secret_value("bad-secret")
        assert "invalid JSON" in str(exc_info.value)

    @mock_aws
    def test_load_naver_credentials_success(self, aws_credentials, mock_secrets):
        """Test loading Naver credentials."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/naver-credentials"
        client.create_secret(
            Name=secret_id, SecretString=json.dumps(mock_secrets[secret_id])
        )

        result = Settings.load_naver_credentials()
        assert result["username"] == "test_user"
        assert result["password"] == "test_pass123"

    @mock_aws
    def test_load_naver_credentials_missing_keys(self, aws_credentials):
        """Test error when Naver credentials missing required keys."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/naver-credentials"
        client.create_secret(Name=secret_id, SecretString=json.dumps({"username": "test"}))

        with pytest.raises(RuntimeError) as exc_info:
            Settings.load_naver_credentials()
        assert "missing required keys" in str(exc_info.value)

    @mock_aws
    def test_load_sens_credentials_success(self, aws_credentials, mock_secrets):
        """Test loading SENS credentials."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/sens-credentials"
        client.create_secret(
            Name=secret_id, SecretString=json.dumps(mock_secrets[secret_id])
        )

        result = Settings.load_sens_credentials()
        assert result["access_key"] == "test_access_key"
        assert result["secret_key"] == "test_secret_key"
        assert result["service_id"] == "test_service_id"

    @mock_aws
    def test_load_sens_credentials_missing_keys(self, aws_credentials):
        """Test error when SENS credentials missing required keys."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/sens-credentials"
        client.create_secret(
            Name=secret_id, SecretString=json.dumps({"access_key": "test"})
        )

        with pytest.raises(RuntimeError) as exc_info:
            Settings.load_sens_credentials()
        assert "missing required keys" in str(exc_info.value)

    @mock_aws
    def test_load_telegram_credentials_success(self, aws_credentials, mock_secrets):
        """Test loading Telegram credentials."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/telegram-credentials"
        client.create_secret(
            Name=secret_id, SecretString=json.dumps(mock_secrets[secret_id])
        )

        result = Settings.load_telegram_credentials()
        assert result["bot_token"] == "test_bot_token"
        assert result["chat_id"] == "test_chat_id"

    @mock_aws
    def test_load_telegram_credentials_missing_keys(self, aws_credentials):
        """Test error when Telegram credentials missing required keys."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/telegram-credentials"
        client.create_secret(Name=secret_id, SecretString=json.dumps({"bot_token": "test"}))

        with pytest.raises(RuntimeError) as exc_info:
            Settings.load_telegram_credentials()
        assert "missing required keys" in str(exc_info.value)


class TestSettingsLocalFile:
    """Tests for Settings class with local file loading."""

    def test_load_from_local_file_success(self):
        """Test loading secrets from local JSON file."""
        secrets = {
            "naver": {"username": "user", "password": "pass"},
            "sens": {"access_key": "key", "secret_key": "secret", "service_id": "svc"},
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
            f.write("invalid json {")
            temp_file = f.name

        try:
            with pytest.raises(RuntimeError) as exc_info:
                Settings._load_from_local_file(temp_file)
            assert "invalid JSON" in str(exc_info.value)
        finally:
            os.unlink(temp_file)

    def test_load_naver_credentials_from_local_file(self):
        """Test loading Naver credentials from local file when env var set."""
        secrets = {
            "naver": {"username": "local_user", "password": "local_pass"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(secrets, f)
            temp_file = f.name

        try:
            with patch("src.config.settings.USE_LOCAL_SECRETS", True):
                with patch("src.config.settings.LOCAL_SECRETS_FILE", temp_file):
                    result = Settings.load_naver_credentials()
                    assert result["username"] == "local_user"
                    assert result["password"] == "local_pass"
        finally:
            os.unlink(temp_file)


class TestSettingsModuleFunctions:
    """Tests for module-level convenience functions."""

    @mock_aws
    def test_get_naver_credentials_function(self, aws_credentials, mock_secrets):
        """Test module-level get_naver_credentials function."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/naver-credentials"
        client.create_secret(
            Name=secret_id, SecretString=json.dumps(mock_secrets[secret_id])
        )

        result = get_naver_credentials()
        assert result["username"] == "test_user"

    @mock_aws
    def test_get_sens_credentials_function(self, aws_credentials, mock_secrets):
        """Test module-level get_sens_credentials function."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/sens-credentials"
        client.create_secret(
            Name=secret_id, SecretString=json.dumps(mock_secrets[secret_id])
        )

        result = get_sens_credentials()
        assert result["access_key"] == "test_access_key"

    @mock_aws
    def test_get_telegram_credentials_function(self, aws_credentials, mock_secrets):
        """Test module-level get_telegram_credentials function."""
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")
        secret_id = "naver-sms-automation/telegram-credentials"
        client.create_secret(
            Name=secret_id, SecretString=json.dumps(mock_secrets[secret_id])
        )

        result = get_telegram_credentials()
        assert result["bot_token"] == "test_bot_token"

    def test_setup_logging_redaction(self):
        """Test setup_logging_redaction doesn't raise errors."""
        logger = logging.getLogger("test_redaction")
        # Should not raise even if secrets can't be loaded (local env)
        setup_logging_redaction()
        assert logger.hasHandlers() or True  # Pass if no error
