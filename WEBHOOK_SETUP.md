# 🌐 Настройка Webhook для масштабирования

## Зачем нужен Webhook?

**Long Polling (текущий режим):**
- ✅ Простой в настройке
- ✅ Не требует домена
- ❌ Только 1 инстанс бота
- ❌ Больше нагрузки на Telegram API

**Webhook (для production):**
- ✅ Поддержка нескольких инстансов
- ✅ Меньше нагрузки
- ✅ Быстрее обрабатывает
- ❌ Требует домен с SSL

**Рекомендация:** Для 3500+ пользователей переходите на Webhook.

---

## 📋 Требования

1. **Домен** с SSL сертификатом (HTTPS)
   - Можно бесплатно: Cloudflare, Let's Encrypt
   
2. **Открытый порт** (443 или 8443)

3. **Reverse proxy** (nginx/caddy) - опционально но рекомендуется

---

## 🚀 Быстрая настройка

### Вариант 1: С Nginx (рекомендуется)

#### 1. Настройте Nginx

```nginx
# /etc/nginx/sites-available/bot

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    location /webhook/ {
        proxy_pass http://localhost:8443;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

Активируйте:
```bash
sudo ln -s /etc/nginx/sites-available/bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 2. Обновите .env

```env
WEBHOOK_HOST=https://your-domain.com
WEBHOOK_PATH=/webhook/your_bot_token
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8443
```

#### 3. Запустите бота

```bash
python main_webhook.py
```

---

### Вариант 2: Без Nginx (прямое подключение)

#### 1. Получите SSL сертификат

```bash
# Certbot
sudo certbot certonly --standalone -d your-domain.com
```

#### 2. Обновите .env

```env
WEBHOOK_HOST=https://your-domain.com
WEBHOOK_PATH=/webhook/your_bot_token
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=443  # или 8443
```

#### 3. Запустите с правами root (для порта 443)

```bash
sudo python main_webhook.py
```

---

## 🐳 Docker с Webhook

### docker-compose.yml

```yaml
services:
  bot:
    build: .
    command: ["python", "main_webhook.py"]
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - WEBHOOK_HOST=https://your-domain.com
      - WEBHOOK_PATH=/webhook/${BOT_TOKEN}
      - WEBAPP_HOST=0.0.0.0
      - WEBAPP_PORT=8443
    ports:
      - "8443:8443"
    restart: always
```

---

## 🔄 Масштабирование (несколько инстансов)

### docker-compose.yml

```yaml
services:
  bot:
    deploy:
      replicas: 3  # 3 инстанса
    build: .
    command: ["python", "main_webhook.py"]
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - WEBHOOK_HOST=https://your-domain.com
      - WEBHOOK_PATH=/webhook/${BOT_TOKEN}
      - WEBAPP_HOST=0.0.0.0
      - WEBAPP_PORT=8443
```

### Nginx Load Balancer

```nginx
upstream telegram_bot {
    least_conn;  # Балансировка по нагрузке
    server bot1:8443;
    server bot2:8443;
    server bot3:8443;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    location /webhook/ {
        proxy_pass http://telegram_bot;
        # ... остальные настройки
    }
}
```

---

## 🔍 Проверка

### Проверить webhook

```bash
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
```

Должно вернуть:
```json
{
  "ok": true,
  "result": {
    "url": "https://your-domain.com/webhook/your_token",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

### Health check

```bash
curl http://your-domain.com/health
```

### Логи

```bash
# Docker
docker-compose logs -f bot

# Локально
tail -f bot.log
```

---

## ⚡ Производительность

| Режим | Инстансов | Обработка (req/sec) | Память (на инстанс) |
|-------|-----------|---------------------|---------------------|
| Long Polling | 1 | ~30 | 100-200 MB |
| Webhook | 1 | ~100 | 150-250 MB |
| Webhook | 3 | ~300 | 150-250 MB |
| Webhook | 5 | ~500 | 150-250 MB |

---

## 🔐 Безопасность

### 1. Скройте токен в URL

В `.env`:
```env
WEBHOOK_PATH=/webhook/${BOT_TOKEN}
```

Telegram автоматически подставит токен.

### 2. Проверка IP Telegram

```nginx
# В nginx
location /webhook/ {
    # Разрешаем только IP Telegram
    allow 149.154.160.0/20;
    allow 91.108.4.0/22;
    deny all;
    
    proxy_pass http://localhost:8443;
}
```

### 3. Rate limiting

```nginx
limit_req_zone $binary_remote_addr zone=webhook:10m rate=100r/s;

location /webhook/ {
    limit_req zone=webhook burst=200;
    proxy_pass http://localhost:8443;
}
```

---

## 🐛 Решение проблем

### Бот не отвечает

1. Проверьте webhook:
```bash
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

2. Проверьте логи:
```bash
docker-compose logs bot
```

3. Проверьте порты:
```bash
netstat -tlnp | grep 8443
```

### 502 Bad Gateway

- Бот не запущен
- Неправильный WEBAPP_PORT
- Nginx не может подключиться

### SSL ошибки

- Проверьте сертификат
- Telegram требует валидный SSL
- Используйте Let's Encrypt

---

## 🔄 Откат на Long Polling

Если что-то пошло не так:

```bash
# Удалите webhook
curl https://api.telegram.org/bot<TOKEN>/deleteWebhook

# Запустите старую версию
python main.py
```

---

## 📊 Мониторинг

### Prometheus метрики

Добавьте в `main_webhook.py`:

```python
from prometheus_client import Counter, Histogram, generate_latest

updates_total = Counter('telegram_updates_total', 'Total updates')
response_time = Histogram('telegram_response_seconds', 'Response time')

async def metrics_handler(request):
    return web.Response(body=generate_latest(), content_type='text/plain')

app.router.add_get("/metrics", metrics_handler)
```

### Grafana Dashboard

Создайте дашборд с метриками:
- Updates per second
- Response time
- Active connections
- Memory usage

---

## ✅ Checklist

- [ ] Домен настроен
- [ ] SSL сертификат получен
- [ ] Nginx настроен (если используется)
- [ ] .env файл обновлен
- [ ] Webhook установлен успешно
- [ ] Health check работает
- [ ] Логи проверены
- [ ] Тестовая регистрация прошла
- [ ] Мониторинг настроен

---

**Готово к масштабированию! 🚀**

Для вопросов см. [OPTIMIZATION.md](OPTIMIZATION.md)

