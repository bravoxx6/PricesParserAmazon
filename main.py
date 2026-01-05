import time
import psycopg2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# --- НАСТРОЙКИ БАЗЫ ДАННЫХ ---
DB_CONFIG = {
    "dbname": "amazon_db",
    "user": "postgres",
    "password": "12345", 
    "host": "localhost",
    "port": "5432"
}

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
def init_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        # Создаем таблицу, если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS laptops (
                id SERIAL PRIMARY KEY NOT NULL,
                title TEXT NOT NULL,
                price VARCHAR(50) NOT NULL,
                link TEXT,
                parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
        """)
        conn.commit()
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        return None

# --- ФУНКЦИЯ ПАРСИНГА ---
def scrape_amazon(search_query, conn):
    # Настройка браузера
    options = Options()
    # options.add_argument("--headless") # Раскомментируйте, чтобы скрыть окно браузера
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    
    try:
        url = f"https://www.amazon.com/s?k={search_query}"
        print(f"Открываю: {url}")
        driver.get(url)
        
        # Ждем прогрузки (лучше использовать WebDriverWait, но для простоты sleep)
        time.sleep(5) 
        
        # Ищем карточки товаров. Селекторы актуальны на 2025, но могут меняться!
        # Amazon часто использует div с атрибутом data-component-type="s-search-result"
        items = driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
        
        cursor = conn.cursor()
        count = 0
        
        for item in items:
            try:
                # Поиск названия
                title_elem = item.find_element(By.CSS_SELECTOR, "h2 a span")
                title = title_elem.text
                
                # Поиск ссылки
                link_elem = item.find_element(By.CSS_SELECTOR, "h2 a")
                link = link_elem.get_attribute("href")
                
                # Поиск цены (она хитро спрятана, берем "offscreen" или видимую часть)
                # На Amazon цена часто дробится на целую и дробную части
                try:
                    price_elem = item.find_element(By.CSS_SELECTOR, ".a-price .a-offscreen")
                    price = price_elem.get_attribute("textContent")
                except:
                    price = "Нет цены"

                # Сохранение в PostgreSQL
                cursor.execute("""
                    INSERT INTO laptops (title, price, link)
                    VALUES (%s, %s, %s)
                """, (title, price, link))
                
                print(f"Найдено: {title[:30]}... | {price}")
                count += 1
                
            except Exception as e:
                # Иногда попадаются рекламные блоки или пустые места
                continue

        conn.commit()
        print(f"\nСохранено {count} товаров в PostgreSQL.")

    except Exception as e:
        print(f"Ошибка парсинга: {e}")
    finally:
        driver.quit()

# --- ЗАПУСК ---
if __name__ == "__main__":
    db_connection = init_db()
    if db_connection:
        scrape_amazon("laptop", db_connection)
        db_connection.close()