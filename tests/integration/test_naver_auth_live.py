"""
Integration Tests for NaverAuthenticator

Tests the Naver login module with real Naver credentials and DynamoDB.
IMPORTANT: Requires real Naver test account credentials and DynamoDB access.
These tests are skipped by default to avoid exposing credentials.
"""

import os
import json

import boto3
import pytest

moto = pytest.importorskip('moto')
from moto import mock_aws  # type: ignore[attr-defined]

from src.auth.naver_login import NaverAuthenticator
from src.auth.session_manager import SessionManager


class TestNaverAuthenticatorIntegration:
    """Integration tests with mocked DynamoDB"""

    def setup_method(self):
        """Setup mock DynamoDB for each test"""
        self.mock = mock_aws()
        self.mock.start()

        # Create mock DynamoDB resource
        self.dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')

        # Create session table
        self.dynamodb.create_table(
            TableName='session',
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

    def teardown_method(self):
        """Cleanup after each test"""
        self.mock.stop()

    def test_session_manager_save_and_retrieve(self):
        """Test saving and retrieving cookies from DynamoDB"""
        session_mgr = SessionManager(self.dynamodb)

        # Test data
        test_cookies = [
            {'name': 'NID_AUT', 'value': 'auth_token_123', 'domain': '.naver.com'},
            {'name': 'NID_SES', 'value': 'session_token_456', 'domain': '.naver.com'},
        ]

        # Save cookies
        cookies_json = json.dumps(test_cookies)
        success = session_mgr.save_cookies(cookies_json)
        assert success, "Should successfully save cookies"

        # Retrieve cookies
        retrieved = session_mgr.get_cookies()
        assert retrieved == test_cookies, "Retrieved cookies should match saved cookies"

    def test_session_manager_get_nonexistent_cookies(self):
        """Test retrieving cookies when none exist"""
        session_mgr = SessionManager(self.dynamodb)

        # Retrieve when no cookies exist
        result = session_mgr.get_cookies()
        assert result is None, "Should return None when no cookies exist"

    def test_session_manager_overwrite_cookies(self):
        """Test overwriting existing cookies"""
        session_mgr = SessionManager(self.dynamodb)

        # Save first set of cookies
        first_cookies = [{'name': 'NID_AUT', 'value': 'first_token'}]
        session_mgr.save_cookies(json.dumps(first_cookies))

        # Save second set of cookies (should overwrite)
        second_cookies = [{'name': 'NID_AUT', 'value': 'second_token'}]
        session_mgr.save_cookies(json.dumps(second_cookies))

        # Verify second set is stored
        retrieved = session_mgr.get_cookies()
        assert retrieved == second_cookies, "Should overwrite and return latest cookies"


# Real Naver integration tests (run only when explicitly enabled)
RUN_LIVE = os.getenv('RUN_NAVER_LIVE_TESTS') == '1'


@pytest.mark.skipif(not RUN_LIVE, reason="Set RUN_NAVER_LIVE_TESTS=1 with test credentials to run live checks")
class TestNaverAuthenticatorLive:
    """Live integration tests with real Naver (MANUAL ONLY)"""

    @pytest.fixture
    def real_dynamodb(self):
        """Use real DynamoDB (requires AWS credentials)"""
        return boto3.resource('dynamodb', region_name='ap-northeast-2')

    @pytest.fixture
    def naver_credentials(self):
        """
        Naver test credentials.
        IMPORTANT: Use test account, never production credentials!
        """
        username = os.getenv('NAVER_TEST_USERNAME')
        password = os.getenv('NAVER_TEST_PASSWORD')
        if not username or not password:
            pytest.skip("NAVER_TEST_USERNAME and NAVER_TEST_PASSWORD environment variables must be set")
        return {'username': username, 'password': password}

    def test_real_naver_fresh_login(self, real_dynamodb, naver_credentials):
        """
        Test fresh login with real Naver credentials.
        
        MANUAL TEST: Only run locally with test account credentials.
        DO NOT RUN in CI/CD or with production credentials.
        """
        session_mgr = SessionManager(real_dynamodb)

        auth = NaverAuthenticator(
            naver_credentials['username'],
            naver_credentials['password'],
            session_mgr
        )

        try:
            # Perform fresh login
            cookies = auth.login(cached_cookies=None)

            # Verify cookies were obtained
            assert len(cookies) > 0, "Should obtain cookies from Naver"
            assert any(c['name'] == 'NID_AUT' for c in cookies), "Should have NID_AUT authentication cookie"

            # Verify cookies were saved to DynamoDB
            saved_cookies = session_mgr.get_cookies()
            assert saved_cookies == cookies, "Cookies should be saved to DynamoDB"

        finally:
            auth.cleanup()

    def test_real_naver_cookie_reuse(self, real_dynamodb, naver_credentials):
        """
        Test cookie reuse with real cached cookies.
        
        Prerequisite: Must have valid cookies in DynamoDB session table.
        """
        session_mgr = SessionManager(real_dynamodb)

        # Get cached cookies
        cached_cookies = session_mgr.get_cookies()
        if cached_cookies is None:
            pytest.skip("No cached cookies available in DynamoDB")

        auth = NaverAuthenticator(
            naver_credentials['username'],
            naver_credentials['password'],
            session_mgr
        )

        try:
            # Attempt login with cached cookies
            result = auth.login(cached_cookies=cached_cookies)

            # Should either reuse or perform fresh login on expiry
            assert len(result) > 0, "Should obtain valid cookies"

        finally:
            auth.cleanup()

    def test_real_naver_api_calls_with_session(self, real_dynamodb, naver_credentials):
        """
        Test that authenticated session can make API calls.
        
        Verifies that cookies from auth can be used for subsequent API calls.
        """
        session_mgr = SessionManager(real_dynamodb)

        # Get cached cookies or perform fresh login
        cookies = session_mgr.get_cookies()
        if cookies is None:
            # Would need fresh login here
            pytest.skip("Requires valid cached cookies or fresh login capability")

        auth = NaverAuthenticator(
            naver_credentials['username'],
            naver_credentials['password'],
            session_mgr
        )

        try:
            auth.login(cached_cookies=cookies)

            # Get requests.Session with cookies
            session = auth.get_session()

            # Test API call with authenticated session
            # Example: GET profile page
            response = session.get('https://partner.booking.naver.com/dashboard')

            # Verify successful response (not redirected to login)
            assert response.status_code < 400, "API call should succeed with authenticated session"
            assert 'login' not in response.url.lower(), "Should not be redirected to login page"

        finally:
            auth.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
