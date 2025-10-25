import json
import time
from random import uniform

from selenium import webdriver
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

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.binary_location = "/opt/chrome/chrome"
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

        service = Service(executable_path="/opt/chromedriver")

        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.get("https://new.smartplace.naver.com/")

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
            for cookie in cached_cookies:
                driver.add_cookie(cookie)

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
