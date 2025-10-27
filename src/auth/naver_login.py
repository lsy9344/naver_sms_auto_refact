import json
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path
from random import uniform
from typing import Any, Dict, List, Optional
from selenium import webdriver
from selenium.common.exceptions import InvalidCookieDomainException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..utils.logger import get_logger

logger = get_logger(__name__)


class NaverAuthenticator:
    """Exact extraction of the legacy Naver login flow."""

    def __init__(self, username: str, password: str, session_manager):
        self.username = username
        self.password = password
        self.session_manager = session_manager
        self.driver = None
        self._cdp_network_enabled = False

    def setup_driver(self):
        chrome_options = Options()
        chrome_binary = self._resolve_chrome_binary_location()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info("Using Chrome binary", context={"path": chrome_binary})
        else:
            logger.warning("Chrome binary not found via known paths; relying on Selenium defaults")

        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-tools")
        chrome_options.add_argument("--no-zygote")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--user-data-dir=/tmp/user-data")
        chrome_options.add_argument("--data-path=/tmp/data-path")
        chrome_options.add_argument("--homedir=/tmp")
        chrome_options.add_argument("--disk-cache-dir=/tmp/cache-dir")
        user_agent = (
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument(user_agent)

        chromedriver_path = self._resolve_chromedriver_path()
        if chromedriver_path:
            logger.info("Using ChromeDriver binary", context={"path": chromedriver_path})
            service = Service(executable_path=chromedriver_path)
        else:
            logger.warning(
                "ChromeDriver binary not found via known paths; falling back to Selenium Manager"
            )
            service = Service()

        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.get("https://new.smartplace.naver.com/")

    def _resolve_chrome_binary_location(self) -> Optional[str]:
        """
        Locate the Chrome binary using environment overrides and common fallback paths.

        Returns:
            Path to Chrome binary if found, otherwise None.
        """
        candidates = [
            os.getenv("CHROME_BINARY_PATH"),
            os.getenv("GOOGLE_CHROME_BIN"),
            os.getenv("GOOGLE_CHROME_SHIM"),
            "/opt/chrome/chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]

        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return candidate

        for binary_name in ("google-chrome", "chrome", "chromium-browser", "chromium"):
            resolved = shutil.which(binary_name)
            if resolved:
                return resolved

        return None

    def _resolve_chromedriver_path(self) -> Optional[str]:
        """
        Locate the ChromeDriver binary via environment hints or PATH.

        Returns:
            Path to ChromeDriver binary if found, otherwise None.
        """
        candidates = [
            os.getenv("CHROMEDRIVER_BIN"),
            os.getenv("CHROMEDRIVER_PATH"),
            "/opt/chromedriver",
            "/usr/local/bin/chromedriver",
            "/usr/bin/chromedriver",
        ]

        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return candidate

        resolved = shutil.which("chromedriver")
        if resolved:
            return resolved

        return None

    def login(self, cached_cookies=None):
        if not self.driver:
            self.setup_driver()

        driver = self.driver
        userid = self.username
        userpw = self.password
        dynamodb_session = self.session_manager
        delay = 0

        logger.info("로그인")
        if not cached_cookies:
            logger.info("Starting fresh Naver login", operation="naver_login")
            logger.debug(
                "No cached cookies, proceeding with Selenium login", operation="naver_login"
            )

            driver.refresh()

            driver.get("https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com/")

            login_btn = driver.find_element(By.ID, "log.login")

            driver.execute_script(
                f"document.querySelector('input[id=\"id\"]').setAttribute('value', '{userid}')"
            )
            time.sleep(uniform(delay + 0.33643, delay + 0.54354))
            driver.execute_script(
                f"document.querySelector('input[id=\"pw\"]').setAttribute('value', '{userpw}')"
            )
            time.sleep(uniform(delay + 0.33643, delay + 0.54354))
            login_btn.click()
            time.sleep(uniform(delay + 0.63643, delay + 0.94354))

            time.sleep(1)

            WebDriverWait(driver, 10).until(EC.url_contains("naver.com"))

            cookies = driver.get_cookies()
            session_cookie = json.dumps(cookies)
            dynamodb_session.put_item(Item={"id": "1", "cookies": session_cookie})

            return cookies
        else:
            self._apply_cached_cookies(cached_cookies)

            driver.get("https://nid.naver.com/user2/help/myInfoV2?lang=ko_KR")
            driver.implicitly_wait(10)

            logger.debug("Validating cached cookie", operation="naver_login_cached")
            time.sleep(3)
            if "login" in driver.current_url:
                msg = "Cookie validation failed, re-authenticating"
                logger.warning(msg, operation="naver_login_cached", error="Cached cookie invalid")
                return self.login(None)
            else:
                logger.info(
                    "Cached cookie validation successful",
                    operation="naver_login_cached",
                )
                return cached_cookies

    def get_session(self):
        import requests

        session = requests.Session()
        if self.driver:
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                session.cookies.set(cookie["name"], cookie["value"])

        return session

    def cleanup(self):
        if self.driver:
            self.driver.quit()

    def _apply_cached_cookies(self, cached_cookies: List[Dict[str, Any]]) -> None:
        """Rehydrate Selenium session by aligning domains before adding cookies."""
        if not self.driver:
            return

        driver = self.driver
        cookies_by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for cookie in cached_cookies:
            domain = cookie.get("domain") or "naver.com"
            cookies_by_domain[domain].append(cookie)

        last_loaded_domain = ""
        for domain, domain_cookies in cookies_by_domain.items():
            sanitized_domain = domain.lstrip(".")
            target_url = f"https://{sanitized_domain}/"

            if last_loaded_domain != sanitized_domain:
                try:
                    driver.get(target_url)
                    last_loaded_domain = sanitized_domain
                except WebDriverException as exc:
                    logger.warning(
                        "Skipping cached cookies for domain due to navigation failure",
                        operation="naver_login_cached",
                        error=str(exc),
                        context={"domain": sanitized_domain},
                    )
                    continue

            for cookie in domain_cookies:
                cookie_payload = cookie.copy()
                expiry = cookie_payload.get("expiry")
                if isinstance(expiry, float):
                    cookie_payload["expiry"] = int(expiry)

                try:
                    driver.add_cookie(cookie_payload)
                except InvalidCookieDomainException as exc:
                    logger.warning(
                        "Cached cookie rejected due to domain mismatch",
                        operation="naver_login_cached",
                        error=str(exc),
                        context={"domain": sanitized_domain},
                    )
                    self._set_cookie_via_devtools(cookie_payload)

    def _ensure_cdp_network(self) -> bool:
        """Enable Chrome DevTools Protocol network domain once per session."""
        if not self.driver or self._cdp_network_enabled:
            return bool(self.driver)

        try:
            self.driver.execute_cdp_cmd("Network.enable", {})
            self._cdp_network_enabled = True
            return True
        except WebDriverException as exc:
            logger.error(
                "Failed to enable CDP network domain",
                operation="naver_login_cdp",
                error=str(exc),
            )
            return False

    def _set_cookie_via_devtools(self, cookie: Dict[str, Any]) -> bool:
        """
        Fallback cookie injection for domains that cannot be navigated to without authentication.
        Uses Chrome DevTools Protocol to bypass Selenium's domain restrictions.
        """
        if not self.driver or not self._ensure_cdp_network():
            return False

        cookie_args: Dict[str, Any] = {
            "name": cookie["name"],
            "value": cookie["value"],
            "path": cookie.get("path", "/"),
            "secure": cookie.get("secure", False),
            "httpOnly": cookie.get("httpOnly", False),
        }

        domain = cookie.get("domain")
        if domain:
            cookie_args["domain"] = domain
        else:
            cookie_args["url"] = "https://naver.com/"

        expiry = cookie.get("expiry")
        if isinstance(expiry, (int, float)):
            cookie_args["expires"] = int(expiry)

        same_site = cookie.get("sameSite")
        if same_site:
            cookie_args["sameSite"] = same_site

        try:
            self.driver.execute_cdp_cmd("Network.setCookie", cookie_args)
            logger.debug(
                "Injected cookie via CDP after Selenium rejection",
                operation="naver_login_cdp",
                context={
                    "domain": domain or "naver.com",
                    "cookie": cookie["name"],
                },
            )
            return True
        except WebDriverException as exc:
            logger.error(
                "Failed to inject cookie via CDP",
                operation="naver_login_cdp",
                error=str(exc),
                context={"cookie": cookie["name"], "domain": domain or "naver.com"},
            )
            return False
