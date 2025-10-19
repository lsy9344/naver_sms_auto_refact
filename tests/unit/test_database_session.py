"""
Unit tests for SessionRepository.

Uses moto to mock DynamoDB for isolated testing without AWS credentials.
Covers session lifecycle and cookie management.
"""

import json
import pytest
from unittest.mock import patch
from botocore.exceptions import ClientError

from moto import mock_aws
import boto3

from src.database.dynamodb_client import SessionRepository
from src.domain.session import Session
from src.database.exceptions import (
    DynamoDBException,
    NetworkError,
    PermissionError,
)


@pytest.fixture
def repository():
    """Create SessionRepository instance with mocked DynamoDB."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-2")
        dynamodb.create_table(
            TableName="session",
            KeySchema=[
                {"AttributeName": "id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        repo = SessionRepository(dynamodb_resource=dynamodb)
        yield repo


class TestSessionRepositoryGetSession:
    """Tests for get_session() method."""
    
    def test_get_session_not_found_returns_none(self, repository):
        """Should return None when session not found."""
        # Act
        result = repository.get_session()
        
        # Assert
        assert result is None
    
    def test_get_session_success(self, repository):
        """Should retrieve existing session."""
        # Arrange
        cookies_json = json.dumps([
            {"name": "NID_AUT", "value": "abc123"},
            {"name": "NID_SES", "value": "def456"},
        ])
        repository.table.put_item(Item={
            "id": "1",
            "cookies": cookies_json,
        })
        
        # Act
        result = repository.get_session()
        
        # Assert
        assert result is not None
        assert isinstance(result, Session)
        assert result.id == "1"
        assert result.cookies == cookies_json
    
    def test_get_session_returns_session_object(self, repository):
        """Should return Session domain object."""
        # Arrange
        cookies_json = json.dumps([
            {"name": "naver_cookie", "value": "xyz789"}
        ])
        repository.table.put_item(Item={
            "id": "1",
            "cookies": cookies_json,
        })
        
        # Act
        result = repository.get_session()
        
        # Assert
        assert isinstance(result, Session)
        cookies_list = result.get_cookies_list()
        assert len(cookies_list) == 1
        assert cookies_list[0]["name"] == "naver_cookie"


class TestSessionRepositorySaveSession:
    """Tests for save_session() method."""
    
    def test_save_session_success(self, repository):
        """Should save session cookies."""
        # Arrange
        cookies_json = json.dumps([
            {"name": "NID_AUT", "value": "abc123"},
        ])
        
        # Act
        result = repository.save_session(cookies_json)
        
        # Assert
        assert result is True
        
        # Verify stored
        stored = repository.table.get_item(Key={"id": "1"})
        assert stored["Item"]["cookies"] == cookies_json
    
    def test_save_session_overwrites_existing(self, repository):
        """Should overwrite existing session (upsert semantics)."""
        # Arrange
        old_cookies = json.dumps([{"name": "old_cookie", "value": "old"}])
        new_cookies = json.dumps([{"name": "new_cookie", "value": "new"}])
        
        repository.table.put_item(Item={"id": "1", "cookies": old_cookies})
        
        # Act
        result = repository.save_session(new_cookies)
        
        # Assert
        assert result is True
        stored = repository.table.get_item(Key={"id": "1"})
        assert stored["Item"]["cookies"] == new_cookies
    
    def test_save_session_empty_cookies(self, repository):
        """Should handle empty cookies list."""
        # Arrange
        empty_cookies = json.dumps([])
        
        # Act
        result = repository.save_session(empty_cookies)
        
        # Assert
        assert result is True
        stored = repository.table.get_item(Key={"id": "1"})
        assert stored["Item"]["cookies"] == empty_cookies
    
    def test_save_session_multiple_cookies(self, repository):
        """Should handle multiple cookies."""
        # Arrange
        cookies_json = json.dumps([
            {"name": "cookie1", "value": "value1", "domain": ".naver.com"},
            {"name": "cookie2", "value": "value2", "path": "/"},
            {"name": "cookie3", "value": "value3", "httpOnly": True},
        ])
        
        # Act
        result = repository.save_session(cookies_json)
        
        # Assert
        assert result is True
        stored = repository.table.get_item(Key={"id": "1"})
        cookies_list = json.loads(stored["Item"]["cookies"])
        assert len(cookies_list) == 3


class TestSessionRepositoryDeleteSession:
    """Tests for delete_session() method."""
    
    def test_delete_session_success(self, repository):
        """Should delete session."""
        # Arrange
        cookies_json = json.dumps([{"name": "test", "value": "value"}])
        repository.table.put_item(Item={"id": "1", "cookies": cookies_json})
        
        # Verify exists
        stored = repository.table.get_item(Key={"id": "1"})
        assert "Item" in stored
        
        # Act
        result = repository.delete_session()
        
        # Assert
        assert result is True
        
        # Verify deleted
        stored = repository.table.get_item(Key={"id": "1"})
        assert "Item" not in stored
    
    def test_delete_session_not_found(self, repository):
        """Should succeed even if session doesn't exist."""
        # Act
        result = repository.delete_session()
        
        # Assert
        assert result is True
    
    def test_delete_session_cache_invalidation(self, repository):
        """Should invalidate cache (prepare for fresh login)."""
        # Arrange
        cookies_json = json.dumps([{"name": "expired", "value": "old"}])
        repository.table.put_item(Item={"id": "1", "cookies": cookies_json})
        
        # Act
        repository.delete_session()
        result = repository.get_session()
        
        # Assert
        assert result is None


class TestSessionDomainModel:
    """Tests for Session domain model."""
    
    def test_session_from_cookies_list(self):
        """Should create Session from cookies list."""
        # Arrange
        cookies_list = [
            {"name": "NID_AUT", "value": "abc123"},
            {"name": "NID_SES", "value": "def456"},
        ]
        
        # Act
        session = Session.from_cookies_list(cookies_list)
        
        # Assert
        assert session.id == "1"
        assert session.cookies is not None
        retrieved = session.get_cookies_list()
        assert len(retrieved) == 2
        assert retrieved[0]["name"] == "NID_AUT"
    
    def test_session_get_cookies_list(self):
        """Should parse cookies JSON."""
        # Arrange
        cookies_json = json.dumps([
            {"name": "cookie1", "value": "value1"},
            {"name": "cookie2", "value": "value2"},
        ])
        session = Session(id="1", cookies=cookies_json)
        
        # Act
        cookies_list = session.get_cookies_list()
        
        # Assert
        assert len(cookies_list) == 2
        assert cookies_list[0]["name"] == "cookie1"
    
    def test_session_is_empty_true(self):
        """Should detect empty session."""
        # Arrange
        session = Session(id="1", cookies="[]")
        
        # Act
        result = session.is_empty()
        
        # Assert
        assert result is True
    
    def test_session_is_empty_false(self):
        """Should detect non-empty session."""
        # Arrange
        cookies_json = json.dumps([{"name": "test", "value": "value"}])
        session = Session(id="1", cookies=cookies_json)
        
        # Act
        result = session.is_empty()
        
        # Assert
        assert result is False
    
    def test_session_to_dict(self):
        """Should convert to dict for DynamoDB storage."""
        # Arrange
        cookies_json = json.dumps([{"name": "test", "value": "value"}])
        session = Session(id="1", cookies=cookies_json)
        
        # Act
        result = session.to_dict()
        
        # Assert
        assert result["id"] == "1"
        assert result["cookies"] == cookies_json
    
    def test_session_malformed_json_raises_error(self):
        """Should raise error on malformed cookies JSON."""
        # Arrange
        session = Session(id="1", cookies="not valid json")
        
        # Act & Assert
        with pytest.raises(ValueError):
            session.get_cookies_list()


class TestSessionRepositoryErrorHandling:
    """Tests for error handling."""
    
    def test_get_session_network_error(self, repository):
        """Should raise NetworkError on network failure."""
        # Arrange
        with patch.object(repository.table, "get_item", side_effect=OSError("Connection refused")):
            # Act & Assert
            with pytest.raises(NetworkError):
                repository.get_session()
    
    def test_save_session_network_error(self, repository):
        """Should raise NetworkError on network failure."""
        # Arrange
        with patch.object(repository.table, "put_item", side_effect=OSError("Connection refused")):
            # Act & Assert
            with pytest.raises(NetworkError):
                repository.save_session('[]')
    
    def test_delete_session_network_error(self, repository):
        """Should raise NetworkError on network failure."""
        # Arrange
        with patch.object(repository.table, "delete_item", side_effect=OSError("Connection refused")):
            # Act & Assert
            with pytest.raises(NetworkError):
                repository.delete_session()


class TestSessionRepositoryLifecycle:
    """Integration tests for session lifecycle."""
    
    def test_session_lifecycle(self, repository):
        """Should handle complete session lifecycle."""
        # 1. Session doesn't exist initially
        assert repository.get_session() is None
        
        # 2. Save session
        cookies_json = json.dumps([{"name": "naver_auth", "value": "token123"}])
        assert repository.save_session(cookies_json) is True
        
        # 3. Retrieve session
        session = repository.get_session()
        assert session is not None
        assert not session.is_empty()
        
        # 4. Update session with new cookies
        new_cookies_json = json.dumps([
            {"name": "naver_auth", "value": "token456"},
            {"name": "naver_session", "value": "sess789"},
        ])
        assert repository.save_session(new_cookies_json) is True
        
        # 5. Verify update
        updated_session = repository.get_session()
        cookies_list = updated_session.get_cookies_list()
        assert len(cookies_list) == 2
        
        # 6. Delete session (cache invalidation)
        assert repository.delete_session() is True
        
        # 7. Verify deletion
        assert repository.get_session() is None
