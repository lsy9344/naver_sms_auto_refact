"""
Naver Login Module - Extracted from lambda_function.py:229-301

CRITICAL: This code is preserved EXACTLY from the original lambda_function.py.
Do not modify the login logic as it is sensitive to bot detection and works reliably.
The Selenium automation, timing, and JavaScript injection are production-proven.
"""

import json
import time
import logging
from random import uniform

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class NaverAuthenticator:
    """
    Handles Naver platform authentication using Selenium.

    CRITICAL: This code is preserved exactly from the original
    lambda_function.py (lines 229-301). Do not modify the login
    logic as it is sensitive to bot detection and works reliably.
    """

    def __init__(self, username: str, password: str, session_manager, delay: float = 0):
        """
        Initialize NaverAuthenticator.

        Args:
            username: Naver account ID
            password: Naver account password
            session_manager: Session manager for DynamoDB cookie storage
            delay: Additional delay multiplier (default 0 for production)
        """
        self.username = username
        self.password = password
        self.session_manager = session_manager
        self.delay = delay
        self.driver = None

    def setup_driver(self):
        """
        Setup Chrome WebDriver with Lambda-specific options.
        EXACT COPY: lambda_function.py:229-248

        Chrome options are specifically tuned for AWS Lambda environment:
        - Binary and ChromeDriver paths for Lambda layer
        - Headless mode with specific flags for Lambda execution
        - Temporary directories for cache/data (Lambda ephemeral storage)
        - User-agent to avoid bot detection
        """
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1280x1696')
        chrome_options.add_argument('--user-data-dir=/tmp/user-data')
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--enable-logging')
        chrome_options.add_argument('--log-level=0')
        chrome_options.add_argument('--v=99')
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--data-path=/tmp/data-path')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--homedir=/tmp')
        chrome_options.add_argument('--disk-cache-dir=/tmp/cache-dir')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
        )

        chrome_options.binary_location = "/opt/python/bin/headless-chromium"
        
        service = Service(executable_path='/opt/python/bin/chromedriver')
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.get('https://new.smartplace.naver.com/')
        self.driver.implicitly_wait(10)

        logger.info("Chrome driver initialized with Lambda environment options")

    def login(self, cached_cookies=None):
        """
        Login to Naver using cached cookies or fresh Selenium login.
        EXACT COPY: lambda_function.py:260-301

        This function implements two login paths:
        1. Fresh Login (no cached cookies):
           - Navigate to Naver login page
           - Inject credentials via JavaScript (avoids input detection)
           - Apply random delays to mimic human behavior
           - Wait for successful navigation
           - Extract and save cookies to DynamoDB

        2. Cookie Reuse (cached cookies available):
           - Add cached cookies to driver
           - Navigate to profile page
           - Detect if cookies expired (URL contains 'login')
           - Recursively retry with fresh login if expired

        Args:
            cached_cookies: List of cookie dicts from DynamoDB or None

        Returns:
            List of cookie dicts (fresh or validated cached)

        Raises:
            Exception: If login fails after retries or driver not initialized
        """
        if not self.driver:
            self.setup_driver()

        logger.info("Starting Naver login")

        if not cached_cookies:
            logger.info("No cached cookies, initiating fresh login")
            self.driver.refresh()

            # Navigate to Naver login page
            self.driver.get('https://nid.naver.com/nidlogin.login?mode=form&url=https://www.naver.com/')

            # Find login button element
            login_btn = self.driver.find_element(By.ID, "log.login")

            # Inject username via JavaScript - avoids input field detection
            self.driver.execute_script(f"document.querySelector('input[id=\"id\"]').setAttribute('value', '{self.username}')")
            time.sleep(uniform(self.delay + 0.33643, self.delay + 0.54354))

            # Inject password via JavaScript - avoids input field detection
            self.driver.execute_script(f"document.querySelector('input[id=\"pw\"]').setAttribute('value', '{self.password}')")
            time.sleep(uniform(self.delay + 0.33643, self.delay + 0.54354))

            # Click login button
            login_btn.click()
            time.sleep(uniform(self.delay + 0.63643, self.delay + 0.94354))

            # Wait for successful login redirect
            time.sleep(1)
            WebDriverWait(self.driver, 10).until(
                EC.url_contains('naver.com')
            )

            # Extract cookies and persist to DynamoDB
            cookies = self.driver.get_cookies()
            self.session_manager.save_cookies(json.dumps(cookies))

            logger.info(f"Fresh login successful, saved {len(cookies)} cookies")
            return cookies
        else:
            # Cookie reuse path
            logger.info("Attempting cookie reuse login")

            for cookie in cached_cookies:
                self.driver.add_cookie(cookie)

            self.driver.get('https://nid.naver.com/user2/help/myInfoV2?lang=ko_KR')
            self.driver.implicitly_wait(10)

            logger.info("Validating cached cookies")
            time.sleep(3)

            # Check if cookies expired by examining URL
            if "login" in self.driver.current_url:
                logger.warning("Cached cookies expired, retrying with fresh login")
                # Recursive retry with fresh login
                return self.login(None)
            else:
                logger.info("Cookie validation successful, cookies reused")
                return cached_cookies

    def get_session(self):
        """
        Convert Selenium session to requests.Session for API calls.

        Extracts cookies from WebDriver and creates a requests Session
        with the cookies pre-populated for subsequent API calls.

        Returns:
            requests.Session: Session with driver cookies pre-loaded
        """
        import requests

        session = requests.Session()
        if self.driver:
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                session.cookies.set(cookie['name'], cookie['value'])
            logger.info(f"Created requests.Session with {len(cookies)} cookies")

        return session

    def cleanup(self):
        """
        Cleanup: Close WebDriver and free resources.
        """
        if self.driver:
            self.driver.quit()
            logger.info("Chrome driver closed")
