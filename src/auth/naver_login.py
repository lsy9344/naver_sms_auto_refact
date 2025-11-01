import json
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path
from random import uniform
from typing import Any, Dict, List, Optional
from selenium import webdriver
from selenium.common.exceptions import (
    InvalidCookieDomainException,
    WebDriverException,
    TimeoutException,
)
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
        import os
        # Enable stealth by default in Lambda to avoid bot-detection signals
        is_lambda = os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
        env_flag = os.getenv("NAVER_STEALTH_MODE")
        if env_flag is None:
            self._stealth_enabled = is_lambda
        else:
            self._stealth_enabled = env_flag.lower() == "true"

    def setup_driver(self):
        chrome_options = Options()
        chrome_binary = self._resolve_chrome_binary_location()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
            logger.info("Using Chrome binary", context={"path": chrome_binary})
        else:
            logger.warning("Chrome binary not found via known paths; relying on Selenium defaults")

        # Headless & stability flags
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--user-data-dir=/tmp/user-data")
        chrome_options.add_argument("--data-path=/tmp/data-path")
        chrome_options.add_argument("--homedir=/tmp")
        chrome_options.add_argument("--disk-cache-dir=/tmp/cache-dir")

        # Randomize viewport size slightly to avoid fingerprints
        try:
            import random
            if self._stealth_enabled:
                width = random.choice([1280, 1296, 1304, 1366])
                height = random.choice([920, 1000, 1024, 1050])
            else:
                width, height = 1280, 1024
            chrome_options.add_argument(f"--window-size={width},{height}")
        except Exception:
            chrome_options.add_argument("--window-size=1280,1024")

        # Stealth options to reduce webdriver fingerprints
        if self._stealth_enabled:
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # Unified user-agent to match API requests later
        user_agent = (
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument(user_agent)

        # Reduce renderer wait by not waiting for all resources
        try:
            chrome_options.page_load_strategy = "eager"
        except Exception:
            # Fallback for older Selenium
            chrome_options.set_capability("pageLoadStrategy", "eager")

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
        try:
            self.driver.set_page_load_timeout(45)
            self.driver.set_script_timeout(30)
        except Exception:
            pass

        # Apply stealth JS hooks to hide webdriver if enabled
        if self._stealth_enabled:
            try:
                self.driver.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": (
                            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                            "Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR','ko','en-US','en']});"
                            "Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});"
                        )
                    },
                )
            except Exception:
                pass

        # Initial warm-up navigation (best-effort)
        self._safe_get("https://new.smartplace.naver.com/", timeout=30)

    def _safe_get(self, url: str, timeout: int = 45) -> bool:
        """
        Navigate with a bounded timeout and gracefully stop page load on stall.

        Returns True if navigation completed; False if timed out but recovered.
        """
        if not self.driver:
            return False

        try:
            try:
                self.driver.set_page_load_timeout(timeout)
            except Exception:
                pass
            self.driver.get(url)
            return True
        except TimeoutException as exc:
            logger.warning(
                "Navigation timed out; stopping page load",
                operation="naver_navigation_timeout",
                error=str(exc),
                context={"url": url, "timeout": timeout},
            )
            try:
                self.driver.execute_script("window.stop();")
            except Exception:
                pass
            return False
        except WebDriverException as exc:
            msg = str(exc)
            # Soft failures we can recover from by stopping the load
            if "Timed out receiving message from renderer" in msg:
                logger.warning(
                    "Renderer stalled; stopping page load",
                    operation="naver_renderer_stall",
                    error=msg,
                    context={"url": url, "timeout": timeout},
                )
                try:
                    self.driver.execute_script("window.stop();")
                except Exception:
                    pass
                return False
            # Hard crash: attempt one browser restart and retry once
            if "tab crashed" in msg.lower():
                logger.warning(
                    "Chrome tab crashed; restarting driver and retrying navigation",
                    operation="naver_tab_crash_recover",
                    context={"url": url},
                    error=msg,
                )
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                try:
                    self.setup_driver()
                    try:
                        self.driver.set_page_load_timeout(timeout)
                    except Exception:
                        pass
                    self.driver.get(url)
                    return True
                except Exception as retry_exc:
                    logger.error(
                        "Failed to recover from tab crash",
                        operation="naver_tab_crash_recover",
                        error=str(retry_exc),
                    )
                    raise
            raise

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

            # Refresh can stall; recover if needed
            try:
                driver.refresh()
            except TimeoutException as exc:
                logger.warning(
                    "Refresh timed out; proceeding",
                    operation="naver_login_refresh",
                    error=str(exc),
                )
                try:
                    driver.execute_script("window.stop();")
                except Exception:
                    pass

            self._safe_get(
                "https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com/",
                timeout=40,
            )

            # Input credentials (stealth: human-like typing)
            try:
                id_input = driver.find_element(By.ID, "id")
                pw_input = driver.find_element(By.ID, "pw")

                if self._stealth_enabled:
                    for ch in str(userid):
                        id_input.send_keys(ch)
                        time.sleep(uniform(0.05, 0.12))
                    time.sleep(uniform(0.15, 0.35))
                    for ch in str(userpw):
                        pw_input.send_keys(ch)
                        time.sleep(uniform(0.05, 0.12))
                    time.sleep(uniform(0.15, 0.35))
                else:
                    # Fallback to legacy JS injection (preserves unit tests behaviour)
                    driver.execute_script(
                        "document.querySelector('input[id=\\\"id\\\"]').setAttribute('value', '{}')".format(userid)
                    )
                    time.sleep(uniform(delay + 0.33643, delay + 0.54354))
                    driver.execute_script(
                        "document.querySelector('input[id=\\\"pw\\\"]').setAttribute('value', '{}')".format(userpw)
                    )
                    time.sleep(uniform(delay + 0.33643, delay + 0.54354))

                login_btn = driver.find_element(By.ID, "log.login")
                login_btn.click()
            except Exception:
                # As a last resort, use legacy JS path
                login_btn = driver.find_element(By.ID, "log.login")
                driver.execute_script(
                    "document.querySelector('input[id=\\\"id\\\"]').setAttribute('value', '{}')".format(userid)
                )
                time.sleep(uniform(delay + 0.33643, delay + 0.54354))
                driver.execute_script(
                    "document.querySelector('input[id=\\\"pw\\\"]').setAttribute('value', '{}')".format(userpw)
                )
                time.sleep(uniform(delay + 0.33643, delay + 0.54354))
                login_btn.click()
            time.sleep(uniform(delay + 0.63643, delay + 0.94354))

            time.sleep(1)

            WebDriverWait(driver, 15).until(EC.url_contains("naver.com"))

            # Warm partner domain to establish service cookies if required by API
            try:
                self._safe_get("https://partner.booking.naver.com/", timeout=40)
                time.sleep(1)
            except Exception:
                # Non-fatal; proceed with whatever cookies we have
                pass

            cookies = driver.get_cookies()
            session_cookie = json.dumps(cookies)
            dynamodb_session.put_item(Item={"id": "1", "cookies": session_cookie})

            return cookies
        else:
            self._apply_cached_cookies(cached_cookies)

            # In Lambda/stealth mode, validate against partner domain instead of account page
            validate_url = (
                "https://partner.booking.naver.com/"
                if self._stealth_enabled
                else "https://nid.naver.com/user2/help/myInfoV2?lang=ko_KR"
            )
            self._safe_get(validate_url, timeout=30)
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
        """
        Build a requests.Session seeded with Selenium cookies.

        Critical fix: preserve cookie domain/path so requests sends them to
        partner.booking.naver.com. Also align the default User-Agent with the
        browser UA used during Selenium login to reduce server-side suspicion.
        """
        import requests

        session = requests.Session()

        # Align session UA with the Chrome UA used in setup_driver
        try:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            session.headers.update({"User-Agent": ua})
        except Exception:
            pass

        if self.driver:
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                name = cookie.get("name")
                value = cookie.get("value")
                domain = cookie.get("domain") or None
                path = cookie.get("path") or "/"

                # Ensure integer expiry when present (requests ignores it for sending)
                expires = cookie.get("expiry")
                if isinstance(expires, float):
                    expires = int(expires)

                try:
                    # Preserve domain/path so cookies are sent to the correct host
                    session.cookies.set(
                        name,
                        value,
                        domain=domain,
                        path=path,
                    )
                except Exception:
                    # Fallback to name/value only if anything goes wrong
                    session.cookies.set(name, value)

            # Note: Avoid duplicating cookies with the same name across domains,
            # as requests' cookie jar will raise CookieConflictError on get().

        return session

    def ensure_partner_session_for_store(self, store_id: str, timeout: int = 45) -> None:
        """
        Navigate to a partner booking view to ensure service cookies are set.

        This helps establish cookies scoped specifically to
        https://partner.booking.naver.com for the target store.
        """
        if not self.driver:
            self.setup_driver()

        url = f"https://partner.booking.naver.com/bizes/{store_id}/booking-list-view"
        logger.info(
            "Ensuring partner session for store",
            operation="naver_partner_session",
            context={"store_id": store_id, "url": url},
        )
        self._safe_get(url, timeout=timeout)
        # Give the site a brief moment to drop service cookies
        try:
            time.sleep(1)
        except Exception:
            pass

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
                    self._safe_get(target_url, timeout=20)
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
