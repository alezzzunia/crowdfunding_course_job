"""
viber_bot.py — Обробник Viber-бота
Отримує повідомлення через webhook і відповідає аналітикою
"""

import json
import requests
from database import get_connection
from ml_analysis import get_platform_stats, calculate_risk_score, forecast_campaign

# ──────────────────────────────────────────
# НАЛАШТУВАННЯ (замінити на реальні дані)
# ──────────────────────────────────────────
VIBER_TOKEN = "ВАШ_VIBER_TOKEN_ТУТ"
VIBER_API   = "https://chatapi.viber.com/pa/send_message"

SENDER_INFO = {
    "name":   "CrowdBot UA",
    "avatar": ""
}


# ──────────────────────────────────────────
# ВІДПРАВКА ПОВІДОМЛЕННЯ
# ──────────────────────────────────────────

def send_message(user_id: str, text: str):
    """Відправляє текстове повідомлення користувачу Viber"""
    payload = {
        "receiver": user_id,
        "min_api_version": 1,
        "sender": SENDER_INFO,
        "tracking_data": "tracking",
        "type": "text",
        "text": text,
    }
    headers = {
        "X-Viber-Auth-Token": VIBER_TOKEN,
        "Content-Type":       "application/json",
    }
    try:
        r = requests.post(VIBER_API, json=payload, headers=headers, timeout=5)
        return r.json()
    except Exception as e:
        print(f"Помилка відправки: {e}")
        return None


# ──────────────────────────────────────────
# ОБРОБКА КОМАНД
# ──────────────────────────────────────────

def handle_message(user_id: str, text: str) -> str:
    """
    Головна функція: отримує команду і повертає відповідь.
    Також зберігає лог у БД.
    """
    text = text.strip().lower()
    response = process_command(text)

    # Зберігаємо лог
    conn = get_connection()
    conn.execute(
        "INSERT INTO bot_logs (user_id, command, response) VALUES (?,?,?)",
        (user_id, text, response[:500])
    )
    conn.commit()
    conn.close()

    return response


def process_command(text: str) -> str:
    """Визначає команду і формує відповідь"""

    if text in ("/start", "start", "привіт", "старт"):
        return (
            "👋 Вітаю! Я CrowdBot — бот аналізу краудфандингу.\n\n"
            "📋 Команди:\n"
            "/топ — топ кампанії\n"
            "/статус — загальна статистика\n"
            "/ризики — кампанії з ризиком\n"
            "/категорії — розподіл по категоріях\n"
            "/допомога — всі команди"
        )

    elif text in ("/топ", "/top"):
        return _cmd_top()

    elif text in ("/статус", "/status", "/stats"):
        return _cmd_status()

    elif text in ("/ризики", "/risks"):
        return _cmd_risks()

    elif text in ("/категорії", "/categories"):
        return _cmd_categories()

    elif text.startswith("/кампанія ") or text.startswith("/campaign "):
        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return _cmd_campaign_detail(int(parts[1]))
        return "❌ Вкажіть ID: /кампанія 1"

    elif text in ("/допомога", "/help"):
        return _cmd_help()

    else:
        return (
            "🤔 Не знаю такої команди.\n"
            "Напишіть /допомога щоб побачити список."
        )


# ──────────────────────────────────────────
# КОМАНДИ
# ──────────────────────────────────────────

def _cmd_top() -> str:
    conn = get_connection()
    rows = conn.execute("""
        SELECT title, goal, collected, status
        FROM campaigns
        ORDER BY collected DESC
        LIMIT 5
    """).fetchall()
    conn.close()

    lines = ["📊 Топ-5 кампаній за збором:\n"]
    for i, r in enumerate(rows, 1):
        pct = round(r["collected"] / r["goal"] * 100)
        bar = "✅" if r["status"] == "completed" else "🔥"
        lines.append(f"{i}. {bar} {r['title']}")
        lines.append(f"   ₴{r['collected']:,.0f} / ₴{r['goal']:,.0f} ({pct}%)")
    return "\n".join(lines)


def _cmd_status() -> str:
    s = get_platform_stats()
    return (
        f"📈 Загальна статистика:\n\n"
        f"Кампаній всього: {s['total_campaigns']}\n"
        f"Активних: {s['active']}\n"
        f"Завершених: {s['completed']}\n"
        f"Успішність: {s['success_rate']}%\n"
        f"Зібрано: ₴{s['total_funds']:,.0f}\n"
        f"Ціль: ₴{s['total_goal']:,.0f}\n"
        f"Пожертв: {s['total_donations']}\n"
        f"Середня пожертва: ₴{s['avg_donation']:,.0f}"
    )


def _cmd_risks() -> str:
    conn = get_connection()
    campaigns = conn.execute(
        "SELECT * FROM campaigns WHERE status='active'"
    ).fetchall()
    conn.close()

    risky = []
    for c in campaigns:
        r = calculate_risk_score(dict(c))
        if r["score"] >= 0.4:
            risky.append((c["title"], r))

    if not risky:
        return "✅ Кампаній з високим ризиком не виявлено!"

    lines = [f"⚠️ Кампанії з ризиком ({len(risky)}):\n"]
    for title, r in risky:
        lines.append(f"• {title}")
        lines.append(f"  Ризик: {r['label']} ({r['score']}) | {r['progress']}%")
    return "\n".join(lines)


def _cmd_categories() -> str:
    stats = get_platform_stats()
    lines = ["🗂 Кампанії по категоріях:\n"]
    for cat, count in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
        lines.append(f"• {cat}: {count} кампаній")
    return "\n".join(lines)


def _cmd_campaign_detail(campaign_id: int) -> str:
    conn = get_connection()
    c = conn.execute(
        "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
    ).fetchone()
    conn.close()

    if not c:
        return f"❌ Кампанію #{campaign_id} не знайдено"

    risk     = calculate_risk_score(dict(c))
    forecast = forecast_campaign(campaign_id)
    pct      = round(c["collected"] / c["goal"] * 100) if c["goal"] else 0

    return (
        f"📋 {c['title']}\n\n"
        f"Категорія: {c['category']}\n"
        f"Ціль: ₴{c['goal']:,.0f}\n"
        f"Зібрано: ₴{c['collected']:,.0f} ({pct}%)\n"
        f"Статус: {c['status']}\n\n"
        f"🧠 ML-аналіз:\n"
        f"Ризик: {risk['label']} ({risk['score']})\n"
        f"Тренд: {forecast['trend']}\n"
        f"Прогноз 7 днів: ₴{forecast['forecast_7d']:,.0f}\n"
        f"Ср. збір/день: ₴{forecast['daily_avg']:,.0f}"
    )


def _cmd_help() -> str:
    return (
        "📋 Всі команди CrowdBot:\n\n"
        "/топ — топ-5 кампаній\n"
        "/статус — статистика платформи\n"
        "/ризики — кампанії з ризиком\n"
        "/категорії — розподіл по категоріях\n"
        "/кампанія {id} — деталі кампанії\n"
        "/допомога — ця довідка\n\n"
        "💡 Просто напишіть запит — бот розуміє вільний текст!"
    )


# ──────────────────────────────────────────
# ОБРОБКА WEBHOOK (викликається з app.py)
# ──────────────────────────────────────────

def process_webhook(data: dict) -> dict:
    """
    Приймає дані від Viber і відповідає.
    Повертає словник з результатом.
    """
    event = data.get("event")

    # Підписка нового користувача
    if event in ("subscribed", "conversation_started"):
        user_id = data.get("user", {}).get("id", "")
        response = handle_message(user_id, "/start")
        send_message(user_id, response)
        return {"status": "ok", "event": event}

    # Вхідне повідомлення
    if event == "message":
        user_id  = data.get("sender", {}).get("id", "")
        msg_type = data.get("message", {}).get("type", "")
        text     = data.get("message", {}).get("text", "")

        if msg_type == "text" and text:
            response = handle_message(user_id, text)
            send_message(user_id, response)
            return {"status": "ok", "reply": response}

    return {"status": "ignored", "event": event}
