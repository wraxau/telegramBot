from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from dataclasses import dataclass
from typing import List
import logging
import time
from datetime import datetime
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class LichiItem:
    url: str

class LichiShopParser:
    BASE_URL = "https://lichi.com/ru/ru"

    def __init__(self):
        import tempfile
        self.chrome_options = Options()
        self.chrome_options.binary_location = "/usr/bin/google-chrome"  # Путь к Chrome
        self.chrome_options.add_argument('--headless')  # Включите для сервера
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--ignore-certificate-errors')
        self.chrome_options.add_argument('--ignore-ssl-errors')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        self.chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        self.chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        temp_dir = tempfile.mkdtemp()
        self.chrome_options.add_argument(f"--user-data-dir={temp_dir}")

    def init_driver(self):
        """Инициализация драйвера Chrome"""
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=self.chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver

    def scroll_to_bottom(self, driver):
        """Прокрутка страницы до конца для загрузки всех товаров"""
        last_height = driver.execute_script("return document.body.scrollHeight")
        scrolls = 0
        max_scrolls = 10  # Максимальное количество прокруток
        
        while scrolls < max_scrolls:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            scrolls += 1
            logger.info(f"Прокрутка {scrolls}/{max_scrolls}, высота: {new_height}")

    def save_debug_info(self, driver, prefix="debug"):
        """Сохранение отладочной информации"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"debug/{prefix}_screenshot_{timestamp}.png"
        html_path = f"debug/{prefix}_page_{timestamp}.html"
        
        try:
            import os
            os.makedirs("debug", exist_ok=True)
            driver.save_screenshot(screenshot_path)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info(f"Сохранена отладочная информация: {screenshot_path}, {html_path}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении отладочной информации: {e}")

    def get_product_urls(self, query: str) -> List[LichiItem]:
        """Получает список URL товаров по поисковому запросу"""
        driver = None
        urls = []
        try:
            logger.info(f"Инициализация драйвера Chrome...")
            driver = self.init_driver()
            
            # Переходим на главную страницу
            logger.info(f"Переход на главную страницу: {self.BASE_URL}")
            driver.get(self.BASE_URL)
            time.sleep(3)

            # Поиск кнопки поиска
            logger.info("Поиск кнопки поиска...")
            try:
                search_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "i.header-base_page_item__icon__NxNyw.header-base_search__fPIKL"))
                )
            except TimeoutException:
                logger.info("Попытка найти кнопку через XPath...")
                search_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="__next"]/header/div[1]/div[2]/ul/li[2]/i'))
                )

            # Кликаем по кнопке поиска
            logger.info("Клик по кнопке поиска...")
            search_button.click()
            time.sleep(2)  # Ждем появления поля поиска
            
            # Поиск поля ввода поиска
            logger.info("Поиск поля ввода...")
            try:
                search_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.ui-form-search_ui_search_box__input__mWuk3"))
                )
            except TimeoutException:
                logger.info("Попытка найти поле ввода через XPath...")
                search_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="sidebar_search_input"]'))
                )
            
            # Очищаем поле и вводим запрос
            logger.info(f"Ввод поискового запроса: {query}")
            search_input.clear()
            search_input.click()  # Добавляем клик по полю ввода
            time.sleep(1)  # Небольшая пауза после клика
            search_input.send_keys(query)
            search_input.send_keys(Keys.RETURN)
            
            # Ждем загрузки результатов
            time.sleep(3)
            
            # Прокручиваем страницу для загрузки всех товаров
            logger.info("Загрузка всех товаров...")
            self.scroll_to_bottom(driver)
            
            # Ищем все ссылки на товары
            logger.info("Поиск ссылок на товары...")
            product_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
            
            # Собираем уникальные ссылки
            seen_urls = set()
            for link in product_links:
                url = link.get_attribute('href')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    urls.append(LichiItem(url=url))
            
            logger.info(f"Найдено уникальных товаров: {len(urls)}")
            
            if not urls:
                logger.warning("Товары не найдены, сохраняем скриншот...")
                self.save_debug_info(driver, f"no_results_{query}")
            
            return urls
            
        except Exception as e:
            logger.error(f"Ошибка при поиске товаров: {e}")
            if driver:
                self.save_debug_info(driver, "error")
            return []
            
        finally:
            if driver:
                driver.quit()
                logger.info("Драйвер Chrome закрыт")

def test_parser():
    """Функция для тестирования парсера"""
    parser = LichiShopParser()
    
    # Тестовый запрос
    query = "платье"
    print(f"\nПоиск товаров: {query}")
    print("=" * 50)
    
    results = parser.get_product_urls(query)
    
    if results:
        print(f"\nНайдено товаров: {len(results)}")
        print("\nСписок всех найденных товаров:")
        print("-" * 100)
        
        for i, item in enumerate(results, 1):
            print(f"{i}. {item.url}")
        
        print(f"\nВсего найдено товаров: {len(results)}")
    else:
        print("Товары не найдены")
    
    print("=" * 100)

if __name__ == "__main__":
    test_parser()
