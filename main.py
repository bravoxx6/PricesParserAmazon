import re
import time
import psycopg2
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
from dotenv import load_dotenv


load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}


# ---------- INIT DB ----------
def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_client_encoding('UTF8')
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS laptops (
            id SERIAL PRIMARY KEY,
            model TEXT NOT NULL,
            price NUMERIC,
            discount NUMERIC,
            price_str TEXT,
            discount_str TEXT,
            parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    return conn

# ---------- PARSING HELPERS ----------
def parse_price_to_float(price_str):
    """Извлекает число из строки цены, возвращает float или None"""
    if not price_str:
        return None
    cleaned = re.sub(r'[^\d.,]', '', price_str).replace(',', '.')
    parts = cleaned.split('.')
    if len(parts) > 2:
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
            txt = el.get_attribute("textContent") or el.text
            if txt:
                return txt.strip()
        except:
            continue
    return None

# ---------- SELENIUM DRIVER ----------
def init_driver(headless=False):
    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    if headless:
        options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    return driver

def scroll_page(driver, times=6, pause=1.2):
    for _ in range(times):
        driver.execute_script("window.scrollBy(0, 900);")
        time.sleep(pause)

# ---------- PARSE ONE CARD ----------
def parse_card(card):
    model = safe_find_text(card, ["h2 a span", "h2", "img"])
    if not model:
        try:
            a = card.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline")
            model = a.get_attribute("title") or a.text
        except:
            pass
    if isinstance(model, str) and len(model) > 300:
        model = model[:300]

    price_str = safe_find_text(card, [".a-price .a-offscreen", ".sg-col-inner .a-price .a-offscreen"])
    discount_str = safe_find_text(card, [".a-letter-space + .a-size-base", ".s-label-popover-default"])

    price = parse_price_to_float(price_str)
    discount = parse_price_to_float(discount_str)

    return {
        "model": model,
        "price": price,
        "discount": discount,
        "price_str": price_str or '',
        "discount_str": discount_str or ''
    }

# ---------- INSERT INTO DB ----------
def insert_laptop(cur, data):
    cur.execute("""
        INSERT INTO laptops (model, price, discount, price_str, discount_str)
        VALUES (%s, %s, %s, %s, %s);
    """, (data['model'], data['price'], data['discount'], data['price_str'], data['discount_str']))

# ---------- MAIN PARSING FUNCTION ----------
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time


def parse_amazon(url="https://www.amazon.com/s?k=laptop",
                 scroll_times=3,
                 scroll_pause=1.2):

    conn = init_db()
    cur = conn.cursor()
    driver = init_driver(headless=False)

    try:
        driver.get(url)

        page_num = 1

        while True:
            print(f"\n=== Страница {page_num} ===")

            scroll_page(driver, times=scroll_times, pause=scroll_pause)

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div[data-component-type='s-search-result']")
                    )
                )
            except TimeoutException:
                print("Карточки не загрузились (капча или блок).")
                break

            cards = driver.find_elements(
                By.CSS_SELECTOR, "div[data-component-type='s-search-result']"
            )
            print(f"Найдено карточек: {len(cards)}")

            for idx, card in enumerate(cards, start=1):
                try:
                    data = parse_card(card)
                    if data.get('model') and data.get('price'):
                        insert_laptop(cur, data)
                        print(f"[{page_num}:{idx}] {data['model'][:60]} — {data['price']}")
                    else:
                        print(f"[{page_num}:{idx}] Пропуск (нет данных)")
                except Exception as e:
                    print(f"[{page_num}:{idx}] Ошибка карточки:", e)

            conn.commit()

            # ---------- NEXT PAGE ----------
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a.s-pagination-next")

                if "s-pagination-disabled" in next_btn.get_attribute("class"):
                    print("Это последняя страница.")
                    break

                next_btn.click()

                WebDriverWait(driver, 10).until(
                    EC.staleness_of(cards[0])
                )

                page_num += 1

            except NoSuchElementException:
                print("Кнопка Next не найдена.")
                break

    finally:
        cur.close()
        conn.close()
        driver.quit()
        print("\nПарсинг завершён.")


# ---------- RUN ----------
if __name__ == "__main__":
    parse_amazon()


# <a href="/s?k=Laptop&amp;i=computers&amp;rh=n%3A565108&amp;page=2&amp;qid=1767631695&amp;xpid=uD2GHbCi8d_P3&amp;ref=sr_pg_1" role="button" tabindex="0" aria-label="Go to next page, page 2" class="s-pagination-item s-pagination-next s-pagination-button s-pagination-button-accessibility s-pagination-separator">Next<svg xmlns="http://www.w3.org/2000/svg" width="8" height="12" viewBox="0 0 8 12" focusable="false" aria-hidden="true"><path d="M2.126.35a1.28 1.28 0 00-1.761 0 1.165 1.165 0 000 1.695L4.478 6 .365 9.955a1.165 1.165 0 000 1.694 1.28 1.28 0 001.76 0L8 6 2.126.35z"></path></svg></a>