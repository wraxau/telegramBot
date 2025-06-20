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
import json
import requests  # Добавлен импорт requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class BefreeItem:
    url: str

class BefreeShopParser:
    BASE_URL = "https://befree.ru/search?query="

    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless=new')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36')
        temp_dir = tempfile.mkdtemp()
        self.chrome_options.add_argument(f"--user-data-dir={temp_dir}")

    def init_driver(self):
        """Инициализация драйвера Chrome"""
        try:
            os.environ["HTTP_PROXY"] = ""
            os.environ["HTTPS_PROXY"] = ""
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("[BEFREE] Драйвер успешно инициализирован")
            return driver
        except Exception as e:
            logger.error(f"[BEFREE] Ошибка инициализации драйвера: {e}")
            raise

    def scroll_to_bottom(self, driver):
        """Прокрутка страницы до конца"""
        last_height = driver.execute_script("return document.body.scrollHeight")
        scrolls = 0
        max_scrolls = 15
        while scrolls < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scrolls += 1
            logger.info(f"[BEFREE] Прокрутка {scrolls}/{max_scrolls}, высота: {new_height}")

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
            logger.info(f"[BEFREE] Сохранена отладка: {screenshot_path}, {html_path}")
        except Exception as e:
            logger.error(f"[BEFREE] Ошибка сохранения отладки: {e}")

    def get_product_urls(self, query: str) -> List[BefreeItem]:
        """Получает список URL товаров по поисковому запросу"""
        driver = None
        items = []
        try:
            logger.info(f"[BEFREE] Начало поиска для запроса: {query}")
            driver = self.init_driver()

            # Перехват API-запросов
            logger.info("[BEFREE] Включение перехвата сетевых запросов")
            driver.execute_cdp_cmd("Network.enable", {})
            requests_list = []
            def log_request(intercepted_request):
                requests_list.append(intercepted_request)
            driver.execute_cdp_cmd("Network.requestWillBeSent", log_request)

            url = f"https://befree.ru/search?query={query}"
            try:
                driver.get(url)
                time.sleep(10)  # Ожидание загрузки API-запросов
                api_requests = [r for r in requests_list if "api" in r.get("request", {}).get("url", "").lower()]
                logger.info(f"[BEFREE] Найдено API-запросов: {api_requests}")
            except Exception as e:
                logger.error(f"[BEFREE] Ошибка загрузки страницы: {e}")
                return []

            if "502 Bad Gateway" in driver.page_source:
                logger.error(f"[BEFREE] Получена ошибка 502 Bad Gateway")
                self.save_debug_info(driver, f"502_error_{query}")
                return []

            # Прямой запрос API
            logger.info("[BEFREE] Проверка API-эндпоинта")
            try:
                api_url = f"https://befree.ru/api/search?query={query}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
                }
                response = requests.get(api_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    api_data = response.json()
                    logger.info(f"[BEFREE] API данные: {str(api_data)[:500]}...")
                    # Извлечение ссылок из API (пример)
                    if isinstance(api_data, dict) and 'products' in api_data:
                        for product in api_data.get('products', []):
                            url = product.get('url') or product.get('href')
                            if url and ('/platia/' in url or '/product/' in url):
                                if url.startswith('/'):
                                    url = f"https://befree.ru{url}"
                                items.append(BefreeItem(url=url))
                    logger.info(f"[BEFREE] Найдено ссылок в API: {[item.url for item in items]}")
                else:
                    logger.warning(f"[BEFREE] API вернул код: {response.status_code}")
            except Exception as e:
                logger.warning(f"[BEFREE] Ошибка API-запроса: {e}")

            logger.info("[BEFREE] Ожидание страницы...")
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                logger.info("[BEFREE] Тело страницы загружено")
                page_source = driver.page_source
                logger.info(f"[BEFREE] Первые 1000 символов HTML: {page_source[:1000]}...")
            except TimeoutException:
                logger.error("[BEFREE] Тело страницы не загрузилось")
                self.save_debug_info(driver, f"timeout_body_{query}")
                return []

            # Проверка на CAPTCHA
            block_indicators = [
                "iframe[src*='captcha'], div[id*='captcha'], div[class*='captcha']",
                "script[src*='perimeterx'], div[class*='px-captcha'], div[id*='px-captcha']"
            ]
            block_found = False
            for indicator in block_indicators:
                elements = driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    block_found = True
                    logger.warning(f"[BEFREE] Обнаружен блок: {indicator}")
                    self.save_debug_info(driver, f"block_{query}")
                    return []

            # Ожидание товаров
            logger.info("[BEFREE] Ожидание товаров...")
            try:
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "div.digi-products-grid, div.digi-product, a.digi-product__link"
                    ))
                )
                logger.info("[BEFREE] Товары загружены")
            except TimeoutException:
                logger.warning("[BEFREE] Товары не загружены")
                self.save_debug_info(driver, f"no_products_{query}")

            time.sleep(30)  # Увеличено ожидание JavaScript

            # Имитация поведения
            logger.info("[BEFREE] Имитация движения мыши")
            try:
                driver.execute_script("window.scrollBy(0, 3000);")
                time.sleep(5)
                driver.execute_script("window.scrollBy(0, -1000);")
                time.sleep(3)
                driver.execute_script("document.body.click();")
            except Exception as e:
                logger.warning(f"[BEFREE] Ошибка при имитации: {e}")

            logger.info("[BEFREE] Прокрутка страницы")
            self.scroll_to_bottom(driver)
            time.sleep(5)
            logger.info("[BEFREE] Дополнительная прокрутка")
            self.scroll_to_bottom(driver)

            # Извлечение JSON
            logger.info("[BEFREE] Поиск JSON-данных...")
            try:
                scripts = driver.find_elements(By.TAG_NAME, "script")
                for script in scripts:
                    content = script.get_attribute("innerHTML")
                    if content and "self.__next_f.push" in content:
                        try:
                            parts = content.split("self.__next_f.push([1,")
                            for part in parts[1:]:
                                try:
                                    json_str = part.split("])")[0].strip('"')
                                    json_str = json_str.encode().decode('unicode_escape')
                                    json_data = json.loads(json_str)
                                    logger.info(f"[BEFREE] Найден JSON: {str(json_data)[:500]}...")

                                    def find_urls(data, urls=None):
                                        if urls is None:
                                            urls = []
                                        if isinstance(data, dict):
                                            for key, value in data.items():
                                                if key in ['url', 'href'] and isinstance(value, str) and (
                                                        '/platia/' in value or '/product/' in value):
                                                    urls.append(value)
                                                elif isinstance(value, (dict, list)):
                                                    find_urls(value, urls)
                                        elif isinstance(data, list):
                                            for item in data:
                                                find_urls(item, urls)
                                        return urls

                                    product_urls = find_urls(json_data)
                                    for url in product_urls:
                                        if url.startswith('/'):
                                            url = f"https://befree.ru{url}"
                                        items.append(BefreeItem(url=url))
                                    logger.info(f"[BEFREE] Найдено ссылок в JSON: {product_urls}")
                                except Exception as e:
                                    logger.warning(f"[BEFREE] Ошибка парсинга части JSON: {e}")
                        except Exception as e:
                            logger.warning(f"[BEFREE] Ошибка обработки скрипта: {e}")
            except Exception as e:
                logger.warning(f"[BEFREE] Ошибка извлечения JSON: {e}")

            # Сбор ссылок из HTML
            logger.info("[BEFREE] Сбор ссылок на товары")
            container_selectors = [
                "div.digi-products-grid",
                "div.digi-products",
                "section.search-page"
            ]
            container = None
            for selector in container_selectors:
                try:
                    container = driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"[BEFREE] Найден контейнер: {selector}")
                    break
                except:
                    continue

            if container:
                try:
                    catalog_content = driver.execute_script("return arguments[0].innerHTML", container)
                    logger.info(f"[BEFREE] Содержимое контейнера: {catalog_content[:500]}...")
                except Exception as e:
                    logger.error(f"[BEFREE] Ошибка получения контента: {e}")
            else:
                logger.warning("[BEFREE] Контейнер товаров не найден")
                self.save_debug_info(driver, f"no_container_{query}")

            try:
                WebDriverWait(driver, 60).until(
                    EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR,
                        "a[href*='/platia/'], a[href*='/product/'], a.digi-product__link"
                    ))
                )
                links = driver.find_elements(By.CSS_SELECTOR,
                                             "a[href*='/platia/'], a[href*='/product/'], a.digi-product__link")
                logger.info(f"[BEFREE] Найдено ссылок: {len(links)}")
                hrefs = [link.get_attribute('href') for link in links if link.get_attribute('href')]
                logger.info(f"[BEFREE] Все ссылки: {hrefs[:50]}...")
            except TimeoutException:
                logger.info("[BEFREE] Попытка альтернативных селекторов...")
                selectors = [
                    "a.digi-product__link",
                    "div.digi-product a",
                    "a.product-link",
                    "a[href*='/platia/']",
                    "a[href*='/product/']"
                ]
                for selector in selectors:
                    try:
                        links = driver.find_elements(By.CSS_SELECTOR, selector)
                        if links:
                            logger.info(f"[BEFREE] Найдены ссылки с селектором: {selector}")
                            break
                    except:
                        continue
                else:
                    links = []

            if links:
                seen_urls = set()
                for link in links:
                    url = link.get_attribute('href')
                    if url and ('/platia/' in url or '/product/' in url) and url not in seen_urls:
                        seen_urls.add(url)
                        if url.startswith('/'):
                            url = f"https://befree.ru{url}"
                        items.append(BefreeItem(url=url))
                logger.info(f"[BEFREE] Отфильтрованные ссылки: {list(seen_urls)}")

            logger.info(f"[BEFREE] Найдено уникальных товаров: {len(items)}")
            return items

        except Exception as e:
            logger.error(f"[BEFREE] Ошибка парсинга: {e}")
            if driver:
                self.save_debug_info(driver, f"error_{query}")
            return []
        finally:
            if driver:
                try:
                    driver.quit()
                    logger.info("[BEFREE] Драйвер закрыт")
                except Exception as e:
                    logger.error(f"[BEFREE] Ошибка при закрытии: {e}")

def test_parser():
    """Функция для тестирования парсера"""
    parser = BefreeShopParser()
    query = input("\nВведите поисковый запрос (например, 'платье'): ") or "платье"
    print(f"\nПоиск товаров: {query}")
    print("=" * 50)
    results = parser.get_product_urls(query)
    if results:
        print(f"\nНайдено товаров: {len(results)}")
        print("\nСписок найденных товаров:")
        print("-" * 100)
        for i, item in enumerate(results, 1):
            print(f"{i}. {item.url}")
        print(f"\nВсего найдено товаров: {len(results)}")
    else:
        print("Товары не найдены")
    print("=" * 100)

if __name__ == "__main__":
    test_parser()
