"""
End-to-end smoke tests for Lambda handler orchestration.

Tests the main integration flow with mocked external services.
Implements AC 9 requirements for automated coverage.
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import the main module to ensure coverage tracking
import src.main
from src.main import lambda_handler, process_all_bookings
from src.domain.booking import Booking
from src.rules.engine import ActionResult


class MockContext:
    """Mock Lambda context for testing."""

    def __init__(self):
        self.function_name = "naver-sms-automation-test"
        self.request_id = "test-request-id"
        self.invoked_function_arn = "arn:aws:lambda:test:test"


@pytest.fixture
def mock_settings():
    """Mock Settings that returns test credentials."""
    with patch("src.main.Settings") as mock_settings_class:
        mock_instance = Mock()
        mock_instance.load_naver_credentials.return_value = {
            "username": "test_user",
            "password": "test_pass",
        }
        mock_instance.load_sens_credentials.return_value = {
            "access_key": "test_access",
            "secret_key": "test_secret",
            "service_id": "test_service",
        }
        mock_instance.load_telegram_credentials.return_value = {
            "bot_token": "test_token",
            "chat_id": "test_chat",
        }
        mock_settings_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_dynamodb():
    """Mock DynamoDB resource."""
    with patch("src.main.dynamodb") as mock_db:
        yield mock_db


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager for cookie management."""
    with patch("src.main.SessionManager") as mock_mgr_class:
        mock_mgr = Mock()
        mock_mgr.get_cookies.return_value = []
        mock_mgr_class.return_value = mock_mgr
        yield mock_mgr


@pytest.fixture
def mock_authenticator():
    """Mock NaverAuthenticator for login."""
    with patch("src.main.NaverAuthenticator") as mock_auth_class:
        mock_auth = Mock()
        mock_auth.login.return_value = [{"name": "test_cookie", "value": "test_value"}]
        mock_auth.get_session.return_value = Mock()
        mock_auth.cleanup.return_value = None
        mock_auth_class.return_value = mock_auth
        yield mock_auth


@pytest.fixture
def mock_booking_api():
    """Mock NaverBookingAPIClient for booking retrieval."""
    with patch("src.main.NaverBookingAPIClient") as mock_api_class:
        mock_api = Mock()

        # Return test bookings
        test_booking = Booking(
            booking_num="1051707_12345",
            phone="010-1234-5678",
            name="Test Customer",
            booking_time="2025-10-19 20:30:00",
            book_id=12345,
            biz_id="1051707",
            option=False,
            reserve_at=datetime(2025, 10, 19, 20, 30),
            status="RC03",
        )

        mock_api.get_all_confirmed_bookings.return_value = [test_booking]
        mock_api.get_all_completed_bookings.return_value = []
        mock_api_class.return_value = mock_api
        yield mock_api


@pytest.fixture
def mock_rule_engine():
    """Mock RuleEngine for processing."""
    with patch("src.main.RuleEngine") as mock_engine_class:
        mock_engine = Mock()
        mock_engine.process_booking.return_value = [
            ActionResult(
                rule_name="Test Rule", action_type="send_sms", success=True, message="SMS sent"
            )
        ]
        mock_engine_class.return_value = mock_engine
        yield mock_engine


@pytest.fixture
def mock_stores_yaml():
    """Mock stores.yaml configuration."""
    stores_config = {
        "stores": {
            "1051707": {
                "name": "다비스튜디오 화성점",
                "fromNumber": "01055814318",
                "templates": {"guide": "1051707"},
            }
        }
    }
    with patch("builtins.open", create=True) as mock_open:
        with patch("yaml.safe_load", return_value=stores_config):
            yield stores_config


@pytest.fixture
def mock_register_conditions():
    """Mock register_conditions function."""
    with patch("src.main.register_conditions") as mock_reg:
        yield mock_reg


@pytest.fixture
def mock_register_actions():
    """Mock register_actions function."""
    with patch("src.main.register_actions") as mock_reg:
        yield mock_reg


@pytest.fixture
def mock_booking_repo():
    """Mock BookingRepository."""
    with patch("src.main.BookingRepository") as mock_repo_class:
        mock_repo = Mock()
        mock_repo.get_booking.return_value = None  # New booking
        mock_repo_class.return_value = mock_repo
        yield mock_repo


@pytest.fixture
def mock_sms_service():
    """Mock SensSmsClient."""
    with patch("src.main.SensSmsClient") as mock_sms_class:
        mock_sms = Mock()
        mock_sms_class.return_value = mock_sms
        yield mock_sms


@pytest.fixture
def mock_telegram():
    """Mock Telegram API requests."""
    with patch("src.main.requests.post") as mock_post:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        yield mock_post


def test_lambda_handler_success(
    mock_settings,
    mock_dynamodb,
    mock_session_manager,
    mock_authenticator,
    mock_booking_api,
    mock_rule_engine,
    mock_stores_yaml,
    mock_register_conditions,
    mock_register_actions,
    mock_booking_repo,
    mock_sms_service,
    mock_telegram,
):
    """
    Test successful Lambda handler execution.

    Verifies:
    - Handler returns 200 status code
    - Response contains expected summary fields
    - Authentication flow is called
    - Booking API is called
    - Rule engine is initialized and used
    - Telegram summary is sent
    """
    with patch("src.main.setup_logging_redaction"):
        result = lambda_handler({}, MockContext())

    # Assert successful response
    assert result["statusCode"] == 200

    # Parse response body
    body = json.loads(result["body"])
    assert body["message"] == "Naver SMS automation completed successfully"
    assert "bookings_processed" in body
    assert "actions_executed" in body
    assert "actions_succeeded" in body
    assert "timestamp" in body

    # Verify authentication was called
    mock_authenticator.login.assert_called_once()
    mock_authenticator.get_session.assert_called_once()
    mock_authenticator.cleanup.assert_called_once()

    # Verify booking API was called
    mock_booking_api.get_all_confirmed_bookings.assert_called_once()
    mock_booking_api.get_all_completed_bookings.assert_called_once()

    # Verify rule engine was initialized
    assert mock_rule_engine.process_booking.called

    # Verify Telegram summary was sent
    assert mock_telegram.called


def test_lambda_handler_error_handling(
    mock_settings, mock_dynamodb, mock_session_manager, mock_stores_yaml
):
    """
    Test Lambda handler error handling.

    Verifies:
    - Handler returns 500 status code on error
    - Error message is included in response
    - Telegram error notification is sent
    """
    with patch("src.main.setup_logging_redaction"):
        with patch("src.main.NaverAuthenticator", side_effect=Exception("Test error")):
            with patch("src.main.requests.post") as mock_telegram:
                result = lambda_handler({}, MockContext())

    # Assert error response
    assert result["statusCode"] == 500

    # Parse response body
    body = json.loads(result["body"])
    assert body["error"] == "Lambda execution failed"
    assert "Test error" in body["message"]
    assert "timestamp" in body

    # Verify Telegram error notification was sent
    assert mock_telegram.called


def test_process_all_bookings_success():
    """
    Test process_all_bookings function.

    Verifies:
    - Bookings are processed through rule engine
    - Summary statistics are calculated correctly
    - Context is built with required fields
    """
    # Create test booking
    booking = Booking(
        booking_num="1051707_12345",
        phone="010-1234-5678",
        name="Test Customer",
        booking_time="2025-10-19 20:30:00",
        book_id=12345,
        biz_id="1051707",
        option=False,
        reserve_at=datetime(2025, 10, 19, 20, 30),
        status="RC03",
    )

    # Mock engine
    mock_engine = Mock()
    mock_engine.process_booking.return_value = [
        ActionResult(
            rule_name="Test Rule", action_type="send_sms", success=True, message="SMS sent"
        )
    ]

    # Mock booking repo
    mock_repo = Mock()
    mock_repo.get_booking.return_value = None

    # Mock settings
    mock_settings_obj = Mock()

    # Call function
    results, summary = process_all_bookings(
        bookings=[booking], engine=mock_engine, booking_repo=mock_repo, settings=mock_settings_obj
    )

    # Verify results
    assert len(results) == 1
    assert summary["bookings_processed"] == 1
    assert summary["actions_executed"] == 1
    assert summary["actions_succeeded"] == 1
    assert summary["sms_sent"] == 1
    assert summary["actions_failed"] == 0

    # Verify engine was called with correct context
    mock_engine.process_booking.assert_called_once()
    call_args = mock_engine.process_booking.call_args[0][0]
    assert call_args["booking"] == booking
    assert call_args["db_record"] is None
    assert "current_time" in call_args
    assert call_args["settings"] == mock_settings_obj


def test_process_all_bookings_with_failures():
    """
    Test process_all_bookings handles action failures.

    Verifies:
    - Failed actions are counted correctly
    - Processing continues after failures
    """
    booking = Booking(
        booking_num="1051707_12345",
        phone="010-1234-5678",
        name="Test Customer",
        booking_time="2025-10-19 20:30:00",
        book_id=12345,
        biz_id="1051707",
        option=False,
        reserve_at=datetime(2025, 10, 19, 20, 30),
        status="RC03",
    )

    # Mock engine with mixed results
    mock_engine = Mock()
    mock_engine.process_booking.return_value = [
        ActionResult(
            rule_name="Test Rule 1", action_type="send_sms", success=True, message="SMS sent"
        ),
        ActionResult(
            rule_name="Test Rule 2",
            action_type="update_flag",
            success=False,
            message="Update failed",
            error="DynamoDB error",
        ),
    ]

    mock_repo = Mock()
    mock_repo.get_booking.return_value = None
    mock_settings_obj = Mock()

    results, summary = process_all_bookings(
        bookings=[booking], engine=mock_engine, booking_repo=mock_repo, settings=mock_settings_obj
    )

    # Verify mixed results
    assert len(results) == 2
    assert summary["actions_succeeded"] == 1
    assert summary["actions_failed"] == 1
    assert summary["sms_sent"] == 1


def test_process_all_bookings_handles_exceptions():
    """
    Test process_all_bookings handles exceptions gracefully.

    Verifies:
    - Exceptions are caught and logged
    - Processing continues for remaining bookings
    - Failed bookings are counted
    """
    booking1 = Booking(
        booking_num="1051707_1",
        phone="010-1111-1111",
        name="Test 1",
        booking_time="2025-10-19 20:30:00",
        book_id=1,
        biz_id="1051707",
        option=False,
        reserve_at=datetime(2025, 10, 19, 20, 30),
        status="RC03",
    )

    booking2 = Booking(
        booking_num="1051707_2",
        phone="010-2222-2222",
        name="Test 2",
        booking_time="2025-10-19 21:30:00",
        book_id=2,
        biz_id="1051707",
        option=False,
        reserve_at=datetime(2025, 10, 19, 21, 30),
        status="RC03",
    )

    # Mock engine that raises exception on first booking
    mock_engine = Mock()
    mock_engine.process_booking.side_effect = [
        Exception("Processing error"),
        [
            ActionResult(
                rule_name="Test Rule", action_type="send_sms", success=True, message="SMS sent"
            )
        ],
    ]

    mock_repo = Mock()
    mock_repo.get_booking.return_value = None
    mock_settings_obj = Mock()

    results, summary = process_all_bookings(
        bookings=[booking1, booking2],
        engine=mock_engine,
        booking_repo=mock_repo,
        settings=mock_settings_obj,
    )

    # Verify only second booking processed
    assert len(results) == 1
    assert summary["bookings_processed"] == 1
    assert summary["actions_failed"] == 1  # First booking exception
    assert summary["actions_succeeded"] == 1  # Second booking success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
