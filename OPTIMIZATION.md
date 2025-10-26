# 🚀 Оптимизация для Production

## 🎯 Советы для работы с 3500+ регистраций за 3 часа

### 1. Переключение на Webhook (вместо Long Polling)

Long Polling не поддерживает масштабирование (несколько инстансов бота).
Для высокой нагрузки используйте Webhook.

#### Настройка Webhook:

```python
# main.py
from aiohttp import web

async def webhook(request):
    update = await request.json()
    await dp.feed_webhook_update(bot, types.Update(**update))
    return web.Response(text="OK")

async def on_startup(app):
    webhook_url = f"https://your-domain.com/webhook/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)
    await initialize_registration_config()

app = web.Application()
app.router.add_post(f'/webhook/{BOT_TOKEN}', webhook)
app.on_startup.append(on_startup)

web.run_app(app, host='0.0.0.0', port=8443)
```

#### Преимущества Webhook:
- ✅ Поддержка нескольких инстансов бота
- ✅ Меньшая нагрузка на Telegram API
- ✅ Быстрее обрабатывает обновления

### 2. Оптимизация PostgreSQL

#### Настройки для высокой нагрузки записи:

```sql
-- postgresql.conf

# Память
shared_buffers = 512MB
effective_cache_size = 2GB
maintenance_work_mem = 128MB
work_mem = 8MB

# Checkpoint (для большого количества записей)
checkpoint_completion_target = 0.9
wal_buffers = 32MB
min_wal_size = 2GB
max_wal_size = 8GB

# Connections
max_connections = 1000

# Параллелизм
max_worker_processes = 8
max_parallel_workers = 8
max_parallel_workers_per_gather = 4

# Vacuum (автоматическая очистка)
autovacuum = on
autovacuum_max_workers = 4
```

#### Индексы для быстрых запросов:

```sql
-- Уже есть в миграции, но для справки:
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_telegram_id 
ON surveys(telegram_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_created_at 
ON surveys(created_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pair_or_single 
ON surveys(pair_or_single);
```

### 3. Redis оптимизация

```conf
# redis.conf

# Память
maxmemory 1gb
maxmemory-policy allkeys-lru

# Персистентность (для FSM storage)
save 900 1
save 300 10
save 60 10000

appendonly yes
appendfsync everysec

# Performance
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

### 4. Масштабирование бота

#### docker-compose.yml для production:

```yaml
bot:
  deploy:
    replicas: 3  # 3-5 инстансов
    update_config:
      parallelism: 1
      delay: 10s
    restart_policy:
      condition: on-failure
      delay: 5s
      max_attempts: 3
  resources:
    limits:
      cpus: '1'
      memory: 512M
    reservations:
      cpus: '0.5'
      memory: 256M
```

### 5. Celery оптимизация для рассылки

```python
# tasks.py - оптимизированные настройки

celery_app.conf.update(
    # Производительность
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_compression='gzip',
    
    # Retry стратегия
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Таймауты
    task_time_limit=300,
    task_soft_time_limit=240,
    
    # Приоритеты задач
    task_default_priority=5,
    task_inherit_parent_priority=True,
    
    # Результаты
    result_expires=3600,  # Хранить результаты 1 час
    result_compression='gzip',
)
```

#### Масштабирование Celery workers:

```yaml
celery_worker:
  deploy:
    replicas: 3  # 3 воркера по 5 concurrent = 15 одновременно
    resources:
      limits:
        cpus: '2'
        memory: 1G
```

### 6. Оптимизация отправки билетов

#### Батчинг (отправка группами):

```python
# tasks.py - улучшенная версия

from celery import group, chord

@celery_app.task
def send_batch(users_batch: list):
    """Отправляет пачку билетов (50-100 за раз)"""
    for user in users_batch:
        generate_and_send_ticket(user)

def broadcast_with_batching(all_users: list, batch_size=50):
    """Разбивает на батчи для эффективности"""
    batches = [all_users[i:i+batch_size] 
               for i in range(0, len(all_users), batch_size)]
    
    job = group(send_batch.s(batch) for batch in batches)
    return job.apply_async()
```

### 7. Мониторинг и алерты

#### Prometheus + Grafana

Добавьте в `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
```

#### prometheus.yml:

```yaml
scrape_configs:
  - job_name: 'bot'
    static_configs:
      - targets: ['bot:8000']
  
  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### 8. Nginx Load Balancer (для Webhook)

```nginx
# nginx.conf

upstream telegram_bot {
    least_conn;  # Балансировка по наименьшей нагрузке
    server bot1:8443 max_fails=3 fail_timeout=30s;
    server bot2:8443 max_fails=3 fail_timeout=30s;
    server bot3:8443 max_fails=3 fail_timeout=30s;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;
    
    location /webhook/ {
        proxy_pass http://telegram_bot;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 9. Кэширование

#### Redis для кэширования частых запросов:

```python
# db/cache.py

import redis
import json
from functools import wraps

redis_cache = redis.Redis(host='redis', port=6379, db=2, decode_responses=True)

def cache_result(expire=300):
    """Декоратор для кэширования результатов"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # Пробуем взять из кэша
            cached = redis_cache.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # Вычисляем и сохраняем
            result = await func(*args, **kwargs)
            redis_cache.setex(cache_key, expire, json.dumps(result))
            return result
        return wrapper
    return decorator

# Использование
@cache_result(expire=60)  # кэш на 1 минуту
async def get_registration_stats():
    # ...
```

### 10. Logging и Error Tracking

#### Sentry для отслеживания ошибок:

```python
# main.py

import sentry_sdk

sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=0.1,  # 10% транзакций
    profiles_sample_rate=0.1,
)
```

#### Structured logging:

```python
import structlog

logger = structlog.get_logger()

# Используйте так:
logger.info("registration_successful", 
           user_id=user_id, 
           ticket_type=ticket_type,
           remaining_seats=remaining)
```

### 11. Database Connection Pool тюнинг

```python
# db/session.py - production настройки

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    
    # Pool размеры (адаптируйте под нагрузку)
    pool_size=100,              # Увеличено для высокой нагрузки
    max_overflow=200,           # Еще больше overflow
    
    # Timeouts
    pool_timeout=30,
    pool_recycle=1800,          # 30 минут
    pool_pre_ping=True,
    
    # Performance
    connect_args={
        "timeout": 30,
        "command_timeout": 60,
        "server_settings": {
            "application_name": "tg_bot",
            "jit": "off",  # Отключить JIT для стабильности
        }
    }
)
```

### 12. Rate Limiting для Telegram API

```python
# bot/rate_limiter.py

import asyncio
from collections import deque
from datetime import datetime

class TelegramRateLimiter:
    """
    Telegram лимиты:
    - 30 сообщений/сек на бота
    - 20 сообщений/мин на пользователя
    """
    def __init__(self, max_per_second=25):  # 25 для безопасности
        self.max_per_second = max_per_second
        self.timestamps = deque()
    
    async def acquire(self):
        now = datetime.now()
        
        # Очищаем старые timestamp
        while self.timestamps and (now - self.timestamps[0]).total_seconds() > 1:
            self.timestamps.popleft()
        
        # Ждем если превышен лимит
        if len(self.timestamps) >= self.max_per_second:
            sleep_time = 1 - (now - self.timestamps[0]).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self.timestamps.popleft()
        
        self.timestamps.append(now)

# Использование
rate_limiter = TelegramRateLimiter()

async def send_message_safe(chat_id, text):
    await rate_limiter.acquire()
    await bot.send_message(chat_id, text)
```

---

## 📊 Checklist перед мероприятием

- [ ] Провести load testing (см. DEPLOYMENT.md)
- [ ] Проверить backup стратегию
- [ ] Настроить алерты (Sentry, Prometheus)
- [ ] Увеличить replicas бота до 3-5
- [ ] Проверить disk space (минимум 20GB свободно)
- [ ] Настроить автоматический restart при падении
- [ ] Подготовить runbook для типичных проблем
- [ ] Убедиться что Celery workers работают
- [ ] Проверить шаблон билета
- [ ] Протестировать полную рассылку на 10-20 тестовых пользователях

---

## 🎯 Ожидаемая производительность

С предложенными оптимизациями:

- ⚡ **1500+ регистраций/час** (пиковая нагрузка)
- 📨 **7000+ билетов/час** (рассылка)
- 🔒 **100% гарантия лимита мест**
- ⏱️ **<100ms latency** на обработку сообщения
- 💾 **<2GB RAM** на инстанс бота
- 📊 **<50% CPU** при средней нагрузке

---

**Готово к масштабу enterprise! 🚀**

