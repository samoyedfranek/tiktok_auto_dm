import os
import sys
import json
import time
import random
import string
import logging
import urllib.request
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# Zapasowa lista cytatów (na wypadek braku połączenia z API)
FALLBACK_QUOTES = [
    "Nie czafsdfie będzie 'asdfsdy'.",
    "Sukces to suasdr3432eh dzień w dzień.",
    "Twój sdfjedyny limitsadfsadf sam.",
    "Każ342345s."
]

CONFIG = {
    "headless": True,
    # Przedział czasowy (w sekundach) pauzy między wiadomościami
    "min_delay_between_messages": 45,
    "max_delay_between_messages": 120,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("tiktok_dm.log", encoding="utf-8"),
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        )
    ]
)
log = logging.getLogger(__name__)


class TikTokDMSender:

    def __init__(self):
        # Pobieranie celów bezpośrednio ze zmiennej środowiskowej TARGET_USERNAMES
        env_targets = os.getenv("TARGET_USERNAMES")
        if env_targets:
            try:
                self.target_usernames = json.loads(env_targets)
            except Exception:
                self.target_usernames = [u.strip() for u in env_targets.split(",") if u.strip()]
        else:
            self.target_usernames = []

    def _init_driver(self):
        log.info("Starting Chrome browser in GitHub Actions environment...")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--window-size=1280,900")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(options=options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return driver

    def _fetch_quote_from_net(self) -> str:
        """Pobiera losowy cytat z sieci. W przypadku błędu zwraca cytat z listy zapasowej."""
        try:
            url = "https://dummyjson.com/quotes/random"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    quote = data.get("quote")
                    author = data.get("author")
                    if quote and author:
                        return f'"{quote}" — {author}'
        except Exception as e:
            log.warning(f"Could not fetch quote from internet: {e}. Using fallback.")
        
        return random.choice(FALLBACK_QUOTES)

    def _generate_dynamic_message(self) -> str:
        """Generuje wiadomość z żywym cytatem z API i unikalnym suffixem."""
        quote = self._fetch_quote_from_net()
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"Siema! Cytat na dziś: {quote} #{random_suffix}"

    def _load_cookies_from_env(self, driver) -> bool:
        """Wstrzykuje ciasteczka bezpośrednio ze zmiennej środowiskowej COOKIES_JSON."""
        env_cookies = os.getenv("COOKIES_JSON")
        if not env_cookies:
            log.error("COOKIES_JSON environment variable is missing!")
            return False

        log.info("Opening TikTok to inject cookies...")
        driver.get("https://www.tiktok.com")
        time.sleep(random.uniform(3.0, 5.0))

        try:
            cookies = json.loads(env_cookies)
            injected = 0
            for cookie in cookies:
                for key in ["sameSite", "storeId", "id", "hostOnly", "session", "firstPartyDomain"]:
                    cookie.pop(key, None)
                if "tiktok.com" not in cookie.get("domain", ""):
                    continue
                try:
                    driver.add_cookie(cookie)
                    injected += 1
                except Exception:
                    pass

            log.info(f"Injected {injected} cookies — refreshing...")
            driver.refresh()
            time.sleep(random.uniform(4.0, 7.0))

            if "login" in driver.current_url.lower():
                log.error("Cookies expired or invalid — login failed.")
                return False

            log.info("Login via cookies successful!")
            return True

        except Exception as e:
            log.error(f"Failed to load cookies from environment: {e}")
            return False

    def _send_dm(self, driver, username, message):
        wait = WebDriverWait(driver, 20)
        log.info(f"Opening profile @{username}...")

        try:
            driver.get(f"https://www.tiktok.com/@{username}")
            time.sleep(random.uniform(3.0, 6.0))

            message_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[data-e2e="message-button"]')
                )
            )
            message_btn.click()
            log.info(f"Message button clicked for @{username}...")
            time.sleep(random.uniform(3.0, 5.0))

            msg_box = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'div.public-DraftEditor-content')
                )
            )
            msg_box.click()
            time.sleep(random.uniform(0.8, 1.5))

            # Symulowanie naturalnego pisania na klawiaturze z losowym opóźnieniem
            actions = ActionChains(driver)
            actions.move_to_element(msg_box).click().pause(0.3)
            for char in message:
                actions.send_keys(char)
                actions.pause(random.uniform(0.04, 0.15))
            actions.perform()
            time.sleep(random.uniform(1.0, 2.0))

            ActionChains(driver).move_to_element(msg_box).click().send_keys(Keys.RETURN).perform()
            time.sleep(random.uniform(2.0, 4.0))

            log.info(f"Message sent successfully to @{username}: '{message}'")
            return True

        except Exception as e:
            log.error(f"Failed to send message to @{username}: {e}")
            driver.save_screenshot(f"error_{username}.png")
            return False

    def run(self):
        log.info("=" * 50)
        log.info(f"Starting session - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log.info("=" * 50)

        if not self.target_usernames:
            log.error("No target usernames found in TARGET_USERNAMES secret!")
            return

        driver = self._init_driver()
        try:
            if not self._load_cookies_from_env(driver):
                log.error("Cookie login failed.")
                return

            log.info(f"Loaded targets ({len(self.target_usernames)}): {self.target_usernames}")

            success = 0
            failed  = 0

            for username in self.target_usernames:
                dynamic_message = self._generate_dynamic_message()
                result = self._send_dm(driver, username, dynamic_message)
                
                if result:
                    success += 1
                else:
                    failed += 1

                # Losowy czas oczekiwania przed kolejną wiadomością
                sleep_time = random.uniform(
                    CONFIG["min_delay_between_messages"], 
                    CONFIG["max_delay_between_messages"]
                )
                log.info(f"Waiting {sleep_time:.1f} seconds before next action...")
                time.sleep(sleep_time)

            log.info(f"Session completed — Successful: {success} | Failed: {failed}")

        finally:
            driver.quit()
            log.info("Browser closed.")


if __name__ == "__main__":
    sender = TikTokDMSender()
    sender.run()
