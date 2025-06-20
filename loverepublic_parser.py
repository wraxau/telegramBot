from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from dataclasses import dataclass
from typing import List
import logging
import time
import tempfile
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class LoveRepublicItem:
    url: str


class LoveRepublicParser:
    BASE_URL = "https://loverepublic.ru/catalog/search/"

    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.binary_location = "/usr/bin/google-chrome"
        self.chrome_options.add_argument('--headless=new')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')
        self.chrome_options.add_argument('--window-size=1920,1080')
        # self.chrome_options.add_argument('--proxy-server=http://4vYje1XyG:BizKnT1Ba@45.140.67.6:62622')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--blink-settings=imagesEnabled=false')
        self.chrome_options.add_argument('--disable-web-security')
        self.chrome_options.add_argument('--allow-running-insecure-content')
        temp_dir = tempfile.mkdtemp()
        self.chrome_options.add_argument(f"--user-data-dir={temp_dir}")

    def init_driver(self):
        """Инициализация драйвера Chrome"""
        try:
            os.environ["HTTP_PROXY"] = ""
            os.environ["HTTPS_PROXY"] = ""
            service = Service(ChromeDriverManager().install())
            # os.environ["HTTP_PROXY"] = "http://4vYje1XyG:BizKnT1Ba@45.140.67.6:62622"
            # os.environ["HTTPS_PROXY"] = "http://4vYje1XyG:BizKnT1Ba@45.140.67.6:62622"
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("[LOVEREPUBLIC] Драйвер успешно инициализирован")
            return driver
        except Exception as e:
            logger.error(f"[LOVEREPUBLIC] Ошибка инициализации драйвера: {e}")
            raise

    def scroll_to_bottom(self, driver):
        """Прокрутка страницы до конца для загрузки всех товаров"""
        last_height = driver.execute_script("return document.body.scrollHeight")
        scrolls = 0
        max_scrolls = 10

        while scrolls < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scrolls += 1
            logger.info(f"[LOVEREPUBLIC] Прокрутка {scrolls}/{max_scrolls}, высота: {new_height}")

    def save_debug_info(self, driver, prefix="debug"):
        """Сохранение отладочной информации"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"debug/{prefix}_screenshot_{timestamp}.png"
        html_path = f"debug/{prefix}_page_{timestamp}.html"

        try:
            os.makedirs("debug", exist_ok=True)
            driver.save_screenshot(screenshot_path)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info(f"[LOVEREPUBLIC] Сохранена отладка: {screenshot_path}, {html_path}")
        except Exception as e:
            logger.error(f"[LOVEREPUBLIC] Ошибка сохранения отладки: {e}")

    def get_product_urls(self, query: str) -> List[LoveRepublicItem]:
        """Получает список URL товаров по поисковому запросу"""
        driver = None
        items = []
        try:
            logger.info(f"[LOVEREPUBLIC] Начало поиска для запроса: {query}")
            driver = self.init_driver()

            url = f"{self.BASE_URL}{query}"
            logger.info(f"[LOVEREPUBLIC] Переход по URL: {url}")
            driver.get(url)

            logger.info("[LOVEREPUBLIC] Ожидание загрузки страницы...")
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(3)

            logger.info("[LOVEREPUBLIC] Прокрутка страницы...")
            self.scroll_to_bottom(driver)

            logger.info("[LOVEREPUBLIC] Поиск ссылок на товары...")
            try:
                product_links = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div.product-card a[href*='/catalog/odezhda/']"))
                )
            except TimeoutException:
                logger.info("[LOVEREPUBLIC] Попытка альтернативного селектора...")
                product_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/catalog/odezhda/']")

            if product_links:
                seen_urls = set()
                for link in product_links:
                    url = link.get_attribute('href')
                    # Фильтровать только ссылки на товары
                    if (url and '/catalog/odezhda/' in url and
                            not url.endswith('/catalog/') and
                            not url.endswith('/catalog/odezhda/') and
                            not 'page=' in url and
                            not url.endswith('/new/') and
                            not url.endswith('/sale/') and
                            url not in seen_urls):
                        seen_urls.add(url)
                        items.append(LoveRepublicItem(url=url))
                logger.info(f"[LOVEREPUBLIC] Найдено уникальных товаров: {len(items)}")

            return items

        except Exception as e:
            logger.error(f"[LOVEREPUBLIC] Ошибка парсинга: {e}")
            if driver:
                self.save_debug_info(driver, f"error_{query}")
            return []
        finally:
            if driver:
                try:
                    driver.quit()
                    logger.info("[LOVEREPUBLIC] Драйвер закрыт")
                except Exception as e:
                    logger.error(f"[LOVEREPUBLIC] Ошибка закрытия драйвера: {e}")


def test_parser():
    """Тестирование парсера"""
    parser = LoveRepublicParser()
    query = "футболка"
    print(f"\nПоиск товаров: {query}")
    print("=" * 80)

    results = parser.get_product_urls(query)

    if results:
        print(f"\nНайдено товаров: {len(results)}")
        print("\nСписок найденных товаров:")
        print("-" * 80)
        for i, item in enumerate(results, 1):
            print(f"{i}. {item.url}")
        print(f"\nВсего найдено: {len(results)}")
    else:
        print("Товары не найдены")

    print("=" * 80)


if __name__ == "__main__":
    test_parser()
