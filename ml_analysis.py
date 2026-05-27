"""
ml_analysis.py — Модуль машинного навчання
Містить: оцінку ризику кампанії, прогноз збору, аналіз тексту
"""

import numpy as np
from database import get_connection


# ──────────────────────────────────────────
# 1. ОЦІНКА РИЗИКУ КАМПАНІЇ (0–1, де 1 = великий ризик)
# ──────────────────────────────────────────

def calculate_risk_score(campaign: dict) -> dict:
    """
    Проста евристична оцінка ризику без зовнішніх бібліотек.
    Повертає score (0.0–1.0) та label ('Низький'/'Середній'/'Високий').
    """
    goal      = campaign["goal"]
    collected = campaign["collected"]
    progress  = collected / goal if goal > 0 else 0

    # Скільки днів пройшло
    from datetime import datetime
    try:
        created = datetime.strptime(campaign["created_at"], "%Y-%m-%d %H:%M:%S")
    except Exception:
        created = datetime.now()
    days_elapsed = max((datetime.now() - created).days, 1)

    # Очікуваний прогрес (лінійний): якщо кампанія 30 днів
    expected_progress = min(days_elapsed / 30, 1.0)

    # Фактори ризику
    r1 = max(0.0, expected_progress - progress)   # відставання від плану
    r2 = 1.0 if progress < 0.2 else 0.0           # менше 20% зібрано
    r3 = 0.3 if days_elapsed > 25 and progress < 0.5 else 0.0  # пізній етап, мало зібрано

    score = round(min(r1 * 0.5 + r2 * 0.3 + r3 * 0.2, 1.0), 2)

    if score < 0.3:
        label, color = "Низький", "green"
    elif score < 0.6:
        label, color = "Середній", "orange"
    else:
        label, color = "Високий", "red"

    return {
        "score":    score,
        "label":    label,
        "color":    color,
        "progress": round(progress * 100, 1),
        "days":     days_elapsed,
    }


# ──────────────────────────────────────────
# 2. ПРОГНОЗ ЗБОРУ НА НАСТУПНІ 7 ДНІВ
# ──────────────────────────────────────────

def forecast_campaign(campaign_id: int) -> dict:
    """
    Лінійна регресія по пожертвах за останні дні.
    Повертає прогнозовану суму за 7 днів.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT DATE(donated_at) as day, SUM(amount) as total
        FROM donations
        WHERE campaign_id = ?
        GROUP BY day
        ORDER BY day
    """, (campaign_id,)).fetchall()
    conn.close()

    if len(rows) < 2:
        return {"forecast_7d": 0, "daily_avg": 0, "trend": "немає даних"}

    amounts = [r["total"] for r in rows]
    n = len(amounts)
    x = list(range(n))

    # Формули простої лінійної регресії
    x_mean = sum(x) / n
    y_mean = sum(amounts) / n
    numerator   = sum((x[i] - x_mean) * (amounts[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    slope     = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean

    # Прогноз на 7 днів вперед
    forecast = sum(max(slope * (n + i) + intercept, 0) for i in range(7))
    daily_avg = sum(amounts) / n

    trend = "зростання" if slope > 50 else "падіння" if slope < -50 else "стабільно"

    return {
        "forecast_7d": round(forecast, 2),
        "daily_avg":   round(daily_avg, 2),
        "trend":       trend,
        "slope":       round(slope, 2),
    }


# ──────────────────────────────────────────
# 3. АНАЛІЗ ТЕКСТУ ОПИСУ (без зовнішніх бібліотек)
# ──────────────────────────────────────────

POSITIVE_WORDS = ["розвиток", "інновація", "допомога", "майбутнє", "перспектива",
                  "успіх", "покращення", "екологічний", "соціальний", "освіта"]

NEGATIVE_WORDS = ["проблема", "криза", "ризик", "невизначеність", "складно",
                  "важко", "брак", "нестача", "небезпека"]


def analyze_text(description: str) -> dict:
    """
    Простий аналіз тональності тексту опису кампанії.
    """
    if not description:
        return {"sentiment": "нейтральний", "score": 0, "positive": 0, "negative": 0}

    text = description.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    score = pos - neg

    if score > 0:
        sentiment = "позитивний"
    elif score < 0:
        sentiment = "негативний"
    else:
        sentiment = "нейтральний"

    return {
        "sentiment": sentiment,
        "score":     score,
        "positive":  pos,
        "negative":  neg,
    }


# ──────────────────────────────────────────
# 4. ЗВЕДЕНА АНАЛІТИКА ПО ВСІХ КАМПАНІЯХ
# ──────────────────────────────────────────

def get_platform_stats() -> dict:
    """Загальна статистика платформи"""
    conn = get_connection()

    campaigns = conn.execute("SELECT * FROM campaigns").fetchall()
    donations  = conn.execute("SELECT amount, donated_at FROM donations").fetchall()
    conn.close()

    total       = len(campaigns)
    completed   = sum(1 for c in campaigns if c["status"] == "completed")
    total_funds = sum(c["collected"] for c in campaigns)
    total_goal  = sum(c["goal"] for c in campaigns)
    success_rate = round(completed / total * 100, 1) if total else 0

    # Пожертви по категоріях
    by_category = {}
    for c in campaigns:
        cat = c["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    # Середня пожертва
    amounts = [d["amount"] for d in donations]
    avg_donation = round(sum(amounts) / len(amounts), 2) if amounts else 0

    return {
        "total_campaigns": total,
        "completed":       completed,
        "active":          total - completed,
        "success_rate":    success_rate,
        "total_funds":     round(total_funds, 2),
        "total_goal":      round(total_goal, 2),
        "avg_donation":    avg_donation,
        "total_donations": len(amounts),
        "by_category":     by_category,
    }
