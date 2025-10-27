# 🎫 Система управления билетами

## 📋 Архитектура

### Жизненный цикл билета:

```
1. Регистрация (handlers.py)
   ↓
2. Сохранение в БД + registration_completed_at
   ↓
3. Запуск Celery задачи generate_ticket()
   ↓
4. Генерация билета (PNG с QR-кодом)
   ↓
5. Сохранение в tickets/ticket_{telegram_id}.png
   ↓
6. Обновление БД: ticket_generated=True, ticket_path, ticket_generated_at
   ↓
7. Ожидание команды /rass
   ↓
8. /rass → Celery send_existing_ticket() для каждого билета
   ↓
9. Отправка через Telegram API
   ↓
10. Обновление БД: ticket_sent=True, ticket_sent_at
```

---

## 🗄️ Структура данных

### Поля в таблице `surveys`:

```sql
-- Временные метки
registration_started_at TIMESTAMP    -- Когда начал заполнять анкету
registration_completed_at TIMESTAMP  -- Когда завершил регистрацию
ticket_generated_at TIMESTAMP        -- Когда билет сгенерирован
ticket_sent_at TIMESTAMP             -- Когда билет отправлен
ticket_cancelled_at TIMESTAMP        -- Когда билет отменен

-- Статусы билета
ticket_generated BOOLEAN             -- Билет сгенерирован?
ticket_path VARCHAR(512)             -- Путь к файлу билета
ticket_sent BOOLEAN                  -- Билет отправлен?
ticket_cancelled BOOLEAN             -- Билет отменен?
```

---

## 📂 Хранение билетов

```
tg_bot_bpl/
├── tickets/                         # Папка с билетами
│   ├── ticket_123456789.png        # Билет пользователя 123456789
│   ├── ticket_987654321.png
│   └── ...
├── ticket_template.png              # Шаблон для генерации
└── ...
```

**Преимущества:**
- ✅ Быстрая рассылка (файлы уже готовы)
- ✅ Можно пересмотреть/проверить билеты до отправки
- ✅ Легко найти билет конкретного пользователя
- ✅ Можно удалить билет при отмене

**Объем:**
- Один билет: ~200-500 KB
- 3500 билетов: ~1-2 GB

---

## 🔄 Процессы

### 1. После регистрации

```python
# В handlers.py после сохранения в БД
from tasks import generate_ticket

# Запускаем генерацию билета в фоне
generate_ticket.delay(
    user_id=survey.id,
    user_data={
        'id': survey.id,
        'telegram_id': survey.telegram_id,
        'fio': survey.fio,
        'faculty': survey.faculty,
        'course': survey.course,
        'group': survey.group,
        'student_id': survey.student_id,
        'ticket_type': survey.pair_or_single,
        'partner_fio': survey.partner_fio
    }
)

# Пользователю показываем сообщение:
"✅ Регистрация успешна!
🎫 Билет будет сгенерирован в течение 1-2 минут.
📨 Рассылка билетов по команде администратора."
```

### 2. Команда /rass (только админы)

```python
# Получаем всех с готовыми билетами
async with async_session() as session:
    result = await session.execute(
        select(Survey).where(
            Survey.ticket_generated == True,
            Survey.ticket_sent == False,
            Survey.ticket_cancelled == False
        )
    )
    users = result.scalars().all()

# Подготавливаем данные для рассылки
tickets_to_send = [{
    'user_id': user.id,
    'telegram_id': user.telegram_id,
    'ticket_path': user.ticket_path
} for user in users]

# Запускаем рассылку
from tasks import broadcast_tickets_task
task = broadcast_tickets_task.delay(tickets_to_send)
```

### 3. Отмена билета

```python
# Когда пользователь отменяет билет
async with async_session() as session:
    # Обновляем статус
    await session.execute(
        update(Survey)
        .where(Survey.telegram_id == telegram_id)
        .values(
            ticket_cancelled=True,
            ticket_cancelled_at=datetime.utcnow()
        )
    )
    await session.commit()

# Удаляем файл билета если был сгенерирован
if os.path.exists(user.ticket_path):
    os.remove(user.ticket_path)

# Освобождаем место в registration_config
# (уменьшаем current_count)
```

### 4. Поиск незавершенных регистраций

```python
# Когда кто-то отменяет, предлагаем место тем, кто начал но не успел

# Находим тех кто начал регистрацию но не завершил
async with async_session() as session:
    result = await session.execute(
        select(Survey).where(
            Survey.registration_started_at.isnot(None),
            Survey.registration_completed_at.is_(None),
            Survey.ticket_cancelled == False
        ).order_by(Survey.registration_started_at)  # Кто раньше начал
    )
    incomplete = result.scalars().all()

# Отправляем им уведомление:
for user in incomplete:
    await bot.send_message(
        user.telegram_id,
        "🎉 Освободилось место!\n\n"
        "Вы начали регистрацию но не успели завершить.\n"
        "Теперь вы можете продолжить!\n\n"
        "Используйте /start"
    )
```

---

## 🔍 SQL запросы для мониторинга

### Статистика билетов

```sql
SELECT 
    COUNT(*) as total_registrations,
    COUNT(CASE WHEN ticket_generated = TRUE THEN 1 END) as tickets_generated,
    COUNT(CASE WHEN ticket_sent = TRUE THEN 1 END) as tickets_sent,
    COUNT(CASE WHEN ticket_cancelled = TRUE THEN 1 END) as tickets_cancelled,
    COUNT(CASE WHEN ticket_generated = FALSE THEN 1 END) as pending_generation
FROM surveys;
```

### Билеты готовые к отправке

```sql
SELECT 
    id, fio, telegram_id, ticket_path, ticket_generated_at
FROM surveys
WHERE ticket_generated = TRUE 
  AND ticket_sent = FALSE 
  AND ticket_cancelled = FALSE
ORDER BY ticket_generated_at;
```

### Незавершенные регистрации

```sql
SELECT 
    id, fio, telegram_id, 
    registration_started_at,
    NOW() - registration_started_at as time_since_start
FROM surveys
WHERE registration_started_at IS NOT NULL
  AND registration_completed_at IS NULL
  AND ticket_cancelled = FALSE
ORDER BY registration_started_at;
```

### Скорость генерации билетов

```sql
SELECT 
    AVG(EXTRACT(EPOCH FROM (ticket_generated_at - registration_completed_at))) as avg_generation_time_seconds
FROM surveys
WHERE ticket_generated = TRUE;
```

---

## 🔧 Административные команды

### Регенерация билета (если испорчен)

```python
@dp.message(Command("regenerate"))
async def cmd_regenerate(message: Message):
    """Перегенерировать билет для пользователя"""
    if not is_admin(message.from_user.id):
        return
    
    # Формат: /regenerate 123456789 (telegram_id)
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Формат: /regenerate <telegram_id>")
        return
    
    telegram_id = parts[1]
    
    # Найти пользователя
    async with async_session() as session:
        result = await session.execute(
            select(Survey).filter_by(telegram_id=telegram_id)
        )
        user = result.scalars().first()
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Удалить старый билет
    if user.ticket_path and os.path.exists(user.ticket_path):
        os.remove(user.ticket_path)
    
    # Сбросить статус
    async with async_session() as session:
        await session.execute(
            update(Survey)
            .where(Survey.id == user.id)
            .values(
                ticket_generated=False,
                ticket_path=None,
                ticket_generated_at=None
            )
        )
        await session.commit()
    
    # Запустить генерацию заново
    generate_ticket.delay(user.id, {...})
    
    await message.answer(f"✅ Билет для {user.fio} будет перегенерирован")
```

### Проверка статуса билетов

```python
@dp.message(Command("check_tickets"))
async def cmd_check_tickets(message: Message):
    """Проверить статус билетов"""
    if not is_admin(message.from_user.id):
        return
    
    async with async_session() as session:
        result = await session.execute(select(Survey))
        users = result.scalars().all()
    
    stats = {
        'total': len(users),
        'generated': sum(1 for u in users if u.ticket_generated),
        'sent': sum(1 for u in users if u.ticket_sent),
        'pending': sum(1 for u in users if not u.ticket_generated),
        'cancelled': sum(1 for u in users if u.ticket_cancelled)
    }
    
    text = (
        f"📊 **СТАТУС БИЛЕТОВ**\n\n"
        f"👥 Всего регистраций: {stats['total']}\n"
        f"🎫 Билетов сгенерировано: {stats['generated']}\n"
        f"📨 Билетов отправлено: {stats['sent']}\n"
        f"⏳ Ожидают генерации: {stats['pending']}\n"
        f"❌ Отменено: {stats['cancelled']}\n"
    )
    
    await message.answer(text, parse_mode="Markdown")
```

---

## ⚠️ Обработка ошибок

### Если генерация билета провалилась

```python
# В tasks.py уже есть retry механизм
# Если после 3 попыток не получилось:

# 1. Записываем в БД что билет НЕ сгенерирован
# 2. Уведомляем администратора

async def notify_admin_ticket_failed(user_id: int, error: str):
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"⚠️ Не удалось сгенерировать билет!\n\n"
            f"User ID: {user_id}\n"
            f"Ошибка: {error}\n\n"
            f"Используйте /regenerate {user_id}"
        )
```

### Если отправка провалилась

```python
# Celery автоматически повторит отправку 3 раза
# Если все попытки провалились - билет останется в статусе:
# ticket_generated=True, ticket_sent=False

# Можно повторить отправку позже:
await cmd_rass(message)  # Отправит только неотправленные
```

---

## 🚀 Производительность

### Генерация

- **Скорость**: ~10-15 билетов/секунду (на одном воркере)
- **3500 билетов**: ~4-6 минут
- **Решение**: Запустить 3-5 Celery workers

```yaml
# docker-compose.yml
celery_worker:
  deploy:
    replicas: 5  # 5 воркеров
  command: ["celery", "-A", "tasks", "worker", "--concurrency=3"]
  # 5 воркеров × 3 concurrent = 15 задач одновременно
```

### Рассылка

- **Telegram лимит**: ~30 сообщений/секунду
- **С задержкой 50ms**: ~20 сообщений/секунду
- **3500 билетов**: ~3 минуты

---

## ✅ Checklist

- [ ] Папка `tickets/` создана и доступна для записи
- [ ] Шаблон `ticket_template.png` на месте
- [ ] Celery workers запущены
- [ ] Тестовая генерация прошла успешно
- [ ] Тестовая отправка прошла успешно
- [ ] Мониторинг настроен (Flower)
- [ ] Резервное копирование папки `tickets/`

---

**Система готова к работе! 🎫**

