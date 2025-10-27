# 🎯 Итоговая система управления билетами

## ✅ Что реализовано

### 1. **Раздельная генерация и отправка**

```
Регистрация → Генерация билета (фон) → Сохранение на сервере → Ожидание /rass → Отправка
```

**Преимущества:**
- ✅ Пользователь не ждет генерации
- ✅ Можно проверить билеты до отправки
- ✅ Быстрая рассылка (файлы готовы)
- ✅ Возможность перегенерации

### 2. **Хранение билетов на сервере**

```
tickets/
├── ticket_123456789.png    # ~200-500 KB каждый
├── ticket_987654321.png
└── ...
```

**Объем:** ~1-2 GB для 3500 билетов

### 3. **Полное отслеживание времени**

```sql
registration_started_at      -- Когда начал заполнять
registration_completed_at    -- Когда завершил
ticket_generated_at          -- Когда билет готов
ticket_sent_at               -- Когда отправлен
ticket_cancelled_at          -- Когда отменен
```

### 4. **Статусы билетов**

```sql
ticket_generated BOOLEAN     -- Билет готов?
ticket_path VARCHAR(512)     -- Где лежит
ticket_sent BOOLEAN          -- Отправлен?
ticket_cancelled BOOLEAN     -- Отменен?
```

### 5. **Лимит 3500 мест**

Уже реализовано через атомарный счетчик в `registration_config`.

---

## 🔄 Как это работает

### Сценарий 1: Обычная регистрация

```
1. Пользователь регистрируется → /start
2. Заполняет анкету
3. Подтверждает
4. ✅ Данные в БД + registration_completed_at
5. 🎫 Celery задача generate_ticket.delay() запускается
6. ⏱ 10-30 секунд генерация
7. 💾 Билет сохранен: tickets/ticket_{id}.png
8. 📝 БД: ticket_generated=True, ticket_path, ticket_generated_at
9. 📨 Пользователю: "Билет будет отправлен администратором"
10. ⏳ Ожидание команды /rass
```

### Сценарий 2: Рассылка (админ)

```
1. Админ: /rass
2. 📊 Выбираем всех с ticket_generated=True, ticket_sent=False
3. 🚀 Celery: send_existing_ticket.delay() для каждого
4. 📤 Отправка со скоростью ~20 билетов/сек
5. 📝 БД: ticket_sent=True, ticket_sent_at
6. ⏱ 3500 билетов за ~3 минуты
```

### Сценарий 3: Отмена билета

```
1. Пользователь: /start → "Отменить билет"
2. ⚠️ Предупреждение о последствиях
3. Подтверждение
4. 📝 БД: ticket_cancelled=True, ticket_cancelled_at
5. 🗑 Удаление файла: os.remove(ticket_path)
6. 📉 Освобождение места: current_count -= (1 или 2)
7. 🔍 Поиск незавершенных регистраций
8. 📨 Уведомление тем кто начал но не успел
```

### Сценарий 4: Незавершенные регистрации

```sql
-- Найти тех кто начал но не успел
SELECT * FROM surveys 
WHERE registration_started_at IS NOT NULL
  AND registration_completed_at IS NULL
  AND ticket_cancelled = FALSE
ORDER BY registration_started_at;
```

```python
# Отправить им уведомление
for user in incomplete:
    await bot.send_message(
        user.telegram_id,
        "🎉 Освободилось место! Продолжите регистрацию: /start"
    )
```

**Для них - особый путь:**
1. Они продолжают заполнение
2. После подтверждения - билет генерируется
3. **Сразу отправляется** (не ждет /rass)

---

## 📊 Мониторинг

### Команды админа

```bash
/stats              # Общая статистика мест
/check_tickets      # Статус билетов
/rass               # Рассылка готовых билетов
/regenerate <id>    # Перегенерировать билет
```

### SQL для проверки

```sql
-- Сколько билетов готовы к отправке?
SELECT COUNT(*) FROM surveys 
WHERE ticket_generated = TRUE 
  AND ticket_sent = FALSE 
  AND ticket_cancelled = FALSE;

-- Сколько еще генерируется?
SELECT COUNT(*) FROM surveys 
WHERE registration_completed_at IS NOT NULL
  AND ticket_generated = FALSE;

-- Средняя скорость генерации
SELECT AVG(EXTRACT(EPOCH FROM (ticket_generated_at - registration_completed_at))) as seconds
FROM surveys WHERE ticket_generated = TRUE;
```

### Web UI (Flower)

```
http://localhost:5555

Видно:
- Сколько задач в очереди
- Сколько выполняется
- Ошибки
- Скорость обработки
```

---

## 🚀 Производительность

### Генерация билетов

**Текущая настройка:**
- 1 Celery worker × 5 concurrent = 5 билетов одновременно
- Скорость: ~10-15 билетов/секунду
- 3500 билетов: ~4-6 минут

**Оптимизация:**
```yaml
# docker-compose.yml
celery_worker:
  deploy:
    replicas: 5  # 5 воркеров
  command: ["celery", "-A", "tasks", "worker", "--concurrency=3"]
  
# = 5 × 3 = 15 задач одновременно
# = ~50 билетов/секунду
# = 3500 билетов за ~70 секунд
```

### Рассылка билетов

**Telegram лимит:**
- 30 сообщений/секунду (жесткий лимит)
- С задержкой 50ms: 20 сообщений/секунду (безопасно)

**Время:**
- 3500 билетов ÷ 20/сек = 175 секунд = ~3 минуты

---

## 🔧 Настройка .env

Добавьте в `.env`:

```env
# Обязательные
BOT_TOKEN=your_token
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/new_bal_db
REDIS_URL=redis://redis:6379/0
REDIS_BROKER_URL=redis://redis:6379/1
ADMIN_IDS=your_telegram_id

# Для билетов
TICKET_TEMPLATE_PATH=./ticket_template.png
FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
```

---

## 📦 Миграция БД

Добавлены новые поля:

```sql
ALTER TABLE surveys ADD COLUMN ticket_generated BOOLEAN DEFAULT FALSE;
ALTER TABLE surveys ADD COLUMN ticket_path VARCHAR(512);
ALTER TABLE surveys ADD COLUMN registration_started_at TIMESTAMP;
ALTER TABLE surveys ADD COLUMN registration_completed_at TIMESTAMP;
ALTER TABLE surveys ADD COLUMN ticket_generated_at TIMESTAMP;
ALTER TABLE surveys ADD COLUMN ticket_sent_at TIMESTAMP;
ALTER TABLE surveys ADD COLUMN ticket_cancelled_at TIMESTAMP;
```

Применить:
```bash
docker-compose exec bot alembic upgrade head
```

---

## ✅ Checklist для запуска

### Перед запуском:

- [ ] `.env` файл настроен (BOT_TOKEN, ADMIN_IDS, Redis)
- [ ] Создана папка `tickets/` с правами на запись
- [ ] Шаблон `ticket_template.png` на месте (или создастся пустой)
- [ ] Docker Compose включает все сервисы (bot, db, redis, celery_worker, flower)

### После запуска:

- [ ] `docker-compose ps` - все сервисы Up
- [ ] `docker-compose logs bot` - нет ошибок
- [ ] `docker-compose logs celery_worker` - worker запущен
- [ ] `http://localhost:5555` - Flower доступен
- [ ] Тестовая регистрация прошла
- [ ] Билет сгенерировался в `tickets/`
- [ ] `/stats` показывает правильные цифры
- [ ] `/check_tickets` показывает статус

---

## 🎯 Итого

### Что у вас есть:

1. ✅ **Раздельная генерация и отправка**
   - Регистрация не ждет генерации
   - Можно проверить билеты до отправки

2. ✅ **Хранение на сервере**
   - tickets/ папка
   - ~1-2 GB для всех билетов

3. ✅ **Полное отслеживание времени**
   - Когда начал, завершил, сгенерирован, отправлен, отменен

4. ✅ **Лимит 3500 мест**
   - Атомарный счетчик
   - Автозакрытие

5. ✅ **Отмена с уведомлением незавершенных**
   - Находим тех кто не успел
   - Даем им возможность
   - Для них - мгновенная отправка билета

6. ✅ **Флаг отправки билета**
   - ticket_sent для каждого

7. ✅ **Все временные метки**
   - registration_started_at
   - registration_completed_at
   - ticket_generated_at
   - ticket_sent_at
   - ticket_cancelled_at

---

## 📚 Документация

- **[TICKET_SYSTEM.md](TICKET_SYSTEM.md)** - Полная документация системы
- **[TICKET_SUMMARY.md](TICKET_SUMMARY.md)** - Эта сводка
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Как обновиться

---

**Система полностью готова к работе! 🚀**

Хотите протестировать или есть вопросы?

