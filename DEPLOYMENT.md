# 🚀 Руководство по развертыванию высоконагруженного бота

## 📋 Содержание
1. [Архитектура системы](#архитектура-системы)
2. [Требования](#требования)
3. [Быстрый старт](#быстрый-старт)
4. [Настройка](#настройка)
5. [Запуск в продакшене](#запуск-в-продакшене)
6. [Мониторинг](#мониторинг)
7. [Команды администратора](#команды-администратора)
8. [Тестирование под нагрузкой](#тестирование-под-нагрузкой)

---

## 🏗 Архитектура системы

```
┌─────────────────┐
│  Telegram Bot   │ (1-5 инстансов)
│   Long Polling  │
└────────┬────────┘
         │
         ├──► Redis (FSM storage + Celery broker)
         │    - База 0: FSM состояния
         │    - База 1: Celery очередь
         │
         ├──► PostgreSQL (данные + атомарный счетчик)
         │    - max_connections=500
         │    - Оптимизирован для записи
         │
         └──► Celery Workers (генерация билетов)
              - 5 concurrent tasks
              - Автоматические повторы
```

### Ключевые особенности:

- ⚡ **Атомарный счетчик мест** с `SELECT FOR UPDATE`
- 🛡️ **Rate limiting** и anti-flood защита
- 🔄 **Redis storage** для состояний (не теряются при перезапуске)
- 📊 **Connection pooling** (50 базовых + 100 overflow)
- 🎫 **Асинхронная рассылка** через Celery
- 📈 **Масштабируемость** до 5 инстансов бота

---

## 💻 Требования

### Минимальные (для разработки):
- CPU: 2 ядра
- RAM: 4 GB
- Disk: 10 GB SSD

### Рекомендуемые (для продакшена с 3500 пользователями):
- CPU: 4-6 ядер
- RAM: 8 GB
- Disk: 20 GB SSD
- Сеть: 100 Мбит/с

### Программное обеспечение:
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (для локальной разработки)

---

## 🚀 Быстрый старт

### 1. Клонирование и настройка

```bash
# Клонируйте репозиторий
git clone <your-repo>
cd tg_bot_bpl

# Создайте .env файл
cp env.example .env
nano .env  # Заполните необходимые переменные
```

### 2. Настройка .env

```env
# Получите токен от @BotFather
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Ваш Telegram ID (можно узнать через @userinfobot)
ADMIN_IDS=123456789,987654321

# База данных (можно оставить по умолчанию для начала)
DB_USER=user
DB_PASSWORD=SecurePassword123
DB_NAME=new_bal_db
```

### 3. Запуск через Docker

```bash
# Сборка и запуск всех сервисов
docker-compose up -d --build

# Проверка логов
docker-compose logs -f bot

# Применение миграций
docker-compose exec bot alembic upgrade head
```

### 4. Проверка работоспособности

```bash
# Все сервисы должны быть "healthy"
docker-compose ps

# Проверьте логи
docker-compose logs bot
docker-compose logs celery_worker
```

Откройте Telegram и напишите боту `/start`

---

## ⚙️ Настройка

### Изменение лимита мест

Отредактируйте `db/models.py`:

```python
max_capacity = Column(Integer, default=5000, nullable=False)  # было 3500
```

Или через SQL после запуска:

```sql
UPDATE registration_config SET max_capacity = 5000 WHERE id = 1;
```

### Настройка Rate Limiting

В `bot/handlers.py`:

```python
# Для обычных пользователей
dp.message.middleware(RateLimitMiddleware(rate_limit=5))  # 5 сообщений/сек

# Anti-flood
dp.message.middleware(AntiFloodMiddleware(
    max_messages=20,  # максимум сообщений
    period=60,        # за 60 секунд
    ban_time=300      # блокировка на 5 минут
))
```

### Масштабирование бота

В `docker-compose.yml`:

```yaml
bot:
  deploy:
    replicas: 3  # Увеличьте до 3-5 инстансов
```

**Внимание:** При использовании Long Polling можно запустить только 1 инстанс!
Для масштабирования нужно переключиться на Webhook.

---

## 🏭 Запуск в продакшене

### 1. Подготовка сервера (VPS/VDS)

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
sudo apt install docker-compose-plugin -y
```

### 2. Настройка файрвола

```bash
# Разрешаем только нужные порты
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp   # HTTPS (для webhook в будущем)
sudo ufw enable
```

### 3. Размещение шаблона билета

```bash
# Создайте папку для билетов
mkdir -p tickets

# Загрузите шаблон билета
# Рекомендуемый размер: 1200x600 px
cp /path/to/your/template.png ticket_template.png
```

### 4. Запуск с мониторингом

```bash
# Запуск в фоне
docker-compose up -d

# Автоматический перезапуск при сбое
docker-compose restart bot

# Просмотр live логов
docker-compose logs -f bot celery_worker
```

### 5. Резервное копирование

```bash
# Бэкап базы данных
docker-compose exec db pg_dump -U user new_bal_db > backup_$(date +%Y%m%d).sql

# Восстановление
cat backup_20251026.sql | docker-compose exec -T db psql -U user new_bal_db
```

---

## 📊 Мониторинг

### 1. Celery Flower (Web UI)

Откройте в браузере: `http://your-server:5555`

Здесь можно отслеживать:
- Количество обработанных задач
- Скорость обработки
- Ошибки
- Статистику воркеров

### 2. Логи

```bash
# Все логи
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Только Celery
docker-compose logs -f celery_worker

# Последние 100 строк
docker-compose logs --tail=100 bot
```

### 3. Метрики базы данных

```bash
# Подключение к PostgreSQL
docker-compose exec db psql -U user new_bal_db

# Количество подключений
SELECT count(*) FROM pg_stat_activity;

# Активные запросы
SELECT pid, now() - query_start as duration, query 
FROM pg_stat_activity 
WHERE state = 'active';
```

### 4. PgAdmin (Web UI)

Откройте: `http://your-server:8080`

Логин: `admin@example.com` (из .env)
Пароль: `admin` (из .env)

---

## 👨‍💼 Команды администратора

### `/stats` - Статистика регистрации

```
📊 СТАТИСТИКА РЕГИСТРАЦИИ

👥 Зарегистрировано: 2450 / 3500
📍 Осталось мест: 1050
📈 Заполнено: 70%
🚪 Статус: 🟢 ОТКРЫТА
```

### `/rass` - Рассылка билетов

Запускает генерацию и рассылку билетов всем зарегистрированным пользователям.

**⚠️ Внимание:**
- Рассылка 3500 билетов займет ~3-5 минут
- Убедитесь, что Celery worker запущен
- Проверьте наличие шаблона `ticket_template.png`

**Процесс:**
1. Генерация QR-кода для каждого билета
2. Наложение данных на шаблон
3. Отправка через Telegram
4. Автоматические повторы при ошибках

---

## 🧪 Тестирование под нагрузкой

### Нагрузочное тестирование с Locust

Установите Locust:

```bash
pip install locust
```

Создайте `locustfile.py`:

```python
from locust import HttpUser, task, between

class BotUser(HttpUser):
    wait_time = between(0.1, 0.5)  # Задержка между запросами
    
    @task
    def register(self):
        # Симуляция регистрации
        # Здесь нужно использовать Telegram Bot API
        pass
```

Запуск:

```bash
locust -f locustfile.py --host=https://api.telegram.org
```

### Стресс-тест базы данных

```sql
-- Генерация 1000 тестовых регистраций
DO $$
BEGIN
  FOR i IN 1..1000 LOOP
    INSERT INTO surveys (consent, fio, "group", student_id, telegram_id, pair_or_single)
    VALUES (true, 'Test User ' || i, 'TEST-' || i, '100000' || i, '1000' || i, 'single');
  END LOOP;
END $$;
```

### Мониторинг производительности

```bash
# CPU и память
docker stats

# Сетевая активность
docker-compose exec bot apt-get install -y iftop
iftop
```

---

## 🔧 Решение проблем

### Бот не отвечает

```bash
# Проверьте статус
docker-compose ps

# Перезапустите бота
docker-compose restart bot

# Проверьте логи
docker-compose logs --tail=50 bot
```

### Рассылка не работает

```bash
# Проверьте Celery worker
docker-compose logs celery_worker

# Перезапустите worker
docker-compose restart celery_worker

# Проверьте очередь в Redis
docker-compose exec redis redis-cli
> SELECT 1
> LLEN celery
```

### База данных заполнена

```bash
# Очистка старых записей (ОСТОРОЖНО!)
docker-compose exec db psql -U user new_bal_db -c "DELETE FROM surveys WHERE created_at < NOW() - INTERVAL '30 days';"

# Vacuum для освобождения места
docker-compose exec db psql -U user new_bal_db -c "VACUUM FULL;"
```

### Регистрация закрылась слишком рано

```sql
-- Проверьте счетчик
SELECT * FROM registration_config;

-- Пересчитайте вручную
UPDATE registration_config 
SET current_count = (SELECT COUNT(*) * 1 + COUNT(*) FILTER (WHERE pair_or_single = 'pair') FROM surveys);
```

---

## 📝 Чеклист перед запуском мероприятия

- [ ] Проверить `.env` файл (BOT_TOKEN, ADMIN_IDS)
- [ ] Залить шаблон билета `ticket_template.png`
- [ ] Применить миграции: `alembic upgrade head`
- [ ] Проверить статус: `docker-compose ps`
- [ ] Проверить лимит мест: `/stats`
- [ ] Открыть регистрацию (по умолчанию открыта)
- [ ] Протестировать полный цикл регистрации
- [ ] Настроить алерты и мониторинг
- [ ] Подготовить резервную копию БД
- [ ] Убедиться что Celery worker работает
- [ ] Проверить доступность Redis

---

## 🆘 Контакты и поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs`
2. Проверьте статус сервисов: `docker-compose ps`
3. Перезапустите сервис: `docker-compose restart <service>`
4. Обратитесь к администратору

---

## 📈 Масштабирование для больших мероприятий (10,000+ человек)

Если вам нужно обрабатывать больше 10,000 регистраций:

1. **Переключитесь на Webhook** вместо Long Polling
2. **Увеличьте replicas** бота до 5-10
3. **Используйте внешний PostgreSQL** (managed service)
4. **Добавьте Redis Cluster**
5. **Увеличьте Celery workers** до 10+
6. **Настройте Load Balancer** (nginx)
7. **Включите CDN** для билетов

---

**Удачного запуска! 🚀**

