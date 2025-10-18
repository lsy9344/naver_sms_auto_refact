"""
Unit Tests for NaverAuthenticator

Tests the Naver login module with mocked Selenium WebDriver.
Covers fresh login, cookie reuse, and cookie expiry retry scenarios.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

import sys
sys.path.insert(0, '/Users/sooyeol/Desktop/Code/naver_sms_automation_refactoring')

from src.auth.naver_login import NaverAuthenticator
from src.auth.session_manager import SessionManager


class TestNaverAuthenticatorFreshLogin:
    """Test fresh login path (no cached cookies)"""

    @patch('src.auth.naver_login.WebDriverWait')
    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_fresh_login_success(self, mock_service, mock_driver_class, mock_wait):
        """Test successful fresh login with credential injection and cookie extraction"""
        # Setup mock driver
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance
        mock_wait.return_value.until.return_value = True

        # Mock cookies returned by driver
        mock_cookies = [
            {'name': 'NID_AUT', 'value': 'auth_token_123', 'domain': '.naver.com'},
            {'name': 'NID_SES', 'value': 'session_token_456', 'domain': '.naver.com'},
        ]
        mock_driver_instance.get_cookies.return_value = mock_cookies
        mock_driver_instance.current_url = 'https://new.smartplace.naver.com/'

        # Mock session manager
        session_mgr = Mock(spec=SessionManager)
        session_mgr.save_cookies.return_value = True

        # Create authenticator
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        # Execute fresh login (no cached cookies)
        result = auth.login(cached_cookies=None)

        # Verify login flow
        assert result == mock_cookies, "Should return extracted cookies"
        assert mock_driver_instance.refresh.called, "Should refresh driver"
        assert mock_driver_instance.get.call_count >= 2, "Should navigate to login and other pages"

        # Verify JavaScript credential injection (lines 274-276 from original)
        execute_script_calls = mock_driver_instance.execute_script.call_args_list
        assert len(execute_script_calls) >= 2, "Should inject both username and password"

        # Check username injection
        username_inject_found = any(
            'document.querySelector' in str(call) and 'testuser' in str(call)
            for call in execute_script_calls
        )
        assert username_inject_found, "Username should be injected via JavaScript"

        # Check password injection
        password_inject_found = any(
            'document.querySelector' in str(call) and 'testpass' in str(call)
            for call in execute_script_calls
        )
        assert password_inject_found, "Password should be injected via JavaScript"

        # Verify cookies saved to DynamoDB
        session_mgr.save_cookies.assert_called_once()
        saved_cookies = session_mgr.save_cookies.call_args[0][0]
        assert json.loads(saved_cookies) == mock_cookies, "Cookies should be saved to DynamoDB"

    @patch('src.auth.naver_login.WebDriverWait')
    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_fresh_login_timing_preservation(self, mock_service, mock_driver_class, mock_wait):
        """Test that random delays are applied (lines 275-279 from original)"""
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance
        mock_driver_instance.get_cookies.return_value = [{'name': 'NID_AUT', 'value': 'test'}]
        mock_wait.return_value.until.return_value = True

        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr, delay=0)

        with patch('src.auth.naver_login.time.sleep') as mock_sleep:
            auth.login(cached_cookies=None)

            # Verify time.sleep was called with uniform(a, b) ranges
            # The original code uses uniform(delay + a, delay + b) for delays
            sleep_calls = mock_sleep.call_args_list
            assert len(sleep_calls) > 0, "Should have time delays applied"

    @patch('src.auth.naver_login.WebDriverWait')
    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_fresh_login_button_click(self, mock_service, mock_driver_class, mock_wait):
        """Test that login button is clicked (line 283 from original)"""
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance
        mock_wait.return_value.until.return_value = True

        mock_button = MagicMock()
        mock_driver_instance.find_element.return_value = mock_button
        mock_driver_instance.get_cookies.return_value = [{'name': 'NID_AUT', 'value': 'test'}]

        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        auth.login(cached_cookies=None)

        # Verify login button was clicked
        mock_button.click.assert_called_once()


class TestNaverAuthenticatorCookieReuse:
    """Test cookie reuse path"""

    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_cookie_reuse_success(self, mock_service, mock_driver_class):
        """Test successful cookie reuse with valid cached cookies"""
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance

        # Simulate valid session (not on login page)
        mock_driver_instance.current_url = 'https://nid.naver.com/user2/help/myInfoV2?lang=ko_KR'

        cached_cookies = [
            {'name': 'NID_AUT', 'value': 'cached_auth'},
            {'name': 'NID_SES', 'value': 'cached_session'},
        ]

        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        result = auth.login(cached_cookies=cached_cookies)

        # Verify cookies were reused and not replaced
        assert result == cached_cookies, "Should return cached cookies without modification"

        # Verify add_cookie was called for each cookie
        assert mock_driver_instance.add_cookie.call_count == len(cached_cookies), \
            f"Should add all {len(cached_cookies)} cookies to driver"

        # Verify no fresh login was triggered (no execute_script calls for credential injection)
        execute_script_calls = [
            call for call in mock_driver_instance.execute_script.call_args_list
            if 'testuser' in str(call) or 'testpass' in str(call)
        ]
        assert len(execute_script_calls) == 0, "Should not inject credentials when reusing cookies"

    @patch('src.auth.naver_login.WebDriverWait')
    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_cookie_expiry_detection_and_retry(self, mock_service, mock_driver_class, mock_wait):
        """Test detection of expired cookies and retry with fresh login (lines 298-300 from original)"""
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance
        mock_wait.return_value.until.return_value = True

        # First call: cookies expired (URL contains 'login')
        # Second call (recursive): fresh login succeeds
        mock_driver_instance.current_url = 'https://nid.naver.com/nidlogin.login'  # Indicates expired
        mock_driver_instance.get_cookies.return_value = [{'name': 'NID_AUT', 'value': 'fresh_auth'}]

        cached_cookies = [{'name': 'NID_AUT', 'value': 'expired_auth'}]

        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        result = auth.login(cached_cookies=cached_cookies)

        # Should detect expiry and retry with fresh login
        # Fresh login cookies should be returned
        assert result[0]['value'] == 'fresh_auth', "Should return fresh cookies after detecting expiry"

        # Verify credentials were injected (fresh login path)
        execute_script_calls = mock_driver_instance.execute_script.call_args_list
        assert len(execute_script_calls) > 0, "Should inject credentials on fresh login retry"

    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_cookie_validation_url_check(self, mock_service, mock_driver_class):
        """Test cookie validation via URL check (line 298 from original)"""
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance

        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        # Test with valid URL (not a login page)
        mock_driver_instance.current_url = 'https://partner.booking.naver.com/profile'
        cached_cookies = [{'name': 'NID_AUT', 'value': 'cached'}]

        result = auth.login(cached_cookies=cached_cookies)

        assert result == cached_cookies, "Should accept cookies when URL is not login page"
        assert mock_driver_instance.execute_script.call_count == 0, "Should not do fresh login"


class TestNaverAuthenticatorSessionConversion:
    """Test conversion of Selenium session to requests.Session"""

    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_get_session_conversion(self, mock_service, mock_driver_class):
        """Test conversion of Selenium cookies to requests.Session"""
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance

        mock_cookies = [
            {'name': 'NID_AUT', 'value': 'auth_123'},
            {'name': 'NID_SES', 'value': 'session_456'},
        ]
        mock_driver_instance.get_cookies.return_value = mock_cookies

        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        # Setup driver without calling login (to avoid WebDriverWait issues)
        auth.driver = mock_driver_instance

        # Get requests session
        session = auth.get_session()

        # Verify cookies were transferred to requests.Session
        assert session is not None, "Should return a requests.Session"
        # Verify all cookies are present
        for cookie in mock_cookies:
            assert session.cookies.get(cookie['name']) == cookie['value'], \
                f"Cookie {cookie['name']} should be in session"

    def test_get_session_no_driver(self):
        """Test get_session when driver is not initialized"""
        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        # Should not raise error even without driver
        session = auth.get_session()
        assert session is not None, "Should return empty session when driver not initialized"


class TestNaverAuthenticatorCleanup:
    """Test cleanup operations"""

    @patch('src.auth.naver_login.webdriver.Chrome')
    @patch('src.auth.naver_login.Service')
    def test_cleanup_closes_driver(self, mock_service, mock_driver_class):
        """Test that cleanup closes WebDriver"""
        mock_driver_instance = MagicMock()
        mock_driver_class.return_value = mock_driver_instance

        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        # Initialize driver
        auth.setup_driver()

        # Cleanup
        auth.cleanup()

        # Verify driver was quit
        mock_driver_instance.quit.assert_called_once()

    def test_cleanup_without_driver(self):
        """Test cleanup when driver is None"""
        session_mgr = Mock(spec=SessionManager)
        auth = NaverAuthenticator('testuser', 'testpass', session_mgr)

        # Should not raise error even without driver
        auth.cleanup()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
