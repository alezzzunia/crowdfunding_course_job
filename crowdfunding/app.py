"""
app.py — Головний Flask-сервер
Запуск: python app.py
Сервер стартує на http://localhost:5000
"""

from flask import Flask, jsonify, request, render_template
from database import init_db, get_connection
from ml_analysis import (
    calculate_risk_score,
    forecast_campaign,
    analyze_text,
    get_platform_stats,
)
from viber_bot import process_webhook

app = Flask(__name__)


# ══════════════════════════════════════════
#  ІНІЦІАЛІЗАЦІЯ БД при старті
# ══════════════════════════════════════════
init_db()


# ══════════════════════════════════════════
#  ГОЛОВНА СТОРІНКА (веб-дашборд)
# ══════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ══════════════════════════════════════════
#  REST API — КАМПАНІЇ
# ══════════════════════════════════════════

@app.route("/api/campaigns", methods=["GET"])
def get_campaigns():
    """
    GET /api/campaigns
    Параметри: category, status, sort (collected/goal/created_at), limit
    """
    category = request.args.get("category")
    status   = request.args.get("status")
    sort     = request.args.get("sort", "collected")
    limit    = int(request.args.get("limit", 50))

    # Захист від SQL-ін'єкцій: дозволяємо тільки відомі колонки
    allowed_sort = {"collected", "goal", "created_at", "title"}
    if sort not in allowed_sort:
        sort = "collected"

    query  = "SELECT * FROM campaigns WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += f" ORDER BY {sort} DESC LIMIT ?"
    params.append(limit)

    conn = get_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    campaigns = []
    for r in rows:
        c = dict(r)
        c["progress_pct"] = round(c["collected"] / c["goal"] * 100, 1) if c["goal"] else 0
        campaigns.append(c)

    return jsonify({"campaigns": campaigns, "total": len(campaigns)})


@app.route("/api/campaigns/<int:campaign_id>", methods=["GET"])
def get_campaign(campaign_id):
    """GET /api/campaigns/1 — деталі однієї кампанії"""
    conn = get_connection()
    row  = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Кампанію не знайдено"}), 404

    campaign = dict(row)
    campaign["progress_pct"] = round(campaign["collected"] / campaign["goal"] * 100, 1)
    return jsonify(campaign)


@app.route("/api/campaigns/<int:campaign_id>/analytics", methods=["GET"])
def get_campaign_analytics(campaign_id):
    """GET /api/campaigns/1/analytics — ML-аналіз кампанії"""
    conn = get_connection()
    row  = conn.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Не знайдено"}), 404

    campaign = dict(row)
    return jsonify({
        "campaign_id": campaign_id,
        "title":       campaign["title"],
        "risk":        calculate_risk_score(campaign),
        "forecast":    forecast_campaign(campaign_id),
        "sentiment":   analyze_text(campaign.get("description", "")),
    })


@app.route("/api/campaigns", methods=["POST"])
def create_campaign():
    """POST /api/campaigns — створити нову кампанію"""
    data = request.get_json()

    required = ["title", "category", "goal"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Поле '{field}' обов'язкове"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO campaigns (title, category, goal, collected, description)
        VALUES (?,?,?,0,?)
    """, (data["title"], data["category"], data["goal"], data.get("description", "")))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({"id": new_id, "message": "Кампанію створено"}), 201


# ══════════════════════════════════════════
#  REST API — ПОЖЕРТВИ
# ══════════════════════════════════════════

@app.route("/api/campaigns/<int:campaign_id>/donations", methods=["GET"])
def get_donations(campaign_id):
    """GET /api/campaigns/1/donations — список пожертв"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM donations WHERE campaign_id=?
        ORDER BY donated_at DESC LIMIT 50
    """, (campaign_id,)).fetchall()
    conn.close()
    return jsonify({"donations": [dict(r) for r in rows]})


@app.route("/api/campaigns/<int:campaign_id>/donations", methods=["POST"])
def add_donation(campaign_id):
    """POST /api/campaigns/1/donations — додати пожертву"""
    data = request.get_json()
    amount = data.get("amount", 0)

    if amount <= 0:
        return jsonify({"error": "Сума має бути більше 0"}), 400

    conn = get_connection()
    conn.execute(
        "INSERT INTO donations (campaign_id, donor_name, amount) VALUES (?,?,?)",
        (campaign_id, data.get("donor_name"), amount)
    )
    conn.execute(
        "UPDATE campaigns SET collected = collected + ? WHERE id=?",
        (amount, campaign_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Пожертву додано", "amount": amount}), 201


# ══════════════════════════════════════════
#  REST API — СТАТИСТИКА
# ══════════════════════════════════════════

@app.route("/api/stats/summary", methods=["GET"])
def stats_summary():
    """GET /api/stats/summary — зведена статистика"""
    return jsonify(get_platform_stats())


@app.route("/api/stats/monthly", methods=["GET"])
def stats_monthly():
    """GET /api/stats/monthly — збір по місяцях (для графіку)"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT strftime('%Y-%m', donated_at) as month, SUM(amount) as total
        FROM donations
        GROUP BY month
        ORDER BY month
        LIMIT 12
    """).fetchall()
    conn.close()
    return jsonify({"monthly": [dict(r) for r in rows]})


@app.route("/api/stats/by_category", methods=["GET"])
def stats_by_category():
    """GET /api/stats/by_category — по категоріях"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT category, COUNT(*) as count, SUM(collected) as funds
        FROM campaigns
        GROUP BY category
    """).fetchall()
    conn.close()
    return jsonify({"categories": [dict(r) for r in rows]})


# ══════════════════════════════════════════
#  VIBER WEBHOOK
# ══════════════════════════════════════════

@app.route("/viber/webhook", methods=["POST"])
def viber_webhook():
    """POST /viber/webhook — отримує події від Viber"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Немає даних"}), 400

    result = process_webhook(data)
    return jsonify(result)


@app.route("/api/bot/test", methods=["POST"])
def bot_test():
    """
    POST /api/bot/test — тестовий ендпоінт для перевірки бота без Viber.
    Body: {"message": "/топ"}
    """
    from viber_bot import process_command
    data = request.get_json()
    text = data.get("message", "")
    if not text:
        return jsonify({"error": "Вкажіть message"}), 400

    response = process_command(text.lower().strip())

    # Логуємо в БД
    conn = get_connection()
    conn.execute(
        "INSERT INTO bot_logs (user_id, command, response) VALUES (?,?,?)",
        ("test_user", text, response[:500])
    )
    conn.commit()
    conn.close()

    return jsonify({"command": text, "response": response})


@app.route("/api/bot/logs", methods=["GET"])
def bot_logs():
    """GET /api/bot/logs — останні запити до бота"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM bot_logs ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    return jsonify({"logs": [dict(r) for r in rows]})


# ══════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Сервер запускається на http://localhost:5000")
    app.run(debug=True, port=5000)
