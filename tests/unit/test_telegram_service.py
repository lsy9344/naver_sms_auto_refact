"""
Unit tests for TelegramBotClient service.

Tests the Telegram Bot API notification client with mocked HTTP requests.
"""

import json
from unittest.mock import Mock, patch

import pytest

from src.notifications.telegram_service import TelegramBotClient, TelegramServiceError


class TestTelegramBotClient:
    """Test suite for TelegramBotClient."""

    def test_init_with_credentials(self):
        """Test client initialization with provided credentials."""
        client = TelegramBotClient(
            bot_token="bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="987654321",
        )

        assert client.bot_token == "bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert client.chat_id == "987654321"
        assert client.api_url == (
            "https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/sendMessage"
        )

    def test_init_without_credentials(self):
        """Test client initialization without credentials."""
        with patch.dict("os.environ", {}, clear=True):
            client = TelegramBotClient()

            assert client.bot_token is None
            assert client.chat_id is None
            assert client.api_url is None

    def test_send_message_success(self):
        """Test successful message sending."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
        )

        client.send_message("Test message")

        # Verify HTTP call
        assert mock_session.post.called
        call_args = mock_session.post.call_args
        assert "https://api.telegram.org/bottest_token/sendMessage" in call_args[0]

        # Verify payload
        payload = json.loads(call_args[1]["data"])
        assert payload["chat_id"] == "test_chat"
        assert payload["text"] == "Test message"
        assert payload["parse_mode"] == "Markdown"

    def test_send_message_with_custom_parse_mode(self):
        """Test message sending with custom parse mode."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
        )

        client.send_message("Test message", parse_mode="HTML")

        payload = json.loads(mock_session.post.call_args[1]["data"])
        assert payload["parse_mode"] == "HTML"

    def test_send_message_without_parse_mode(self):
        """Test message sending without parse mode."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
        )

        client.send_message("Test message", parse_mode=None)

        payload = json.loads(mock_session.post.call_args[1]["data"])
        assert "parse_mode" not in payload

    def test_send_message_when_not_configured(self):
        """Test that send_message skips when client not configured."""
        with patch.dict("os.environ", {}, clear=True):
            client = TelegramBotClient()

            # Should not raise, just skip silently
            client.send_message("Test message")

    def test_send_notification_with_template_params(self):
        """Test send_notification with template parameter substitution."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
        )

        client.send_notification(
            message="Hello {{name}}, your booking {{booking_id}} is confirmed!",
            template_params={"name": "홍길동", "booking_id": "12345"},
        )

        payload = json.loads(mock_session.post.call_args[1]["data"])
        assert payload["text"] == "Hello 홍길동, your booking 12345 is confirmed!"

    def test_send_notification_without_template_params(self):
        """Test send_notification without template parameters."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
        )

        client.send_notification(message="Plain message")

        payload = json.loads(mock_session.post.call_args[1]["data"])
        assert payload["text"] == "Plain message"

    def test_retry_on_transient_error(self):
        """Test retry logic on transient HTTP errors."""
        mock_session = Mock()

        # First call fails, second succeeds
        mock_fail = Mock()
        mock_fail.status_code = 500
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {"ok": True}

        mock_session.post.side_effect = [Exception("Network error"), mock_success]

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
            retry_delay_seconds=0.01,  # Speed up test
        )

        client.send_message("Test message")

        # Should have retried
        assert mock_session.post.call_count == 2

    def test_rate_limit_handling(self):
        """Test rate limit response handling (429)."""
        mock_session = Mock()

        # Rate limited response
        mock_rate_limit = Mock()
        mock_rate_limit.status_code = 429
        mock_rate_limit.headers = {"Retry-After": "60"}

        mock_session.post.return_value = mock_rate_limit

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
            retry_delay_seconds=0.01,
        )

        result = client.send_message("Test message")

        # Rate limit should cause immediate failure (no retry to avoid Lambda timeout)
        assert mock_session.post.call_count == 1
        assert result is False

    def test_throttling_delay_after_success(self):
        """Test that throttling delay is applied after successful message delivery."""
        import time

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
            throttle_seconds=0.05,  # 50ms delay for testing
        )

        start_time = time.time()
        result = client.send_message("Test message")
        elapsed = time.time() - start_time

        # Should succeed and include throttle delay
        assert result is True
        assert elapsed >= 0.05  # At least 50ms elapsed due to throttle
        assert mock_session.post.call_count == 1

    def test_no_throttling_when_disabled(self):
        """Test that no throttling occurs when throttle_seconds is 0."""
        import time

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
            throttle_seconds=0.0,  # Throttling disabled
        )

        start_time = time.time()
        result = client.send_message("Test message")
        elapsed = time.time() - start_time

        # Should succeed without delay
        assert result is True
        assert elapsed < 0.05  # Should complete quickly without throttle delay
        assert mock_session.post.call_count == 1

    def test_api_error_response(self):
        """Test handling of Telegram API error responses."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: chat not found",
        }
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="invalid_chat",
            http_client=mock_session,
            max_retries=1,
        )

        # Should not raise, but log error and return
        client.send_message("Test message")

    def test_http_error_response(self):
        """Test handling of HTTP error status codes."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
            max_retries=1,
        )

        # Should not raise, but log error and return
        client.send_message("Test message")

    def test_get_client_status(self):
        """Test client status reporting."""
        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            max_retries=5,
            retry_delay_seconds=1.5,
            throttle_seconds=0.2,
        )

        status = client.get_client_status()

        assert status["bot_configured"] is True
        assert status["chat_id_configured"] is True
        assert status["api_url"] == "https://api.telegram.org/bottest_token/sendMessage"
        assert status["max_retries"] == 5
        assert status["retry_delay_seconds"] == 1.5
        assert status["throttle_seconds"] == 0.2

    def test_get_client_status_not_configured(self):
        """Test client status when not configured."""
        with patch.dict("os.environ", {}, clear=True):
            client = TelegramBotClient()
            status = client.get_client_status()

            assert status["bot_configured"] is False
            assert status["chat_id_configured"] is False
            assert status["api_url"] is None

    def test_send_message_with_custom_chat_id(self):
        """Test sending message to a different chat ID."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_session.post.return_value = mock_response

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="default_chat",
            http_client=mock_session,
        )

        client.send_message("Test message", chat_id="custom_chat")

        payload = json.loads(mock_session.post.call_args[1]["data"])
        assert payload["chat_id"] == "custom_chat"

    def test_markdown_parse_error_falls_back_to_plain_text(self):
        """Telegram markdown parse errors should retry without parse mode."""
        mock_session = Mock()

        parse_error_response = Mock()
        parse_error_response.status_code = 400
        parse_error_response.text = (
            '{"ok":false,"error_code":400,'
            '"description":"Bad Request: can\\\'t parse entities: '
            "Can\\'t find end of the entity starting at byte offset 18\"}"
        )

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {"ok": True}

        mock_session.post.side_effect = [parse_error_response, success_response]

        client = TelegramBotClient(
            bot_token="test_token",
            chat_id="test_chat",
            http_client=mock_session,
        )

        client.send_message("Message with underscore_value")

        assert mock_session.post.call_count == 2

        first_payload = json.loads(mock_session.post.call_args_list[0][1]["data"])
        second_payload = json.loads(mock_session.post.call_args_list[1][1]["data"])

        assert first_payload["parse_mode"] == "Markdown"
        assert "parse_mode" not in second_payload
