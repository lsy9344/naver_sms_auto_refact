"""
Configuration loader for Naver SMS Automation

Fetches credentials from AWS Secrets Manager with caching,
exponential backoff, and structured logging redaction.
"""

import json
import logging
import os
import time
from functools import lru_cache
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Secrets Manager secret names (from Story 1.2)
# NOTE: These are secret NAMES, not secret VALUES. Values are fetched from AWS Secrets Manager.
NAVER_SECRET_ID = "naver-sms-automation/naver-credentials"  # nosec B105
SENS_SECRET_ID = "naver-sms-automation/sens-credentials"  # nosec B105
TELEGRAM_SECRET_ID = "naver-sms-automation/telegram-credentials"  # nosec B105

# For local development with dummy credentials file
USE_LOCAL_SECRETS = os.getenv("USE_LOCAL_SECRETS_FILE", "false").lower() == "true"
LOCAL_SECRETS_FILE = os.getenv("LOCAL_SECRETS_FILE_PATH", ".local/secrets.json")


class SecretRedactionFilter(logging.Filter):
    """
    Logging filter that redacts secret values from log records.
    Replaces secret substrings with ***REDACTED*** to prevent accidental leakage.
    """

    def __init__(self, secrets: Optional[Dict[str, Any]] = None):
        """
        Initialize filter with secrets to redact.

        Args:
            secrets: Dictionary of secrets to redact (values will be masked)
        """
        super().__init__()
        self.secrets = secrets or {}
        self.redacted_values = set()
        if self.secrets:
            self._extract_secret_values(self.secrets)

    def _extract_secret_values(self, obj: Any, max_depth: int = 5) -> None:
        """Recursively extract all secret values from nested structures."""
        if max_depth <= 0:
            return

        if isinstance(obj, dict):
            for value in obj.values():
                self._extract_secret_values(value, max_depth - 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._extract_secret_values(item, max_depth - 1)
        elif isinstance(obj, str) and obj and len(obj) > 3:
            # Only redact strings with meaningful length
            self.redacted_values.add(obj)

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and redact log record."""
        try:
            # Redact message
            record.msg = self._redact_string(str(record.msg))
            # Redact args if present
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: self._redact_string(str(v)) for k, v in record.args.items()
                    }
                elif isinstance(record.args, (list, tuple)):
                    record.args = tuple(
                        self._redact_string(str(arg)) for arg in record.args
                    )
        except Exception as e:
            logger.warning(f"Error during secret redaction: {e}")
        return True

    def _redact_string(self, text: str) -> str:
        """Redact all secret values from string."""
        for secret in self.redacted_values:
            if secret in text:
                text = text.replace(secret, "***REDACTED***")
        return text


class Settings:
    """
    Configuration loader that fetches credentials from AWS Secrets Manager.
    Implements caching, exponential backoff, and error handling.
    """

    def __init__(self, region_name: str = "ap-northeast-2"):
        """
        Initialize Settings loader.

        Args:
            region_name: AWS region for Secrets Manager
        """
        self.region_name = region_name
        self._secrets_cache: Dict[str, Any] = {}
        self._cache_initialized = False
        self.secrets_client = None

    def _get_secrets_client(self):
        """Lazy initialize Secrets Manager client."""
        if self.secrets_client is None:
            self.secrets_client = boto3.client(
                "secretsmanager", region_name=self.region_name
            )
        return self.secrets_client

    @staticmethod
    def _get_secret_value(
        secret_id: str, max_retries: int = 3, base_wait: float = 1.0
    ) -> Dict[str, Any]:
        """
        Fetch secret from Secrets Manager with exponential backoff.

        Args:
            secret_id: Secret identifier in Secrets Manager
            max_retries: Maximum number of retry attempts
            base_wait: Base wait time in seconds for exponential backoff

        Returns:
            Parsed secret JSON as dictionary

        Raises:
            RuntimeError: If secret cannot be retrieved after retries
        """
        client = boto3.client("secretsmanager", region_name="ap-northeast-2")

        for attempt in range(max_retries):
            try:
                response = client.get_secret_value(SecretId=secret_id)
                secret_string = response.get("SecretString")
                if not secret_string:
                    raise ValueError(f"Secret {secret_id} has empty value")
                return json.loads(secret_string)
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "ResourceNotFoundException":
                    raise RuntimeError(
                        f"Secret '{secret_id}' not found in Secrets Manager. "
                        f"Please verify the secret exists in region ap-northeast-2"
                    ) from e
                elif error_code in ["AccessDeniedException", "UnauthorizedOperation"]:
                    raise RuntimeError(
                        f"Access denied to secret '{secret_id}'. "
                        f"Verify Lambda execution role has secretsmanager:GetSecretValue permission"
                    ) from e
                elif error_code == "DecryptionFailure":
                    raise RuntimeError(
                        f"Failed to decrypt secret '{secret_id}'. "
                        f"Verify KMS key permissions for Lambda role"
                    ) from e
                else:
                    # Transient error, retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = base_wait * (2 ** attempt)
                        logger.warning(
                            f"Transient error fetching secret {secret_id}: {error_code}. "
                            f"Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                    else:
                        raise RuntimeError(
                            f"Failed to retrieve secret '{secret_id}' after {max_retries} attempts: {error_code}"
                        ) from e
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Secret '{secret_id}' contains invalid JSON: {str(e)}"
                ) from e
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = base_wait * (2 ** attempt)
                    logger.warning(
                        f"Unexpected error fetching secret {secret_id}: {str(e)}. "
                        f"Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Unexpected error retrieving secret '{secret_id}': {str(e)}"
                    ) from e

        raise RuntimeError(
            f"Failed to retrieve secret '{secret_id}' - exhausted all retry attempts"
        )

    @staticmethod
    def load_naver_credentials() -> Dict[str, str]:
        """
        Load Naver credentials from Secrets Manager or local file.

        Returns:
            Dictionary with 'username' and 'password' keys

        Raises:
            RuntimeError: If credentials cannot be loaded
        """
        if USE_LOCAL_SECRETS:
            return Settings._load_from_local_file(LOCAL_SECRETS_FILE).get(
                "naver", {}
            )

        credentials = Settings._get_secret_value(NAVER_SECRET_ID)
        if "username" not in credentials or "password" not in credentials:
            raise RuntimeError(
                f"Naver credentials missing required keys. "
                f"Expected: username, password. Got: {list(credentials.keys())}"
            )
        return credentials

    @staticmethod
    def load_sens_credentials() -> Dict[str, str]:
        """
        Load SENS (SMS API) credentials from Secrets Manager or local file.

        Returns:
            Dictionary with 'access_key', 'secret_key', 'service_id' keys

        Raises:
            RuntimeError: If credentials cannot be loaded
        """
        if USE_LOCAL_SECRETS:
            return Settings._load_from_local_file(LOCAL_SECRETS_FILE).get("sens", {})

        credentials = Settings._get_secret_value(SENS_SECRET_ID)
        required_keys = {"access_key", "secret_key", "service_id"}
        if not required_keys.issubset(credentials.keys()):
            raise RuntimeError(
                f"SENS credentials missing required keys. "
                f"Expected: {required_keys}. Got: {set(credentials.keys())}"
            )
        return credentials

    @staticmethod
    def load_telegram_credentials() -> Dict[str, str]:
        """
        Load Telegram credentials from Secrets Manager or local file.

        Returns:
            Dictionary with 'bot_token' and 'chat_id' keys

        Raises:
            RuntimeError: If credentials cannot be loaded
        """
        if USE_LOCAL_SECRETS:
            return Settings._load_from_local_file(LOCAL_SECRETS_FILE).get(
                "telegram", {}
            )

        credentials = Settings._get_secret_value(TELEGRAM_SECRET_ID)
        if "bot_token" not in credentials or "chat_id" not in credentials:
            raise RuntimeError(
                f"Telegram credentials missing required keys. "
                f"Expected: bot_token, chat_id. Got: {list(credentials.keys())}"
            )
        return credentials

    @staticmethod
    def _load_from_local_file(filepath: str) -> Dict[str, Any]:
        """
        Load secrets from local JSON file for development.

        Args:
            filepath: Path to local secrets JSON file

        Returns:
            Dictionary of secrets

        Raises:
            RuntimeError: If file cannot be read or contains invalid JSON
        """
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            raise RuntimeError(
                f"Local secrets file not found: {filepath}. "
                f"Use AWS Secrets Manager or provide USE_LOCAL_SECRETS_FILE=true and LOCAL_SECRETS_FILE_PATH"
            )
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Local secrets file contains invalid JSON: {str(e)}")

    @staticmethod
    def setup_redaction_filter(logger_instance: logging.Logger) -> None:
        """
        Configure logger with secret redaction filter.

        Args:
            logger_instance: Logger instance to configure
        """
        try:
            # Try to load all credentials for redaction
            all_secrets = {}
            try:
                all_secrets.update(Settings.load_naver_credentials())
                all_secrets.update(Settings.load_sens_credentials())
                all_secrets.update(Settings.load_telegram_credentials())
            except RuntimeError:
                # If we can't load secrets, redaction filter will be created without them
                pass

            redaction_filter = SecretRedactionFilter(all_secrets)
            logger_instance.addFilter(redaction_filter)
        except Exception as e:
            logger.warning(f"Failed to setup redaction filter: {e}")


# Module-level convenience functions
def get_naver_credentials() -> Dict[str, str]:
    """Get Naver credentials."""
    return Settings.load_naver_credentials()


def get_sens_credentials() -> Dict[str, str]:
    """Get SENS credentials."""
    return Settings.load_sens_credentials()


def get_telegram_credentials() -> Dict[str, str]:
    """Get Telegram credentials."""
    return Settings.load_telegram_credentials()


def setup_logging_redaction() -> None:
    """Setup logging redaction for root logger."""
    Settings.setup_redaction_filter(logging.getLogger())
