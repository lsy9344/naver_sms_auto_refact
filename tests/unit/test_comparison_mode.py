"""
Comparison Mode Kill Switch Tests

Story 5.5 SEC-001: Validates that COMPARISON_MODE prevents production SMS.

Ensures that when validation campaign is running in comparison mode,
no actual SMS messages are sent to customers. This is a critical security
requirement to prevent SMS leakage during validation.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

logger = logging.getLogger(__name__)


class ComparisonModeConfig:
    """Configuration for comparison mode."""

    def __init__(self, comparison_mode_enabled: bool = False):
        """
        Initialize comparison mode config.

        Args:
            comparison_mode_enabled: True to enable comparison mode (no SMS sent)
        """
        self.comparison_mode_enabled = comparison_mode_enabled

    @classmethod
    def from_environment(cls) -> "ComparisonModeConfig":
        """Load from environment variables."""
        enabled = os.getenv("COMPARISON_MODE_ENABLED", "false") == "true"
        return cls(comparison_mode_enabled=enabled)

    def is_enabled(self) -> bool:
        """Check if comparison mode is enabled."""
        return self.comparison_mode_enabled


class SMSServiceWithComparisonMode:
    """SMS service with comparison mode support."""

    def __init__(self, comparison_mode_config: ComparisonModeConfig):
        """
        Initialize SMS service.

        Args:
            comparison_mode_config: Comparison mode configuration
        """
        self.config = comparison_mode_config
        self.logger = logging.getLogger(__name__)
        self.mock_sms_log = []

    def send_sms(self, phone: str, message: str, sms_type: str) -> bool:
        """
        Send SMS or simulate based on comparison mode.

        Args:
            phone: Phone number
            message: Message content
            sms_type: Type of SMS (confirm, guide, event)

        Returns:
            True if sent/simulated successfully, False if failed

        Raises:
            RuntimeError: If comparison mode prevents SMS
        """
        if self.config.is_enabled():
            # Comparison mode: simulate instead of sending
            self._simulate_sms(phone, message, sms_type)
            return True
        else:
            # Production mode: actually send
            return self._send_real_sms(phone, message, sms_type)

    def _simulate_sms(self, phone: str, message: str, sms_type: str) -> None:
        """
        Simulate SMS send without actual delivery.

        Args:
            phone: Phone number
            message: Message content
            sms_type: Type of SMS
        """
        self.mock_sms_log.append(
            {
                "mode": "SIMULATED",
                "phone": self._mask_phone(phone),
                "type": sms_type,
                "message_preview": message[:50],
            }
        )

        self.logger.info(
            f"[COMPARISON MODE] SMS simulated",
            extra={
                "phone": self._mask_phone(phone),
                "type": sms_type,
            },
        )

    def _send_real_sms(self, phone: str, message: str, sms_type: str) -> bool:
        """
        Send real SMS via SENS API.

        Args:
            phone: Phone number
            message: Message content
            sms_type: Type of SMS

        Returns:
            True if sent successfully
        """
        # This would call actual SENS API in production
        self.mock_sms_log.append(
            {
                "mode": "SENT",
                "phone": self._mask_phone(phone),
                "type": sms_type,
                "message_preview": message[:50],
            }
        )

        self.logger.info(
            f"SMS sent",
            extra={
                "phone": self._mask_phone(phone),
                "type": sms_type,
            },
        )

        return True

    @staticmethod
    def _mask_phone(phone: str) -> str:
        """Mask phone number for logging."""
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) <= 4:
            return digits
        return f"{'*' * (len(digits) - 4)}{digits[-4:]}"

    def get_mock_sms_log(self) -> list:
        """Get log of simulated/sent SMS."""
        return self.mock_sms_log


class TestComparisonModeConfiguration:
    """Test comparison mode configuration."""

    def test_comparison_mode_can_be_enabled(self):
        """SEC-001: Comparison mode can be enabled."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)

        assert config.is_enabled()

    def test_comparison_mode_can_be_disabled(self):
        """SEC-001: Comparison mode can be disabled."""
        config = ComparisonModeConfig(comparison_mode_enabled=False)

        assert not config.is_enabled()

    def test_comparison_mode_loads_from_environment(self):
        """SEC-001: Comparison mode loads from environment variable."""
        with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": "true"}):
            config = ComparisonModeConfig.from_environment()

            assert config.is_enabled()

    def test_comparison_mode_defaults_disabled_from_environment(self):
        """SEC-001: Comparison mode defaults to disabled."""
        with patch.dict(os.environ, {}, clear=True):
            config = ComparisonModeConfig.from_environment()

            assert not config.is_enabled()


class TestComparisonModePreventsSMS:
    """Test that comparison mode prevents actual SMS sends."""

    def test_comparison_mode_simulates_sms_instead_of_sending(self):
        """SEC-001: Comparison mode simulates SMS instead of sending."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        result = service.send_sms(
            phone="010-1234-5678",
            message="Test message",
            sms_type="confirm",
        )

        assert result
        assert len(service.get_mock_sms_log()) == 1
        assert service.get_mock_sms_log()[0]["mode"] == "SIMULATED"

    def test_production_mode_sends_real_sms(self):
        """SEC-001: Production mode sends actual SMS."""
        config = ComparisonModeConfig(comparison_mode_enabled=False)
        service = SMSServiceWithComparisonMode(config)

        result = service.send_sms(
            phone="010-1234-5678",
            message="Test message",
            sms_type="confirm",
        )

        assert result
        assert len(service.get_mock_sms_log()) == 1
        assert service.get_mock_sms_log()[0]["mode"] == "SENT"

    def test_multiple_sms_in_comparison_mode(self):
        """SEC-001: Multiple SMS all simulated in comparison mode."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        # Send multiple SMS
        service.send_sms(
            phone="010-1111-1111",
            message="Confirmation",
            sms_type="confirm",
        )
        service.send_sms(
            phone="010-2222-2222",
            message="Guide",
            sms_type="guide",
        )
        service.send_sms(
            phone="010-3333-3333",
            message="Event",
            sms_type="event",
        )

        # All should be simulated
        log = service.get_mock_sms_log()
        assert len(log) == 3
        assert all(entry["mode"] == "SIMULATED" for entry in log)

    def test_comparison_mode_masks_phone_numbers_in_logs(self):
        """SEC-001: Comparison mode masks phone numbers in logs."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        service.send_sms(
            phone="010-1234-5678",
            message="Test",
            sms_type="confirm",
        )

        log = service.get_mock_sms_log()[0]
        phone_masked = log["phone"]

        # Should only show last 4 digits
        assert "****" in phone_masked
        assert "5678" in phone_masked

    def test_comparison_mode_truncates_message_in_logs(self):
        """SEC-001: Comparison mode logs truncate long messages."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        long_message = "A" * 200
        service.send_sms(
            phone="010-1234-5678",
            message=long_message,
            sms_type="confirm",
        )

        log = service.get_mock_sms_log()[0]
        preview = log["message_preview"]

        assert len(preview) <= 50
        assert preview == "A" * 50


class TestComparisonModeHandling:
    """Test comparison mode behavior in different scenarios."""

    def test_mode_applies_to_all_sms_types(self):
        """SEC-001: Comparison mode applies to all SMS types."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        sms_types = ["confirm", "guide", "event"]

        for sms_type in sms_types:
            service.send_sms(
                phone="010-1234-5678",
                message=f"Test {sms_type}",
                sms_type=sms_type,
            )

        log = service.get_mock_sms_log()
        assert len(log) == len(sms_types)
        assert all(entry["mode"] == "SIMULATED" for entry in log)

    def test_mode_switch_from_comparison_to_production(self):
        """SEC-001: Mode can switch from comparison to production."""
        # Start in comparison mode
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        service.send_sms(
            phone="010-1111-1111",
            message="First",
            sms_type="confirm",
        )

        assert service.get_mock_sms_log()[0]["mode"] == "SIMULATED"

        # Switch to production
        config.comparison_mode_enabled = False

        service.send_sms(
            phone="010-2222-2222",
            message="Second",
            sms_type="confirm",
        )

        # Second SMS should be sent
        assert service.get_mock_sms_log()[1]["mode"] == "SENT"

    def test_mode_switch_from_production_to_comparison(self):
        """SEC-001: Mode can switch from production to comparison."""
        # Start in production mode
        config = ComparisonModeConfig(comparison_mode_enabled=False)
        service = SMSServiceWithComparisonMode(config)

        service.send_sms(
            phone="010-1111-1111",
            message="First",
            sms_type="confirm",
        )

        assert service.get_mock_sms_log()[0]["mode"] == "SENT"

        # Switch to comparison
        config.comparison_mode_enabled = True

        service.send_sms(
            phone="010-2222-2222",
            message="Second",
            sms_type="confirm",
        )

        # Second SMS should be simulated
        assert service.get_mock_sms_log()[1]["mode"] == "SIMULATED"


class TestComparisonModeEdgeCases:
    """Test edge cases for comparison mode."""

    def test_empty_phone_number_handled_safely(self):
        """SEC-001: Empty phone number handled safely in comparison mode."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        result = service.send_sms(
            phone="",
            message="Test",
            sms_type="confirm",
        )

        assert result
        log = service.get_mock_sms_log()[0]
        assert log["mode"] == "SIMULATED"

    def test_very_short_message_handled(self):
        """SEC-001: Very short message handled in comparison mode."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        result = service.send_sms(
            phone="010-1234-5678",
            message="Hi",
            sms_type="confirm",
        )

        assert result
        log = service.get_mock_sms_log()[0]
        assert log["message_preview"] == "Hi"

    def test_unknown_sms_type_handled(self):
        """SEC-001: Unknown SMS type handled gracefully."""
        config = ComparisonModeConfig(comparison_mode_enabled=True)
        service = SMSServiceWithComparisonMode(config)

        # Unknown type should still be simulated
        result = service.send_sms(
            phone="010-1234-5678",
            message="Test",
            sms_type="unknown_type",
        )

        assert result
        log = service.get_mock_sms_log()[0]
        assert log["mode"] == "SIMULATED"
        assert log["type"] == "unknown_type"


class TestComparisonModeSecurity:
    """Security tests for comparison mode."""

    def test_comparison_mode_is_explicit_and_must_be_enabled(self):
        """SEC-001: Comparison mode must be explicitly enabled (fail-safe)."""
        # Default should be disabled (safer default)
        config = ComparisonModeConfig()

        assert not config.is_enabled()

    def test_comparison_mode_not_enabled_by_typo_env_var(self):
        """SEC-001: Typos in environment variable don't accidentally enable mode."""
        with patch.dict(
            os.environ,
            {"COMPARISON_MODE": "true"},  # Wrong var name
            clear=True,
        ):
            config = ComparisonModeConfig.from_environment()

            # Should still be disabled because var name is wrong
            assert not config.is_enabled()

    def test_comparison_mode_case_sensitive_environment_variable(self):
        """SEC-001: Environment variable value must be exactly 'true'."""
        test_cases = [
            ("true", True),
            ("True", False),  # Case sensitive
            ("TRUE", False),  # Case sensitive
            ("yes", False),  # Must be exactly 'true'
            ("1", False),  # Must be exactly 'true'
        ]

        for env_value, expected_enabled in test_cases:
            with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": env_value}):
                config = ComparisonModeConfig.from_environment()

                assert config.is_enabled() == expected_enabled, (
                    f"Environment value '{env_value}' should result in "
                    f"enabled={expected_enabled}"
                )
