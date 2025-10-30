# 📊 Система мониторинга бота

## 🎯 Что у вас уже работает:

### 1️⃣ **Flower** - Мониторинг Celery (очереди задач)
**URL**: `http://YOUR_SERVER:5555`

**Что показывает:**
- 📊 Количество задач в очереди
- ⏱️ Время выполнения задач
- ✅ Успешные задачи
- ❌ Упавшие задачи
- 🔄 Текущие задачи (в процессе)
- 📈 Графики производительности

**Как использовать:**
```bash
# Открыть в браузере
http://5.53.125.89:5555

# Смотреть в реальном времени:
# - Tasks -> по типу (generate_ticket, send_existing_ticket, broadcast_tickets_task)
# - Workers -> сколько воркеров активно
# - Monitor -> графики в реальном времени
```

**Критичные метрики при ажиотаже:**
- **Active tasks** > 50 → очередь растёт быстро
- **Failed tasks** > 0 → проверить логи
- **Task time** > 5 сек → медленная генерация

---

### 2️⃣ **PgAdmin** - Управление БД
**URL**: `http://YOUR_SERVER:8080`

**Логин:**
- Email: `admin@example.com` (из `.env`)
- Password: `admin` (из `.env`)

**Что делать:**
1. Добавить сервер:
   - Host: `db`
   - Port: `5432`
   - Database: `new_bal_db`
   - Username: `user`
   - Password: `pass`

2. **Полезные запросы** (Query Tool):

```sql
-- 📊 Общая статистика
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN ticket_generated THEN 1 ELSE 0 END) as generated,
    SUM(CASE WHEN ticket_sent THEN 1 ELSE 0 END) as sent,
    SUM(CASE WHEN ticket_cancelled THEN 1 ELSE 0 END) as cancelled
FROM surveys;

-- ⏱️ Средняя скорость генерации
SELECT 
    AVG(EXTRACT(EPOCH FROM (ticket_generated_at - registration_completed_at))) as avg_seconds
FROM surveys 
WHERE ticket_generated = TRUE;

-- 🔍 Активные блокировки (если тормозит)
SELECT 
    pid,
    state,
    wait_event,
    query,
    NOW() - query_start as duration
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- 📈 Скорость регистрации (по минутам)
SELECT 
    DATE_TRUNC('minute', created_at) as minute,
    COUNT(*) as registrations
FROM surveys
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC
LIMIT 20;
```

---

### 3️⃣ **Docker Stats** - Нагрузка на контейнеры
```bash
# Реальное время
docker stats

# Или только нужные контейнеры
docker stats $(docker ps --format "{{.Names}}" | grep -E "bot|celery|db")
```

**Критичные показатели:**
- **CPU > 90%** → добавить реплик
- **MEM > 90%** → увеличить лимиты
- **NET I/O** - должен расти при рассылке

---

## 🚀 Дополнительный мониторинг (опционально):

### 4️⃣ **Prometheus + Grafana** - Продвинутая аналитика

Хотите добавить? Создам красивые дашборды! 📊

**Что покажет:**
- 📈 Графики регистраций в реальном времени
- 🎫 Скорость генерации/отправки билетов
- 💾 Использование ресурсов (CPU, RAM, Disk)
- 🔴 Алерты при проблемах
- 📊 Метрики PostgreSQL и Redis

---

## 📱 Простой мониторинг через Telegram (сейчас)

Уже работает через админские команды:

```
/stats - Статистика регистрации
```

Показывает:
- Зарегистрировано: X / 3500
- Статус: ОТКРЫТА/ЗАКРЫТА

---

## 🎯 Сценарии мониторинга:

### При открытии регистрации (первые 30 секунд):

**1. Flower** (`http://SERVER:5555`)
- Смотрим: Tasks → Active
- Должно: Задачи `generate_ticket` начинают появляться

**2. Docker Stats**
```bash
docker stats
```
- Смотрим: CPU% для `bot_1`, `bot_2`, `bot_3`
- Должно: ~50-80% каждый при ажиотаже

**3. Логи бота**
```bash
docker-compose logs -f bot --tail=100
```
- Смотрим: "✅ Registration: user_id=..."
- Должно: Сыпаться регистрации

### Через 5-10 минут (генерация идёт):

**Flower** → Workers → `celery_worker_1` и `celery_worker_2`
- Смотрим: сколько задач выполнено
- Считаем скорость: tasks/минуту

### Перед рассылкой:

**PgAdmin** или команда:
```bash
docker-compose exec db psql -U user -d new_bal_db -c "
SELECT 
    COUNT(*) FILTER (WHERE ticket_generated = TRUE AND ticket_sent = FALSE) as ready_to_send,
    COUNT(*) FILTER (WHERE ticket_generated = FALSE) as not_generated
FROM surveys 
WHERE ticket_cancelled = FALSE;
"
```

---

## 🔔 Создать уведомления в Telegram?

Могу добавить функцию, чтобы бот сам писал админу:

```python
# Когда регистрация заполнилась
→ "✅ Все 3500 мест заполнены за 12 секунд!"

# Когда билеты сгенерированы
→ "🎫 Все билеты готовы! Можно делать /rass"

# Если есть ошибки
→ "⚠️ 15 билетов не сгенерировались, проверьте логи"
```

Хотите добавить? 🤔

---

## 📋 Быстрая памятка:

| Инструмент | URL | Для чего |
|-----------|-----|----------|
| **Flower** | `http://SERVER:5555` | Очереди Celery |
| **PgAdmin** | `http://SERVER:8080` | База данных |
| **Docker Stats** | `docker stats` | Ресурсы контейнеров |
| **Логи** | `docker-compose logs -f bot` | Ошибки и события |

**Готово к мониторингу! 📊**

