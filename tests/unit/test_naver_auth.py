import json
from unittest.mock import Mock, MagicMock, call, patch

from src.auth.naver_login import NaverAuthenticator


def _build_driver_mock():
    driver = MagicMock()
    driver.find_element.return_value = MagicMock()
    driver.current_url = "https://new.smartplace.naver.com/profile"
    return driver


@patch("src.auth.naver_login.Service")
@patch("src.auth.naver_login.webdriver.Chrome")
def test_fresh_login_preserves_original_flow(mock_chrome, mock_service):
    driver = _build_driver_mock()
    driver.get_cookies.return_value = [
        {"name": "NID_AUT", "value": "auth_token", "domain": ".naver.com"}
    ]
    mock_chrome.return_value = driver
    mock_service.return_value = MagicMock()

    session_mgr = Mock()
    auth = NaverAuthenticator("testuser", "testpass", session_mgr)

    with patch("src.auth.naver_login.time.sleep"):
        cookies = auth.login(cached_cookies=None)

    assert cookies == driver.get_cookies.return_value

    driver.get.assert_has_calls(
        [
            call("https://new.smartplace.naver.com/"),
            call("https://nid.naver.com/nidlogin.login"),
            call("https://new.smartplace.naver.com/"),
        ]
    )

    calls_text = " ".join(str(args) for args, _ in driver.execute_script.call_args_list)
    assert "document.getElementsByName('id')[0].value='testuser'" in calls_text
    assert "document.getElementsByName('pw')[0].value='testpass'" in calls_text

    session_mgr.put_item.assert_called_once()
    payload = session_mgr.put_item.call_args.kwargs["Item"]
    assert payload["id"] == "1"
    assert json.loads(payload["cookies"]) == driver.get_cookies.return_value

    driver.find_element.return_value.click.assert_called_once()


@patch("src.auth.naver_login.Service")
@patch("src.auth.naver_login.webdriver.Chrome")
def test_cookie_reuse_returns_cached(mock_chrome, mock_service):
    driver = _build_driver_mock()
    mock_chrome.return_value = driver
    mock_service.return_value = MagicMock()

    cached_cookies = [{"name": "NID_SES", "value": "cached"}]
    session_mgr = Mock()
    auth = NaverAuthenticator("testuser", "testpass", session_mgr)

    with patch("src.auth.naver_login.time.sleep"):
        result = auth.login(cached_cookies=cached_cookies)

    assert result == cached_cookies
    assert driver.add_cookie.call_count == len(cached_cookies)
    driver.get.assert_has_calls(
        [
            call("https://new.smartplace.naver.com/"),
            call("https://new.smartplace.naver.com/profile"),
        ]
    )
    session_mgr.put_item.assert_not_called()


@patch("src.auth.naver_login.Service")
@patch("src.auth.naver_login.webdriver.Chrome")
def test_cookie_expiry_triggers_recursive_fresh_login(mock_chrome, mock_service):
    driver = _build_driver_mock()
    driver.current_url = "https://nid.naver.com/nidlogin.login"
    driver.get_cookies.return_value = [{"name": "NID_AUT", "value": "fresh"}]
    mock_chrome.return_value = driver
    mock_service.return_value = MagicMock()

    session_mgr = Mock()
    auth = NaverAuthenticator("testuser", "testpass", session_mgr)

    with patch("src.auth.naver_login.time.sleep"):
        cookies = auth.login(cached_cookies=[{"name": "NID_AUT", "value": "expired"}])

    assert cookies == driver.get_cookies.return_value
    assert session_mgr.put_item.called
    calls_text = " ".join(str(args) for args, _ in driver.execute_script.call_args_list)
    assert "document.getElementsByName('id')[0].value='testuser'" in calls_text


@patch("src.auth.naver_login.Service")
@patch("src.auth.naver_login.webdriver.Chrome")
def test_get_session_mirrors_driver_cookies(mock_chrome, mock_service):
    driver = _build_driver_mock()
    driver.get_cookies.return_value = [
        {"name": "NID_AUT", "value": "auth"},
        {"name": "NID_SES", "value": "session"},
    ]
    mock_chrome.return_value = driver
    mock_service.return_value = MagicMock()

    session_mgr = Mock()
    auth = NaverAuthenticator("testuser", "testpass", session_mgr)
    auth.driver = driver

    session = auth.get_session()
    assert session.cookies.get("NID_AUT") == "auth"
    assert session.cookies.get("NID_SES") == "session"


def test_get_session_without_driver_returns_empty_session():
    session_mgr = Mock()
    auth = NaverAuthenticator("testuser", "testpass", session_mgr)
    session = auth.get_session()
    assert session.cookies.get_dict() == {}
