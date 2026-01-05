import re
import time
import psycopg2
from psycopg2 import sql
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------- DB CONFIG ----------
DB_CONFIG = {
    "dbname": "amazon_db",
    "user": "postgres",
    "password": "12345",
    "host": "localhost",
    "port": "5432"
}

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding('UTF8')  # 🔥 КЛЮЧЕВО
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS laptops (
            id SERIAL PRIMARY KEY,
            model TEXT NOT NULL,
            price TEXT,
            old_price TEXT DEFAULT '',
            discount TEXT DEFAULT '',
            link TEXT UNIQUE,
            parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    return conn


def parse_price_to_float(price_str):
    """Извлекает число из строки цены, возвращает float или None"""
    if not price_str:
        return None
    # Удаляем все кроме цифр и точки/запятой
    cleaned = re.sub(r'[^\d.,]', '', price_str).replace(',', '.')
    # Возможны вариации вроде "1,299.99" -> оставим только последнюю точку
    # Простая логика: если несколько точек — оставим последнюю как десятичную
    parts = cleaned.split('.')
    if len(parts) > 2:
        # объединяем все кроме последнего
        cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
    try:
        return float(cleaned)
    except:
        return None

def safe_find_text(element, selectors):
    """Пытается вернуть текст/атрибут по списку селекторов (css селектор или xpath)"""
    for sel in selectors:
        try:
            if sel.startswith('//') or sel.startswith('.//'):
                el = element.find_element(By.XPATH, sel)
            else:
                el = element.find_element(By.CSS_SELECTOR, sel)
            # для цен иногда используем get_attribute
            txt = el.get_attribute("textContent") or el.text
            if txt:
                return txt.strip()
        except:
            continue
    return None

def parse_amazon_v2():
    conn = init_db()
    try:
        with conn:
            with conn.cursor() as cur:
                options = Options()
                # имитация обычного браузера
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("start-maximized")
                # поменяйте user-agent при необходимости
                options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
                # НЕ включаем headless по умолчанию — он чаще вызывает капчу
                driver = webdriver.Chrome(options=options)

                try:
                    driver.get("https://www.amazon.com/s?k=laptop")
                    # выдержка для загрузки и первичный скролл
                    print("Прокручиваю страницу для загрузки товаров...")
                    for _ in range(6):
                        driver.execute_script("window.scrollBy(0, 900);")
                        time.sleep(1.2)

                    # Ждём карточки
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-component-type='s-search-result']"))
                        )
                    except Exception as e:
                        print("Элементы не появились на странице. Возможно капча или блокировка.")
                        return

                    cards = driver.find_elements(By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
                    print(f"Найдено карточек: {len(cards)}")

                    for idx, card in enumerate(cards, start=1):
                        try:
                            # Название: пробуем несколько мест
                            model = None
                            # В некоторых карточках название в h2 > a > span
                            model = safe_find_text(card, ["h2 a span", "h2", "img"])
                            if not model:
                                # fallback: искать внутри ссылки
                                try:
                                    a = card.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")
                                    model = a.get_attribute("title") or a.text
                                except:
                                    pass
                            if isinstance(model, str) and len(model) > 300:
                                model = model[:300]

                            # Ссылка товара
                            link = None
                            try:
                                a_tag = card.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")
                                link = a_tag.get_attribute("href")
                            except:
                                try:
                                    link = card.find_element(By.TAG_NAME, "a").get_attribute("href")
                                except:
                                    link = None

                            # Цена: несколько вариантов
                            price = safe_find_text(card, [".a-price .a-offscreen", ".sg-col-inner .a-price .a-offscreen"])
                            old_price = safe_find_text(card, [".a-price.a-text-price .a-offscreen", ".a-price-whole + .a-price-fraction"])
                            discount = safe_find_text(card, [".a-letter-space + .a-size-base", ".s-label-popover-default"])

                            price_value = parse_price_to_float(price)

                            if link and model and price:
                                cur.execute("""
                                    INSERT INTO laptops (model, price, old_price, discount, link)
                                    VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (link) DO NOTHING;
                                """, (model, price, old_price or '', discount or '', link))
                                print(f"[{idx}] Вставлено/обнаружено: {model[:60]} — {price}")
                            else:
                                print(f"[{idx}] Пропущена карточка (не все поля найдены). model={bool(model)}, price={bool(price)}, link={bool(link)}")

                        except Exception as e:
                            # не останавливаем весь парсинг из-за одной карточки
                            print("Ошибка при обработке карточки:", e)
                            continue

                    # коммит делается автоматически в with conn:
                    print("Парсинг завершён, изменения сохранены.")

                finally:
                    driver.quit()
    finally:
        conn.close()

if __name__ == "__main__":
    parse_amazon_v2()
