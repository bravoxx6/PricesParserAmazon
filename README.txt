# Amazon Parser (Selenium + PostgreSQL)

This is a Python-based parser for Amazon products and reviews using **Selenium** for web scraping and **PostgreSQL** for data storage. Designed for dynamic content handling and scalable data collection.

---

## 🚀 Features

- Scrape Amazon product details (title, price, rating, etc.)
- Collect user reviews and ratings
- Handle dynamic pages using Selenium
- Store data in PostgreSQL for analysis

---

## 🛠️ Technology Stack

- Python 3.x  
- Selenium  
- PostgreSQL  
- psycopg2  

---

## ⚙️ Installation

1. Clone the repository:
```bash
git clone https://github.com/bravoxx6/amazon-parser.git
cd amazon-parser
2.
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
3.
pip install -r requirements.txt
4.
DB_NAME=amazon_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432




