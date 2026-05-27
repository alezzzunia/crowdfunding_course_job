# Система аналізу краудфандингових даних
## Курсова робота — Практична частина

### Структура проекту
```
crowdfunding/
├── app.py           — Flask-сервер + всі маршрути
├── database.py      — SQLite БД + тестові дані
├── ml_analysis.py   — Аналіз ризиків, прогноз, NLP
├── viber_bot.py     — Viber-бот (webhook + команди)
├── requirements.txt — Залежності
└── templates/
    └── index.html   — Веб-дашборд
```

---

### Встановлення та запуск

1. Встановити залежності:
```bash
pip install -r requirements.txt
```

2. Запустити сервер:
```bash
python app.py
```

3. Відкрити браузер: http://localhost:5000

---

### REST API ендпоінти

| Метод | URL | Опис |
|-------|-----|------|
| GET  | /api/campaigns | Список кампаній |
| GET  | /api/campaigns?category=Технології | Фільтр по категорії |
| GET  | /api/campaigns/{id} | Одна кампанія |
| GET  | /api/campaigns/{id}/analytics | ML-аналіз кампанії |
| POST | /api/campaigns | Створити кампанію |
| GET  | /api/campaigns/{id}/donations | Пожертви кампанії |
| POST | /api/campaigns/{id}/donations | Додати пожертву |
| GET  | /api/stats/summary | Загальна статистика |
| GET  | /api/stats/monthly | Збір по місяцях |
| GET  | /api/stats/by_category | По категоріях |
| POST | /api/bot/test | Тест бота (без Viber) |
| GET  | /api/bot/logs | Логи бота |
| POST | /viber/webhook | Viber webhook |

---

### Viber-бот: налаштування

1. Зареєструвати бота на https://partners.viber.com
2. Скопіювати токен у viber_bot.py → `VIBER_TOKEN`
3. Налаштувати публічний URL (ngrok для тестування):
```bash
ngrok http 5000
```
4. Встановити webhook:
```bash
curl -X POST https://chatapi.viber.com/pa/set_webhook \
  -H "X-Viber-Auth-Token: ВАШ_ТОКЕН" \
  -d '{"url": "https://your-ngrok-url.ngrok.io/viber/webhook"}'
```

---

### ML-модулі

- **Оцінка ризику**: евристична модель на основі прогресу та часу
- **Прогноз збору**: лінійна регресія по щоденних пожертвах
- **Аналіз тексту**: аналіз тональності опису кампанії

---

### Команди бота

```
/топ         — топ-5 кампаній за збором
/статус      — загальна статистика платформи
/ризики      — кампанії з підвищеним ризиком
/категорії   — розподіл по категоріях
/кампанія 1  — деталі кампанії #1
/допомога    — список всіх команд
```
