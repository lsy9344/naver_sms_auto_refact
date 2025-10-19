# Dependency Injection (DI) Integration Guide

This document describes how to use the `Settings` configuration object with dependency injection patterns across the Naver SMS Automation application.

## Overview

The refactored application uses dependency injection to decouple configuration management from business logic. All modules receive their configuration needs via constructor parameters rather than importing configuration directly.

**Benefits:**
- Easy testing: Mock Settings for unit tests
- Loose coupling: Modules don't depend on configuration location
- Flexibility: Easy to swap implementations
- Testability: Each component can be tested in isolation

## Pattern

### Basic DI Pattern

```python
from src.config.settings import Settings

class MyService:
    """Service that depends on configuration."""
    
    def __init__(self, settings: Settings):
        """Initialize with injected Settings instance.
        
        Args:
            settings: Settings instance with all configuration
        """
        self.settings = settings
        self.region = settings.aws_region
        self.table_name = settings.dynamodb_table_sms
```

### Usage in Main Handler

```python
from src.config.settings import get_settings
from src.database.dynamodb_client import DynamoDBClient
from src.auth.naver_login import NaverAuthenticator
from src.notifications.sms_service import SMSService

def lambda_handler(event, context):
    """AWS Lambda handler with DI."""
    
    # Load configuration once (cached on first call)
    settings = get_settings()
    
    # Inject settings into services
    db_client = DynamoDBClient(settings)
    authenticator = NaverAuthenticator(settings)
    sms_service = SMSService(settings)
    
    # Process event
    result = process_bookings(db_client, authenticator, sms_service, event)
    
    return result
```

## Module Examples

### 1. Database Module (`src/database/dynamodb_client.py`)

```python
from src.config.settings import Settings
import boto3

class DynamoDBClient:
    """DynamoDB client with injected settings."""
    
    def __init__(self, settings: Settings):
        """
        Initialize DynamoDB client.
        
        Args:
            settings: Settings instance providing:
                - aws_region: AWS region for DynamoDB
                - dynamodb_table_sms: SMS tracking table name
                - dynamodb_table_session: Session cache table name
        """
        self.settings = settings
        self.region = settings.aws_region
        self.sms_table = settings.dynamodb_table_sms
        self.session_table = settings.dynamodb_table_session
        
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.sms_table_resource = self.dynamodb.Table(self.sms_table)
        self.session_table_resource = self.dynamodb.Table(self.session_table)
    
    def get_booking(self, booking_num: str, phone: str):
        """Retrieve booking from DynamoDB."""
        response = self.sms_table_resource.get_item(
            Key={
                'booking_num': booking_num,
                'phone': phone
            }
        )
        return response.get('Item')
    
    def save_booking(self, booking_data: dict):
        """Save booking to DynamoDB."""
        self.sms_table_resource.put_item(Item=booking_data)
```

**Unit Test Example:**

```python
import pytest
from src.config.settings import Settings
from src.database.dynamodb_client import DynamoDBClient

@pytest.fixture
def mock_settings():
    """Fixture providing mock Settings for testing."""
    return Settings(
        aws_region='ap-northeast-2',
        dynamodb_table_sms='test_sms',
        dynamodb_table_session='test_session'
    )

@pytest.fixture
def db_client(mock_settings):
    """Fixture providing DynamoDBClient with mock settings."""
    return DynamoDBClient(mock_settings)

def test_get_booking(db_client, monkeypatch):
    """Test booking retrieval with mocked DynamoDB."""
    # Mock the boto3 DynamoDB resource
    mock_table = MagicMock()
    mock_table.get_item.return_value = {
        'Item': {'booking_num': '123', 'phone': '010-1234-5678'}
    }
    
    monkeypatch.setattr(
        db_client.sms_table_resource, 
        'get_item', 
        mock_table.get_item
    )
    
    result = db_client.get_booking('123', '010-1234-5678')
    assert result['booking_num'] == '123'
```

### 2. Authentication Module (`src/auth/naver_login.py`)

```python
from src.config.settings import Settings
from selenium import webdriver

class NaverAuthenticator:
    """Handles Naver login with injected credentials."""
    
    def __init__(self, settings: Settings):
        """
        Initialize Naver authenticator.
        
        Args:
            settings: Settings instance providing:
                - naver_username: Naver account username
                - naver_password: Naver account password
        """
        self.settings = settings
        self.username = settings.naver_username
        self.password = settings.naver_password
        self.driver = None
    
    def login(self, cached_cookies=None):
        """Login to Naver using credentials."""
        # Implementation uses injected username/password
        if cached_cookies:
            return self._login_with_cookies(cached_cookies)
        else:
            return self._fresh_login()
    
    def _fresh_login(self):
        """Fresh login with stored username/password."""
        # Uses self.username and self.password from settings
        self.driver.find_element("id", "id").send_keys(self.username)
        self.driver.find_element("id", "pw").send_keys(self.password)
        # ... rest of login logic
```

### 3. SMS Service Module (`src/notifications/sms_service.py`)

```python
from src.config.settings import Settings

class SMSService:
    """SMS sending service with injected SENS credentials."""
    
    def __init__(self, settings: Settings):
        """
        Initialize SMS service.
        
        Args:
            settings: Settings instance providing:
                - sens_access_key: SENS API access key
                - sens_secret_key: SENS API secret key
                - sens_service_id: SENS service ID
                - stores: Store configurations with phone numbers
        """
        self.settings = settings
        self.access_key = settings.sens_access_key
        self.secret_key = settings.sens_secret_key
        self.service_id = settings.sens_service_id
        self.stores = settings.stores
    
    def send_sms(self, phone: str, message: str, store_id: str = None):
        """Send SMS via SENS API using injected credentials."""
        from_number = self._get_from_number(store_id)
        
        # Use injected SENS credentials
        signature = self._make_signature(self.secret_key)
        
        headers = {
            'x-ncp-apigw-signature-v2': signature,
            'x-ncp-iam-access-key': self.access_key,
        }
        
        # Send SMS...
    
    def _get_from_number(self, store_id: str = None):
        """Get phone number for store from settings."""
        if store_id and store_id in self.stores:
            return self.stores[store_id].fromNumber
        return self.settings.stores[list(self.stores.keys())[0]].fromNumber
```

## Best Practices

### 1. Always Inject Settings in Constructor

❌ **Bad - Direct import:**

```python
from src.config.settings import get_settings

class MyService:
    def __init__(self):
        self.settings = get_settings()  # Hard to test
```

✅ **Good - Dependency injection:**

```python
from src.config.settings import Settings

class MyService:
    def __init__(self, settings: Settings):
        self.settings = settings  # Easy to test with mock
```

### 2. Extract Only Needed Fields

❌ **Bad - Storing entire Settings:**

```python
class MyService:
    def __init__(self, settings: Settings):
        self.settings = settings  # Exposes everything
        
    def do_something(self):
        # References settings.aws_region many times
        self.settings.aws_region
```

✅ **Good - Extract needed values:**

```python
class MyService:
    def __init__(self, settings: Settings):
        self.region = settings.aws_region  # Clear dependency
        
    def do_something(self):
        # Uses extracted value
        self.region
```

### 3. Use Type Hints for Settings

✅ **Always specify Settings type:**

```python
from src.config.settings import Settings

class MyService:
    def __init__(self, settings: Settings) -> None:
        """Type hint enables IDE autocomplete and mypy checking."""
        self.settings = settings
```

### 4. Create Fixtures for Tests

✅ **Reusable test fixtures:**

```python
import pytest
from src.config.settings import Settings

@pytest.fixture
def test_settings():
    """Standard test settings fixture."""
    return Settings(
        aws_region='ap-northeast-2',
        dynamodb_table_sms='test_sms',
        dynamodb_table_session='test_session',
        naver_username='test_user',
        naver_password='test_pass',
        sens_access_key='test_key',
        sens_secret_key='test_secret',
        sens_service_id='test_svc',
        telegram_bot_token='test_token',
        telegram_chat_id='test_chat',
    )

# Use in tests:
def test_my_service(test_settings):
    service = MyService(test_settings)
    assert service.region == 'ap-northeast-2'
```

## Summary

- **Inject Settings** in constructor, not at module level
- **Extract values** you need, store them as instance variables
- **Type hint** Settings parameter
- **Create test fixtures** for common Settings configurations
- **Use mocks** in unit tests, real settings in integration tests

This approach ensures:
- ✅ Easy to test (no global state)
- ✅ Clear dependencies (visible in constructor)
- ✅ Flexible (easy to swap implementations)
- ✅ Maintainable (changes to one service don't affect others)
