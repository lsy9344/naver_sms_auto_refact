"""
Configuration loader for Naver SMS Automation

Fetches credentials from AWS Secrets Manager with caching,
exponential backoff, and structured logging redaction.
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional, List, Tuple

import boto3
import jsonschema
import yaml
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""

    pass


# Secrets Manager secret names (from Story 1.2)
# NOTE: These are secret NAMES, not secret VALUES. Values are fetched from AWS Secrets Manager.
NAVER_SECRET_ID = "naver-sms-automation/naver-credentials"  # nosec B105
SENS_SECRET_ID = "naver-sms-automation/sens-credentials"  # nosec B105
TELEGRAM_SECRET_ID = "naver-sms-automation/telegram-credentials"  # nosec B105
SLACK_SECRET_ID = "naver-sms-automation/slack-credentials"  # nosec B105

# For local development with dummy credentials file
USE_LOCAL_SECRETS = os.getenv("USE_LOCAL_SECRETS_FILE", "false").lower() == "true"
LOCAL_SECRETS_FILE = os.getenv("LOCAL_SECRETS_FILE_PATH", ".local/secrets.json")

# Slack configuration (Story 6.2)
# Default: False (Slack disabled) - Requires explicit enable via environment variable
SLACK_ENABLED = os.getenv("SLACK_ENABLED", "false").lower() == "true"
SLACK_WEBHOOK_URL_ENV = os.getenv("SLACK_WEBHOOK_URL", None)  # Direct override if provided
SLACK_CONFIG_FILE = os.getenv("SLACK_CONFIG_FILE", "config/my_slack_webhook.yaml")


# Telegram configuration helper (flag evaluated at runtime per Settings instance)
def _read_telegram_flag() -> Tuple[bool, bool]:
    """Return (enabled_value, flag_defined) from environment variables."""
    flag_raw = os.getenv("ENABLE_TELEGRAM_NOTIFICATIONS")
    if flag_raw is None:
        flag_raw = os.getenv("TELEGRAM_ENABLED")
    if flag_raw is None:
        return False, False
    return flag_raw.lower() == "true", True


# Manual approval gate for SENS SMS delivery (Story 5.4 - AC 10)
# Default: False (SMS delivery disabled) - Requires explicit owner sign-off
# Set to True via environment variable or Lambda config after manual approval
SENS_DELIVERY_ENABLED = os.getenv("SENS_DELIVERY_ENABLED", "false").lower() == "true"

# Comparison/validation mode flag
# When True: Logs SMS payloads and metrics but does NOT send real SENS SMS
COMPARISON_MODE_ENABLED = os.getenv("COMPARISON_MODE_ENABLED", "false") == "true"

_TELEGRAM_CREDENTIALS_CACHE: Optional[Dict[str, str]] = None


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
        self.redacted_values: set[str] = set()
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
                    record.args = {k: self._redact_string(str(v)) for k, v in record.args.items()}
                elif isinstance(record.args, (list, tuple)):
                    record.args = tuple(self._redact_string(str(arg)) for arg in record.args)
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
        self.rules: List[Dict[str, Any]] = []
        self.rules_schema: Dict[str, Any] = {}
        # Feature flags (Story 5.4)
        self.sens_delivery_enabled = SENS_DELIVERY_ENABLED
        self.comparison_mode_enabled = COMPARISON_MODE_ENABLED
        telegram_flag_value, flag_defined = _read_telegram_flag()
        self.telegram_flag_defined = flag_defined
        self.telegram_enabled = telegram_flag_value
        if not self.telegram_flag_defined:
            self.telegram_enabled = self._auto_enable_telegram_notifications()

    def is_sens_delivery_enabled(self) -> bool:
        """Check if SENS SMS delivery is enabled (Story 5.4 AC 10)."""
        return self.sens_delivery_enabled

    def is_comparison_mode_enabled(self) -> bool:
        """Check if comparison/validation mode is enabled."""
        return self.comparison_mode_enabled

    def is_telegram_enabled(self) -> bool:
        """Check if Telegram notifications are permitted."""
        return self.telegram_enabled

    def _auto_enable_telegram_notifications(self) -> bool:
        """
        Auto-enable Telegram when explicit flag not provided but credentials exist.
        Prefers environment variables, then local secrets, then Secrets Manager.
        """
        env_bot = os.getenv("TELEGRAM_BOT_TOKEN")
        env_chat = os.getenv("TELEGRAM_CHAT_ID")
        if env_bot and env_chat:
            logger.info("Detected Telegram bot credentials via environment; enabling notifications")
            return True

        global _TELEGRAM_CREDENTIALS_CACHE

        if USE_LOCAL_SECRETS:
            try:
                local_creds = self._load_from_local_file(LOCAL_SECRETS_FILE).get("telegram", {})
                if local_creds.get("bot_token") and local_creds.get("chat_id"):
                    logger.info(
                        "Detected Telegram credentials in local secrets file; enabling notifications"
                    )
                    _TELEGRAM_CREDENTIALS_CACHE = local_creds
                    return True
            except Exception as e:
                logger.debug(f"Local Telegram credential detection failed: {e}")

        if not USE_LOCAL_SECRETS:
            try:
                credentials = Settings._get_secret_value(TELEGRAM_SECRET_ID)
                if credentials.get("bot_token") and credentials.get("chat_id"):
                    logger.info(
                        "Detected Telegram credentials in Secrets Manager; enabling notifications"
                    )
                    _TELEGRAM_CREDENTIALS_CACHE = credentials
                    return True
            except Exception as e:
                logger.debug(f"Telegram secret auto-detect failed: {e}")

        return False

    def _get_secrets_client(self):
        """Lazy initialize Secrets Manager client."""
        if self.secrets_client is None:
            self.secrets_client = boto3.client("secretsmanager", region_name=self.region_name)
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
                        wait_time = base_wait * (2**attempt)
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
                raise RuntimeError(f"Secret '{secret_id}' contains invalid JSON: {str(e)}") from e
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = base_wait * (2**attempt)
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
            return Settings._load_from_local_file(LOCAL_SECRETS_FILE).get("naver", {})

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
        global _TELEGRAM_CREDENTIALS_CACHE
        if _TELEGRAM_CREDENTIALS_CACHE:
            return _TELEGRAM_CREDENTIALS_CACHE

        if USE_LOCAL_SECRETS:
            credentials = Settings._load_from_local_file(LOCAL_SECRETS_FILE).get("telegram", {})
            _TELEGRAM_CREDENTIALS_CACHE = credentials
            return credentials

        credentials = Settings._get_secret_value(TELEGRAM_SECRET_ID)
        if "bot_token" not in credentials or "chat_id" not in credentials:
            raise RuntimeError(
                f"Telegram credentials missing required keys. "
                f"Expected: bot_token, chat_id. Got: {list(credentials.keys())}"
            )
        _TELEGRAM_CREDENTIALS_CACHE = credentials
        return credentials

    @staticmethod
    def load_slack_webhook_url() -> Optional[str]:
        """
        Load Slack webhook URL from environment, local config, or Secrets Manager (AC 2, Story 6.2).

        Priority:
        1. SLACK_WEBHOOK_URL environment variable (direct override)
        2. config/my_slack_webhook.yaml (local development)
        3. Secrets Manager (production)

        Returns:
            Webhook URL string or None if not configured

        Raises:
            RuntimeError: If loading fails catastrophically
        """
        # Priority 1: Direct environment override
        if SLACK_WEBHOOK_URL_ENV:
            return SLACK_WEBHOOK_URL_ENV

        # Priority 2: Local config file
        try:
            if os.path.exists(SLACK_CONFIG_FILE):
                with open(SLACK_CONFIG_FILE, "r", encoding="utf-8") as f:
                    content = yaml.safe_load(f)
                    if content and isinstance(content, dict):
                        webhook_url = content.get("slack webhook url")
                        if webhook_url:
                            return webhook_url
        except Exception as e:
            logger.warning(f"Failed to load Slack webhook from {SLACK_CONFIG_FILE}: {e}")

        # Priority 3: Secrets Manager
        if not USE_LOCAL_SECRETS:
            try:
                credentials = Settings._get_secret_value(SLACK_SECRET_ID)
                webhook_url = credentials.get("webhook_url")
                if webhook_url:
                    return webhook_url
            except Exception as e:
                logger.warning(f"Failed to load Slack webhook from Secrets Manager: {e}")

        return None

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

    def load_rules(self, rules_config_path: str, schema_config_path: str) -> None:
        """
        Load rules from YAML configuration and validate against schema.

        Args:
            rules_config_path: Path to rules.yaml configuration file
            schema_config_path: Path to rules.schema.json validation schema

        Raises:
            FileNotFoundError: If config files not found
            ValueError: If rule schema is invalid
            jsonschema.ValidationError: If rules don't match schema
            yaml.YAMLError: If YAML parsing fails
        """
        # Load schema first
        try:
            with open(schema_config_path, "r", encoding="utf-8") as f:
                self.rules_schema = json.load(f)
                logger.debug(f"Loaded rules schema from {schema_config_path}")
        except FileNotFoundError:
            logger.error(f"Rules schema file not found: {schema_config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in rules schema: {e}")
            raise ValueError(f"Invalid JSON in {schema_config_path}: {e}") from e

        # Load and validate rules
        try:
            with open(rules_config_path, "r", encoding="utf-8") as f:
                rules_config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Rules configuration file not found: {rules_config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in rules configuration: {e}")
            raise ValueError(f"Invalid YAML in {rules_config_path}: {e}") from e

        if not rules_config:
            logger.warning(f"Empty rules configuration: {rules_config_path}")
            self.rules = []
            return

        # Validate against schema
        try:
            jsonschema.validate(instance=rules_config, schema=self.rules_schema)
            logger.info("Rules configuration validated against schema")
        except jsonschema.ValidationError as e:
            logger.error(f"Rules configuration failed schema validation: {e.message}")
            raise ValueError(f"Rules configuration validation failed: {e.message}") from e
        except jsonschema.SchemaError as e:
            logger.error(f"Rules schema is invalid: {e.message}")
            raise ValueError(f"Rules schema is invalid: {e.message}") from e

        # Extract and store rules
        self.rules = rules_config.get("rules", [])
        logger.info(f"Successfully loaded {len(self.rules)} rules from {rules_config_path}")

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


def get_slack_webhook_url() -> Optional[str]:
    """Get Slack webhook URL (Story 6.2)."""
    return Settings.load_slack_webhook_url()


def setup_logging_redaction() -> None:
    """Setup logging redaction for root logger."""
    Settings.setup_redaction_filter(logging.getLogger())
