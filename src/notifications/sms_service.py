"""
SENS SMS notifications client.

Preserves the legacy signature algorithm, headers, and payload structure
while externalising templates and store configuration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests
import yaml

from config.settings import Settings
from utils.logger import get_logger, StructuredLogger


class SmsServiceError(Exception):
    """Raised when the SMS service fails to deliver a message."""


def _default_timestamp_provider() -> str:
    """Return millisecond epoch timestamp as string."""
    return str(int(time.time() * 1000))


class SensSmsClient:
    """
    Client for sending SMS messages through Naver Cloud SENS.

    Attributes mirror the legacy implementation to guarantee parity while
    sourcing configuration and credentials from external files.
    """

    SENS_URL = "https://sens.apigw.ntruss.com"

    def __init__(
        self,
        settings: Optional[Settings] = None,
        credentials: Optional[Dict[str, str]] = None,
        templates_path: Optional[Path] = None,
        stores_path: Optional[Path] = None,
        http_client: Optional[requests.Session] = None,
        logger: Optional[StructuredLogger] = None,
        timestamp_provider: Callable[[], str] = _default_timestamp_provider,
        max_retries: int = 3,
        retry_delay_seconds: float = 0.5,
    ) -> None:
        """
        Initialise the SMS client.

        Args:
            settings: Optional Settings instance (falls back to default Settings()).
            credentials: Optional explicit credentials dict for testing.
            templates_path: Path to sms_templates.yaml.
            stores_path: Path to stores.yaml.
            http_client: Optional requests-like session (useful for testing).
            logger: Optional structured logger instance.
            timestamp_provider: Callable returning millisecond timestamp string.
            max_retries: Number of attempts when sending SMS.
            retry_delay_seconds: Base delay between retries (linear backoff).
        """
        self.logger = logger or get_logger(__name__)
        self.http_client = http_client or requests.Session()
        self._timestamp_provider = timestamp_provider
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

        self.settings = settings or Settings()
        self.credentials = credentials or self.settings.load_sens_credentials()
        self.access_key = self.credentials["access_key"]
        self.secret_key = self.credentials["secret_key"]
        self.service_id = self.credentials["service_id"]

        root_dir = Path(__file__).resolve().parents[2]
        if templates_path:
            self.templates_path = Path(templates_path)
        else:
            self.templates_path = root_dir / "config" / "sms_templates.yaml"
        if stores_path:
            self.stores_path = Path(stores_path)
        else:
            self.stores_path = root_dir / "config" / "stores.yaml"

        self.templates = self._load_templates()
        self.store_directory = self._load_store_directory()

        self.uri = f"/sms/v2/services/{self.service_id}/messages"

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def send_confirm_sms(self, phone: str, store_id: Optional[str] = None) -> None:
        """Send booking confirmation SMS."""
        template = self._get_template("booking_confirm")
        payload = self._build_payload(template, phone, store_id)
        self._dispatch(payload, store_id, phone, action="send_confirm_sms")

    def send_guide_sms(self, store_id: str, phone: str) -> None:
        """Send store specific guide SMS."""
        if not store_id:
            raise ValueError("store_id is required for guide SMS")
        template_key = self._get_store_template(store_id, "guide")
        template = self._get_template(("guide", template_key))
        payload = self._build_payload(template, phone, store_id)
        self._dispatch(payload, store_id, phone, action="send_guide_sms")

    def send_event_sms(self, phone: str, store_id: Optional[str] = None) -> None:
        """Send event/review SMS."""
        template = self._get_template("event")
        payload = self._build_payload(template, phone, store_id)
        self._dispatch(payload, store_id, phone, action="send_event_sms")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _dispatch(
        self,
        payload: Dict[str, Any],
        store_id: Optional[str],
        phone: str,
        action: str,
    ) -> None:
        """Send payload to SENS with retry handling."""
        url = f"{self.SENS_URL}{self.uri}"
        body = json.dumps(payload)  # ensure_ascii=True preserves legacy behaviour
        masked_phone = self._mask_phone(phone)

        for attempt in range(1, self.max_retries + 1):
            timestamp = self._timestamp_provider()
            headers = self._build_headers(timestamp)
            try:
                self.logger.info(
                    "Sending SMS via SENS",
                    operation=action,
                    context={
                        "status": "attempt",
                        "attempt": attempt,
                        "store_id": store_id,
                        "phone_masked": masked_phone,
                    }
                )
                response = self.http_client.post(
                    url, headers=headers, data=body, timeout=10
                )
                if response.status_code >= 400:
                    raise SmsServiceError(
                        f"SENS responded with {response.status_code}: {response.text}"
                    )

                self.logger.info(
                    "SMS delivered",
                    operation=action,
                    context={
                        "status": "success",
                        "attempt": attempt,
                        "store_id": store_id,
                        "phone_masked": masked_phone,
                    }
                )
                return
            except Exception as exc:  # noqa: BLE001 - we need to retry on any failure
                if attempt >= self.max_retries:
                    self.logger.error(
                        "SMS delivery failed",
                        operation=action,
                        context={
                            "status": "failed",
                            "attempt": attempt,
                            "store_id": store_id,
                            "phone_masked": masked_phone,
                        },
                        error=str(exc),
                    )
                    raise SmsServiceError("Failed to deliver SMS") from exc

                self.logger.warning(
                    "Retrying SMS delivery",
                    operation=action,
                    context={
                        "status": "retry",
                        "attempt": attempt,
                        "store_id": store_id,
                        "phone_masked": masked_phone,
                    },
                    error=str(exc),
                )
                time.sleep(self.retry_delay_seconds * attempt)

    def _build_payload(
        self,
        template: Dict[str, Any],
        phone: str,
        store_id: Optional[str],
    ) -> Dict[str, Any]:
        """Construct request payload identical to the legacy implementation."""
        normalized_phone = self._normalize_phone(phone)
        from_number = self._get_from_number(store_id)

        if not normalized_phone:
            raise ValueError("phone number is required")

        return {
            "type": template["type"],
            "contentType": template["contentType"],
            "from": from_number,
            "subject": template["subject"],
            "content": template["content"],
            "messages": [{"to": normalized_phone}],
        }

    def _build_headers(self, timestamp: str) -> Dict[str, str]:
        """Return headers with preserved signature logic."""
        signature = self._make_signature(timestamp)
        return {
            "Content-Type": "application/json; charset=utf-8",
            "x-ncp-apigw-timestamp": timestamp,
            "x-ncp-iam-access-key": self.access_key,
            "x-ncp-apigw-signature-v2": signature,
        }

    def _make_signature(self, timestamp: str) -> str:
        """Generate SENS signature exactly as legacy implementation."""
        message = f"POST {self.uri}\n{timestamp}\n{self.access_key}"
        digest = hmac.new(
            self.secret_key.encode("UTF-8"),
            message.encode("UTF-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("UTF-8")

    def _get_template(self, template_key: Any) -> Dict[str, Any]:
        """Fetch template definition."""
        if isinstance(template_key, tuple):
            namespace, key = template_key
            content = self.templates[namespace]["stores"].get(key)
            if content is None:
                raise KeyError(f"Template '{namespace}:{key}' not found")
            template = {
                "type": self.templates[namespace]["type"],
                "contentType": self.templates[namespace]["contentType"],
                "subject": self.templates[namespace]["subject"],
                "content": content,
            }
            return template

        template = self.templates.get(template_key)
        if template is None:
            raise KeyError(f"Template '{template_key}' not found")
        return template

    def _get_store_template(self, store_id: str, template_type: str) -> str:
        """Return template key for given store and type."""
        store = self.store_directory["stores"].get(store_id)
        if not store:
            raise KeyError(f"Store '{store_id}' not found in configuration")
        template_key = store.get("templates", {}).get(template_type)
        if template_key is None:
            raise KeyError(f"Template mapping '{template_type}' missing for store '{store_id}'")
        return template_key

    def _get_from_number(self, store_id: Optional[str]) -> str:
        """Retrieve store specific from-number with fallback."""
        fallback = os.getenv(
            "SENS_DEFAULT_FROM",
            self.store_directory["default"]["fromNumber"],
        )
        if not store_id:
            return fallback

        store = self.store_directory["stores"].get(store_id)
        if not store:
            return fallback

        from_number = store.get("fromNumber") or fallback
        return from_number

    def _normalize_phone(self, phone: str) -> str:
        """Remove non-digit characters from phone number."""
        return "".join(ch for ch in phone if ch.isdigit())

    def _mask_phone(self, phone: str) -> str:
        """Mask phone number except last four digits."""
        digits = self._normalize_phone(phone)
        if len(digits) <= 4:
            return digits
        return f"{'*' * (len(digits) - 4)}{digits[-4:]}"

    # ------------------------------------------------------------------ #
    # Configuration loaders
    # ------------------------------------------------------------------ #
    def _load_templates(self) -> Dict[str, Any]:
        """Load SMS templates from YAML file."""
        if not self.templates_path.exists():
            raise FileNotFoundError(f"SMS templates file not found: {self.templates_path}")

        with self.templates_path.open("r", encoding="utf-8") as handle:
            parsed = yaml.safe_load(handle) or {}

        templates = parsed.get("templates")
        if not templates:
            raise ValueError("templates section missing in sms_templates.yaml")

        return templates

    def _load_store_directory(self) -> Dict[str, Any]:
        """Load store configuration and apply environment overrides."""
        if not self.stores_path.exists():
            raise FileNotFoundError(f"Stores configuration file not found: {self.stores_path}")

        with self.stores_path.open("r", encoding="utf-8") as handle:
            directory = yaml.safe_load(handle) or {}

        defaults = directory.get("default")
        stores = directory.get("stores")
        if not defaults or not stores:
            raise ValueError("Invalid stores.yaml structure; expected default and stores sections")

        env_override = os.getenv("SENS_FROM_MAP_JSON")
        if env_override:
            self._apply_from_map_override(stores, env_override)

        return {"default": defaults, "stores": stores}

    def _apply_from_map_override(self, stores: Dict[str, Any], raw: str) -> None:
        """Overlay store from-numbers using environment JSON map."""
        try:
            override = json.loads(raw)
        except json.JSONDecodeError as err:
            self.logger.warning(
                "Failed to decode SENS_FROM_MAP_JSON",
                error=str(err),
            )
            return

        def _normalize(value: Any) -> str:
            return str(value).strip()

        for key, value in override.items():
            store_id = _normalize(key)
            number = _normalize(value)
            if not store_id or not number:
                continue
            if store_id not in stores:
                stores[store_id] = {
                    "name": f"Store {store_id}",
                    "fromNumber": number,
                    "templates": {},
                }
            else:
                stores[store_id]["fromNumber"] = number
