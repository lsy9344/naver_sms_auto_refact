"""
Security Tests for Comparison Mode Configuration

Validates the COMPARISON_MODE_ENABLED security feature to prevent
accidental real SMS sends during validation campaigns.
"""

import os
from unittest.mock import patch

from src.config.settings import Settings, COMPARISON_MODE_ENABLED


def test_comparison_mode_case_sensitive_lowercase_true():
    """SEC-001: COMPARISON_MODE_ENABLED only accepts lowercase 'true'."""
    # Test that lowercase 'true' enables comparison mode
    with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": "true"}):
        # Reload the module to pick up the new environment variable
        import importlib
        import src.config.settings

        importlib.reload(src.config.settings)

        # Test the reloaded comparison mode value
        assert src.config.settings.COMPARISON_MODE_ENABLED is True


def test_comparison_mode_case_sensitive_uppercase_true():
    """SEC-001: COMPARISON_MODE_ENABLED rejects uppercase 'TRUE'."""
    # Test that uppercase 'TRUE' does NOT enable comparison mode (security)
    with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": "TRUE"}):
        import importlib
        import src.config.settings

        importlib.reload(src.config.settings)

        # This is the security feature - uppercase TRUE should NOT enable comparison mode
        assert src.config.settings.COMPARISON_MODE_ENABLED is False


def test_comparison_mode_case_sensitive_mixed_case():
    """SEC-001: COMPARISON_MODE_ENABLED rejects mixed case."""
    # Test that mixed case does NOT enable comparison mode
    with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": "True"}):
        import importlib
        import src.config.settings

        importlib.reload(src.config.settings)

        assert src.config.settings.COMPARISON_MODE_ENABLED is False

    with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": "True"}):
        import importlib
        import src.config.settings

        importlib.reload(src.config.settings)

        assert src.config.settings.COMPARISON_MODE_ENABLED is False


def test_comparison_mode_default_false():
    """SEC-001: COMPARISON_MODE_ENABLED defaults to false."""
    # Test default behavior when not set
    with patch.dict(os.environ, {}, clear=True):
        # Clear all environment variables temporarily and reload
        import importlib
        import src.config.settings

        importlib.reload(src.config.settings)

        # Default should be false
        assert src.config.settings.COMPARISON_MODE_ENABLED is False


def test_settings_class_comparison_mode():
    """SEC-001: Settings class properly reflects comparison mode setting."""
    with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": "true"}):
        import importlib
        import src.config.settings

        importlib.reload(src.config.settings)

        settings = src.config.settings.Settings()
        assert settings.is_comparison_mode_enabled() is True


def test_settings_class_comparison_mode_disabled():
    """SEC-001: Settings class properly handles disabled comparison mode."""
    with patch.dict(os.environ, {"COMPARISON_MODE_ENABLED": "false"}):
        import importlib
        import src.config.settings

        importlib.reload(src.config.settings)

        settings = src.config.settings.Settings()
        assert settings.is_comparison_mode_enabled() is False


if __name__ == "__main__":
    # Run the tests
    test_comparison_mode_case_sensitive_lowercase_true()
    test_comparison_mode_case_sensitive_uppercase_true()
    test_comparison_mode_case_sensitive_mixed_case()
    test_comparison_mode_default_false()
    print("All security tests passed!")
