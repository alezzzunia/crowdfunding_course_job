"""
database.py — Ініціалізація БД та тестові дані
Використовується SQLite (файл crowdfunding.db)
"""

import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "crowdfunding.db"


def get_connection():
    """Повертає з'єднання з БД"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # дозволяє звертатись до колонок по імені
    return conn


def init_db():
    """Створює таблиці та заповнює тестовими даними"""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблиця кампаній
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            category    TEXT NOT NULL,
            goal        REAL NOT NULL,
            collected   REAL DEFAULT 0,
            description TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # Таблиця пожертв
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id  INTEGER NOT NULL,
            donor_name   TEXT,
            amount       REAL NOT NULL,
            donated_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )
    """)

    # Таблиця запитів Viber-бота
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT,
            command    TEXT,
            response   TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Якщо кампаній ще немає — додаємо тестові дані
    cursor.execute("SELECT COUNT(*) FROM campaigns")
    if cursor.fetchone()[0] == 0:
        _seed_data(cursor)

    conn.commit()
    conn.close()
    print("✅ База даних ініціалізована")


def _seed_data(cursor):
    """Вставляє тестові кампанії та пожертви"""
    categories = ["Технології", "Соціальні", "Мистецтво", "Наука", "Освіта"]

    campaigns = [
        ("EcoTech UA",        "Технології", 500000, 423000, "Розробка еко-сенсорів для міст"),
        ("MedHelp Lviv",      "Соціальні",  200000, 201500, "Медичне обладнання для лікарні"),
        ("Art Space Kyiv",    "Мистецтво",  150000,  58000, "Відкриття арт-простору"),
        ("SciLab Kharkiv",    "Наука",      350000,  42000, "Наукова лабораторія"),
        ("GreenCity",         "Технології", 280000, 201600, "Озеленення міських дахів"),
        ("EdTech Start",      "Освіта",     200000, 126000, "Платформа онлайн-навчання"),
        ("Folk Art Revival",  "Мистецтво",   80000,  74400, "Відродження народних ремесел"),
        ("BioResearch UA",    "Наука",      450000,  49500, "Біомедичні дослідження"),
        ("Solar Villages",    "Технології", 600000, 522000, "Сонячні панелі для сіл"),
        ("Kids Future",       "Соціальні",  120000, 120000, "Дитячі майданчики"),
    ]

    for title, cat, goal, collected, desc in campaigns:
        days_ago = random.randint(5, 60)
        created = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
        status = "completed" if collected >= goal else "active"
        cursor.execute(
            "INSERT INTO campaigns (title, category, goal, collected, description, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (title, cat, goal, collected, desc, status, created)
        )

    # Генеруємо пожертви за останні 30 днів
    random.seed(42)
    for campaign_id in range(1, 11):
        n = random.randint(10, 40)
        for _ in range(n):
            amount = round(random.uniform(100, 5000), 2)
            days_ago = random.randint(0, 30)
            donated_at = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            names = ["Іван", "Марія", "Олег", "Наталя", "Петро", "Анна", "Тарас", None]
            cursor.execute(
                "INSERT INTO donations (campaign_id, donor_name, amount, donated_at) VALUES (?,?,?,?)",
                (campaign_id, random.choice(names), amount, donated_at)
            )

    print("✅ Тестові дані додано")
