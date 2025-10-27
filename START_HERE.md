# 🚀 С ЧЕГО НАЧАТЬ

## ✅ Что уже сделано

Я полностью переработал систему согласно вашим требованиям:

1. ✅ Webhook версия (для масштабирования)
2. ✅ Новые поля в БД (is_student, faculty, course, временные метки)
3. ✅ Новый порядок вопросов (как вы просили)
4. ✅ Валидация студ. билета (ровно 6 цифр)
5. ✅ Редактирование анкеты после отправки
6. ✅ Отмена билета с предупреждением
7. ✅ **Умная система билетов:**
   - Генерация после регистрации (фон)
   - Хранение на сервере
   - Рассылка по команде /rass
   - Отслеживание всех временных меток
   - Уведомление незавершенных при отмене

---

## ⚠️ ЧТО СДЕЛАТЬ СЕЙЧАС

### Шаг 1: Дополните .env файл

Ваш текущий `.env`:
```env
BOT_TOKEN=8469981217:AAHAOe-THNhbaiZb13M2zjpyhL911ercStM
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/new_bal_db
```

**Добавьте:**
```env
# Redis (ОБЯЗАТЕЛЬНО!)
REDIS_URL=redis://redis:6379/0
REDIS_BROKER_URL=redis://redis:6379/1

# Ваш Telegram ID (узнайте через @userinfobot)
ADMIN_IDS=YOUR_TELEGRAM_ID

# Опционально
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=admin
```

**Как узнать свой Telegram ID:**
1. Откройте Telegram
2. Напишите @userinfobot
3. Он пришлет ваш ID
4. Вставьте в .env: `ADMIN_IDS=123456789`

---

### Шаг 2: Создайте бэкап БД (ОБЯЗАТЕЛЬНО!)

```bash
docker-compose exec db pg_dump -U user new_bal_db > backup_$(date +%Y%m%d).sql
```

Если у вас Windows PowerShell:
```powershell
docker-compose exec db pg_dump -U user new_bal_db > backup.sql
```

---

### Шаг 3: Проверьте длину student_id

```bash
docker-compose exec db psql -U user new_bal_db
```

```sql
-- Проверка
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN LENGTH(student_id) > 6 THEN 1 END) as need_fix
FROM surveys;

-- Если need_fix > 0, исправьте:
UPDATE surveys SET student_id = RIGHT(student_id, 6) WHERE LENGTH(student_id) > 6;
UPDATE surveys SET partner_student_id = RIGHT(partner_student_id, 6) WHERE LENGTH(partner_student_id) > 6;

-- Выход
\q
```

---

### Шаг 4: Пересоберите контейнеры

```bash
# Остановите всё
docker-compose down

# Запустите заново с новыми сервисами
docker-compose up -d --build

# Подождите 1-2 минуты пока всё запустится
```

---

### Шаг 5: Примените миграции

```bash
# Дождитесь когда всё запустится
docker-compose ps

# Примените миграции
docker-compose exec bot alembic upgrade head

# Должно вывести:
# INFO [alembic.runtime.migration] Running upgrade 0002 -> 0003
```

---

### Шаг 6: Проверьте

```bash
# Проверьте логи
docker-compose logs --tail=50 bot

# Проверьте что все сервисы запущены
docker-compose ps

# Должны быть:
# db              Up (healthy)
# redis           Up (healthy)
# bot             Up
# celery_worker   Up
# flower          Up
# pgadmin         Up
```

---

### Шаг 7: Протестируйте

1. **Откройте Telegram**, напишите боту `/start`

2. **Пройдите регистрацию** с новыми вопросами:
   - Согласие
   - Студент/Выпускник ← НОВОЕ
   - ФИО
   - Факультет ← НОВОЕ (кнопками)
   - Курс ← НОВОЕ (кнопками)
   - Группа (в кавычках)
   - Студ. билет (6 цифр) ← НОВОЕ

3. **Проверьте админ команды** (если добавили ADMIN_IDS):
   - `/stats` - статистика
   - `/check_tickets` - статус билетов (НОВОЕ)

4. **Проверьте Flower** (мониторинг Celery):
   - http://localhost:5555

---

## 📊 Новая архитектура билетов

### Как теперь работает:

```
1. Регистрация
   ↓
2. Данные в БД + флаг registration_completed_at
   ↓
3. Celery задача: генерация билета (фон)
   ↓
4. Билет сохранен в tickets/ticket_{id}.png
   ↓
5. БД: ticket_generated=True, ticket_generated_at
   ↓
6. Ждем команду админа: /rass
   ↓
7. Рассылка готовых билетов (~3 минуты на 3500)
   ↓
8. БД: ticket_sent=True, ticket_sent_at
```

### Преимущества:

- ✅ Пользователь не ждет генерации
- ✅ Можно проверить билеты до отправки
- ✅ Быстрая рассылка (файлы готовы)
- ✅ Полное отслеживание времени
- ✅ При отмене - уведомление тех кто не успел

---

## 📁 Структура проекта

```
tg_bot_bpl/
├── tickets/                  # Сгенерированные билеты (создастся автоматически)
│   ├── ticket_123.png
│   └── ...
├── ticket_template.png       # Шаблон (создайте или будет пустой)
├── .env                      # ДОПОЛНИТЕ!
├── docker-compose.yml        # Обновлен (новые сервисы)
├── bot/
│   ├── handlers.py           # Полностью переписан
│   └── ...
├── db/
│   └── models.py             # Новые поля
└── tasks.py                  # Обновлен (генерация билетов)
```

---

## 🎨 Шаблон билета (опционально)

Если хотите кастомный билет:

1. Создайте изображение 1200x600 px
2. Сохраните как `ticket_template.png`
3. QR-код добавится автоматически в позицию (900, 300)

Или используйте скрипт:
```bash
docker-compose exec bot python create_test_template.py
```

---

## 🐛 Если что-то пошло не так

### Бот не запускается

```bash
# Проверьте логи
docker-compose logs bot

# Скорее всего не хватает переменных в .env
# Добавьте REDIS_URL и ADMIN_IDS
```

### База не подключается

```bash
# Проверьте статус
docker-compose ps db

# Подождите еще минуту, БД может долго стартовать
docker-compose logs db
```

### Celery worker не работает

```bash
# Проверьте логи
docker-compose logs celery_worker

# Перезапустите
docker-compose restart celery_worker
```

---

## 📚 Документация

### Главное:
- **[TICKET_SUMMARY.md](TICKET_SUMMARY.md)** ← Про систему билетов
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** ← Если проблемы

### Подробно:
- [TICKET_SYSTEM.md](TICKET_SYSTEM.md) - Полная документация
- [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md) - Для масштабирования
- [QUICKSTART.md](QUICKSTART.md) - Быстрый старт

---

## ✅ Checklist

- [ ] `.env` дополнен (REDIS_URL, ADMIN_IDS)
- [ ] Бэкап БД создан
- [ ] student_id проверен (если < 6 цифр)
- [ ] `docker-compose down && docker-compose up -d --build`
- [ ] `docker-compose exec bot alembic upgrade head`
- [ ] Все сервисы запущены (docker-compose ps)
- [ ] Тестовая регистрация прошла
- [ ] Новые вопросы работают
- [ ] `/stats` показывает статистику
- [ ] Flower доступен (localhost:5555)

---

## 🎯 Что дальше?

### Перед мероприятием:

1. **Настройте шаблон билета** (ticket_template.png)
2. **Протестируйте полный цикл**:
   - Регистрация
   - Генерация (проверьте tickets/)
   - Рассылка (/rass)
3. **Настройте мониторинг** (Flower)
4. **Создайте резервные копии БД**

### Во время регистрации:

1. **Следите за статистикой**: `/stats`
2. **Проверяйте билеты**: `/check_tickets`
3. **Мониторьте Celery**: http://localhost:5555
4. **Логи**: `docker-compose logs -f bot celery_worker`

### После регистрации:

1. **Проверьте билеты** в папке `tickets/`
2. **Запустите рассылку**: `/rass`
3. **Следите за прогрессом** в Flower

---

## 🆘 Нужна помощь?

1. Проверьте [TICKET_SUMMARY.md](TICKET_SUMMARY.md)
2. Проверьте [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
3. Посмотрите логи: `docker-compose logs bot`
4. Создайте issue

---

**Всё готово! Начинайте с Шага 1 - дополните .env файл! 🚀**

