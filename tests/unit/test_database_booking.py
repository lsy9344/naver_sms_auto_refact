"""
Unit tests for BookingRepository.

Uses moto to mock DynamoDB for isolated testing without AWS credentials.
Covers all CRUD operations and error handling scenarios.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from decimal import Decimal

from moto import mock_aws
import boto3
from botocore.exceptions import ClientError

from src.database.dynamodb_client import BookingRepository
from src.database.exceptions import (
    DynamoDBException,
    NotFoundError,
    ThrottlingError,
    NetworkError,
    PermissionError,
)


@pytest.fixture
@mock_aws
def dynamodb_table():
    """Create a test DynamoDB table with moto mock."""
    dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")

    table = dynamodb.create_table(
        TableName="sms",
        KeySchema=[
            {"AttributeName": "booking_num", "KeyType": "HASH"},
            {"AttributeName": "phone", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "booking_num", "AttributeType": "S"},
            {"AttributeName": "phone", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    yield table


@pytest.fixture
def repository():
    """Create BookingRepository instance with mocked DynamoDB."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
        dynamodb.create_table(
            TableName="sms",
            KeySchema=[
                {"AttributeName": "booking_num", "KeyType": "HASH"},
                {"AttributeName": "phone", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "booking_num", "AttributeType": "S"},
                {"AttributeName": "phone", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        repo = BookingRepository(dynamodb_resource=dynamodb)
        yield repo


class TestBookingRepositoryGetBooking:
    """Tests for get_booking() method."""
    
    def test_get_booking_success(self, repository):
        """Should retrieve existing booking."""
        # Arrange
        booking_data = {
            "booking_num": "1051707_12345",
            "phone": "010-1234-5678",
            "name": "Kim Soo",
            "booking_time": "2025-10-20 14:30:00",
            "confirm_sms": True,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }
        repository.table.put_item(Item=booking_data)
        
        # Act
        result = repository.get_booking("1051707_12345", "010-1234-5678")
        
        # Assert
        assert result is not None
        assert result["booking_num"] == "1051707_12345"
        assert result["phone"] == "010-1234-5678"
        assert result["name"] == "Kim Soo"
    
    def test_get_booking_not_found_returns_none(self, repository):
        """Should return None when booking not found (AC-4a)."""
        # Act
        result = repository.get_booking("1051707_99999", "010-0000-0000")
        
        # Assert
        assert result is None
    
    def test_get_booking_preserves_all_fields(self, repository):
        """Should preserve all booking fields including extra_fields."""
        # Arrange
        booking_data = {
            "booking_num": "951291_54321",
            "phone": "010-9876-5432",
            "name": "Park Min",
            "booking_time": "2025-10-21 10:00:00",
            "confirm_sms": False,
            "remind_sms": True,
            "option_sms": True,
            "option_time": "2025-10-21",
            "custom_field": "future_value",
        }
        repository.table.put_item(Item=booking_data)
        
        # Act
        result = repository.get_booking("951291_54321", "010-9876-5432")
        
        # Assert
        assert result["custom_field"] == "future_value"


class TestBookingRepositoryCreateBooking:
    """Tests for create_booking() method."""
    
    def test_create_booking_success(self, repository):
        """Should create new booking record."""
        # Arrange
        booking_data = {
            "booking_num": "1120125_11111",
            "phone": "010-1111-1111",
            "name": "Lee Jung",
            "booking_time": "2025-10-22 15:00:00",
            "confirm_sms": True,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }
        
        # Act
        result = repository.create_booking(booking_data)
        
        # Assert
        assert result is True
        
        # Verify stored
        stored = repository.table.get_item(
            Key={"booking_num": "1120125_11111", "phone": "010-1111-1111"}
        )
        assert stored["Item"]["name"] == "Lee Jung"
    
    def test_create_booking_missing_required_field(self, repository):
        """Should raise DynamoDBException if required fields missing."""
        # Arrange
        incomplete_data = {
            "booking_num": "1285716_22222",
            "phone": "010-2222-2222",
            # Missing: name, booking_time
        }
        
        # Act & Assert
        with pytest.raises(DynamoDBException):
            repository.create_booking(incomplete_data)
    
    def test_create_booking_with_extra_fields(self, repository):
        """Should support extra fields for future expansion."""
        # Arrange
        booking_data = {
            "booking_num": "1462519_33333",
            "phone": "010-3333-3333",
            "name": "Choi Mi",
            "booking_time": "2025-10-23 11:30:00",
            "confirm_sms": False,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
            "customer_id": "naver_12345",
            "visit_count": 5,
            "booking_amount": 150000,
        }
        
        # Act
        result = repository.create_booking(booking_data)
        
        # Assert
        assert result is True
        stored = repository.table.get_item(
            Key={"booking_num": "1462519_33333", "phone": "010-3333-3333"}
        )
        assert stored["Item"]["customer_id"] == "naver_12345"
        assert stored["Item"]["visit_count"] == 5


class TestBookingRepositoryUpdateFlag:
    """Tests for update_flag() method."""
    
    def test_update_flag_success(self, repository):
        """Should update booking flag."""
        # Arrange
        booking_data = {
            "booking_num": "1473826_44444",
            "phone": "010-4444-4444",
            "name": "Song Ji",
            "booking_time": "2025-10-24 09:00:00",
            "confirm_sms": False,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }
        repository.table.put_item(Item=booking_data)
        
        # Act
        result = repository.update_flag("1473826_44444", "010-4444-4444", "confirm_sms", True)
        
        # Assert
        assert result is True
        
        # Verify update
        stored = repository.table.get_item(
            Key={"booking_num": "1473826_44444", "phone": "010-4444-4444"}
        )
        assert stored["Item"]["confirm_sms"] is True
    
    def test_update_multiple_flags(self, repository):
        """Should support updating different flags independently."""
        # Arrange
        booking_data = {
            "booking_num": "1466783_55555",
            "phone": "010-5555-5555",
            "name": "Han Na",
            "booking_time": "2025-10-25 13:00:00",
            "confirm_sms": False,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }
        repository.table.put_item(Item=booking_data)
        
        # Act
        repository.update_flag("1466783_55555", "010-5555-5555", "confirm_sms", True)
        repository.update_flag("1466783_55555", "010-5555-5555", "remind_sms", True)
        
        # Assert
        stored = repository.table.get_item(
            Key={"booking_num": "1466783_55555", "phone": "010-5555-5555"}
        )
        assert stored["Item"]["confirm_sms"] is True
        assert stored["Item"]["remind_sms"] is True
        assert stored["Item"]["option_sms"] is False
    
    def test_update_custom_flag(self, repository):
        """Should support custom flag names for extensibility."""
        # Arrange
        booking_data = {
            "booking_num": "867589_66666",
            "phone": "010-6666-6666",
            "name": "Yoon Ji",
            "booking_time": "2025-10-26 16:30:00",
            "confirm_sms": False,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }
        repository.table.put_item(Item=booking_data)
        
        # Act
        result = repository.update_flag("867589_66666", "010-6666-6666", "custom_notified", True)
        
        # Assert
        assert result is True


class TestBookingRepositoryScanUnnotifiedOptions:
    """Tests for scan_unnotified_options() method."""
    
    def test_scan_unnotified_options_empty(self, repository):
        """Should return empty dict when no unnotified options."""
        # Act
        result = repository.scan_unnotified_options()
        
        # Assert
        assert result == {}
    
    def test_scan_unnotified_options_single_store(self, repository):
        """Should find and group unnotified options by store."""
        # Arrange
        bookings = [
            {
                "booking_num": "1051707_1",
                "phone": "010-1111-1111",
                "name": "Customer 1",
                "booking_time": "2025-10-20 10:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
            {
                "booking_num": "1051707_2",
                "phone": "010-2222-2222",
                "name": "Customer 2",
                "booking_time": "2025-10-20 14:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
        ]
        for booking in bookings:
            repository.table.put_item(Item=booking)
        
        # Act
        result = repository.scan_unnotified_options()
        
        # Assert
        assert "1051707" in result
        assert result["1051707"]["start_time"] == "2025-10-20T10:00:00.000Z"
        assert result["1051707"]["end_time"] == "2025-10-20T14:00:00.000Z"
    
    def test_scan_unnotified_options_multiple_stores(self, repository):
        """Should handle multiple stores in one scan."""
        # Arrange
        bookings = [
            {
                "booking_num": "1051707_1",
                "phone": "010-1111-1111",
                "name": "Store 1 Customer",
                "booking_time": "2025-10-20 10:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
            {
                "booking_num": "951291_1",
                "phone": "010-2222-2222",
                "name": "Store 2 Customer",
                "booking_time": "2025-10-20 15:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
        ]
        for booking in bookings:
            repository.table.put_item(Item=booking)
        
        # Act
        result = repository.scan_unnotified_options()
        
        # Assert
        assert "1051707" in result
        assert "951291" in result
        assert result["1051707"]["start_time"] == "2025-10-20T10:00:00.000Z"
        assert result["951291"]["start_time"] == "2025-10-20T15:00:00.000Z"
    
    def test_scan_unnotified_options_sorting(self, repository):
        """Should sort bookings by booking_time within each store."""
        # Arrange
        bookings = [
            {
                "booking_num": "1051707_3",
                "phone": "010-3333-3333",
                "name": "Late booking",
                "booking_time": "2025-10-20 18:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
            {
                "booking_num": "1051707_1",
                "phone": "010-1111-1111",
                "name": "Early booking",
                "booking_time": "2025-10-20 08:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
            {
                "booking_num": "1051707_2",
                "phone": "010-2222-2222",
                "name": "Middle booking",
                "booking_time": "2025-10-20 12:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
        ]
        for booking in bookings:
            repository.table.put_item(Item=booking)
        
        # Act
        result = repository.scan_unnotified_options()
        
        # Assert
        assert result["1051707"]["start_time"] == "2025-10-20T08:00:00.000Z"
        assert result["1051707"]["end_time"] == "2025-10-20T18:00:00.000Z"
    
    def test_scan_ignores_notified_options(self, repository):
        """Should ignore bookings with option_sms=True."""
        # Arrange
        bookings = [
            {
                "booking_num": "1051707_1",
                "phone": "010-1111-1111",
                "name": "Not notified",
                "booking_time": "2025-10-20 10:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": False,
                "option_time": "",
            },
            {
                "booking_num": "1051707_2",
                "phone": "010-2222-2222",
                "name": "Already notified",
                "booking_time": "2025-10-20 14:00:00",
                "confirm_sms": True,
                "remind_sms": True,
                "option_sms": True,
                "option_time": "",
            },
        ]
        for booking in bookings:
            repository.table.put_item(Item=booking)
        
        # Act
        result = repository.scan_unnotified_options()
        
        # Assert
        assert "1051707" in result
        # Should only have times from the one unnotified booking
        assert result["1051707"]["start_time"] == "2025-10-20T10:00:00.000Z"
        assert result["1051707"]["end_time"] == "2025-10-20T10:00:00.000Z"


class TestBookingRepositoryErrorHandling:
    """Tests for error handling and retry logic."""
    
    def test_get_booking_network_error(self, repository):
        """Should raise NetworkError on network failure."""
        # Arrange
        with patch.object(repository.table, "get_item", side_effect=OSError("Connection refused")):
            # Act & Assert
            with pytest.raises(NetworkError):
                repository.get_booking("1051707_12345", "010-1234-5678")
    
    def test_create_booking_network_error(self, repository):
        """Should raise NetworkError on network failure during create."""
        # Arrange
        booking_data = {
            "booking_num": "1051707_12345",
            "phone": "010-1234-5678",
            "name": "Test",
            "booking_time": "2025-10-20 10:00:00",
            "confirm_sms": False,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }
        
        with patch.object(repository.table, "put_item", side_effect=OSError("Connection refused")):
            # Act & Assert
            with pytest.raises(NetworkError):
                repository.create_booking(booking_data)
    
    def test_throttling_error_retry(self, repository):
        """Should retry on throttling error."""
        # Arrange
        booking_data = {
            "booking_num": "1051707_12345",
            "phone": "010-1234-5678",
            "name": "Test",
            "booking_time": "2025-10-20 10:00:00",
            "confirm_sms": False,
            "remind_sms": False,
            "option_sms": False,
            "option_time": "",
        }
        
        # Mock to fail twice then succeed
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                error_response = {"Error": {"Code": "ProvisionedThroughputExceededException"}}
                raise ClientError(error_response, "PutItem")
            return None
        
        with patch.object(repository.table, "put_item", side_effect=side_effect):
            # Act
            result = repository.create_booking(booking_data)
        
        # Assert
        assert result is True
        assert call_count == 3


class TestPhoneMasking:
    """Tests for phone number masking in logs."""
    
    def test_phone_masking_with_hyphens(self):
        """Should mask phone number correctly."""
        from src.utils.logger import mask_phone
        
        result = mask_phone("010-1234-5678")
        assert result == "010-****-5678"
    
    def test_phone_masking_without_hyphens(self):
        """Should normalize and mask phone number."""
        from src.utils.logger import mask_phone
        
        result = mask_phone("01012345678")
        assert result == "010-****-5678"
    
    def test_phone_masking_invalid(self):
        """Should handle invalid phone numbers."""
        from src.utils.logger import mask_phone
        
        assert mask_phone("") == "unknown"
        assert mask_phone("123") == "invalid"
