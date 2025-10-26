# 📝 Changelog - Все изменения

## 🎉 Версия 2.0 - Большое обновление (26.10.2025)

### ✨ Новые возможности

#### Для пользователей:

1. **Новый порядок регистрации**
   - Вопрос "Является ли студентом?" (до ФИО)
   - Выбор факультета кнопками (9 вариантов + Другое)
   - Выбор курса кнопками (4 бакалавриат + 2 магистратура)
   - Группа теперь в кавычках в примере: `"ПИ23-1"`

2. **Улучшенная валидация**
   - Студенческий билет - **строго 6 цифр** (было до 64 символов)
   - ФИО без цифр
   - Номер диплома для выпускников - только цифры

3. **Управление билетом**
   - ✏️ **Редактирование анкеты** после отправки
   - ❌ **Отмена билета** с предупреждением
   - При повторном `/start` - показывается меню управления билетом

4. **Улучшенный UX**
   - Вопрос о персональных данных **не исчезает**, а редактируется с галочкой
   - Все выборы отображаются с подтверждением
   - Исправлена бесконечная загрузка кнопок
   - Эмодзи для лучшей визуализации

#### Для администраторов:

1. **Webhook поддержка**
   - Файл `main_webhook.py` для масштабирования
   - Поддержка нескольких инстансов бота
   - Health check endpoint: `/health`

2. **Улучшенные команды**
   - `/stats` - расширенная статистика
   - `/rass` - рассылка с учетом отмененных билетов

### 🗄️ Изменения в базе данных

#### Новые поля:
```sql
ALTER TABLE surveys ADD COLUMN is_student BOOLEAN;           -- Студент/выпускник
ALTER TABLE surveys ADD COLUMN faculty VARCHAR(64);          -- Факультет
ALTER TABLE surveys ADD COLUMN course VARCHAR(32);           -- Курс
ALTER TABLE surveys ADD COLUMN diploma_number VARCHAR(64);   -- Номер диплома
ALTER TABLE surveys ADD COLUMN ticket_sent BOOLEAN;          -- Билет отправлен?
ALTER TABLE surveys ADD COLUMN ticket_cancelled BOOLEAN;     -- Билет отменен?
ALTER TABLE surveys ADD COLUMN partner_faculty VARCHAR(64);  -- Факультет партнера
ALTER TABLE surveys ADD COLUMN partner_course VARCHAR(32);   -- Курс партнера
ALTER TABLE surveys ADD COLUMN updated_at TIMESTAMP;         -- Дата обновления
```

#### Изменения полей:
```sql
-- Студенческий билет: было 64 символа → стало 6 символов
ALTER TABLE surveys ALTER COLUMN student_id TYPE VARCHAR(6);
ALTER TABLE surveys ALTER COLUMN partner_student_id TYPE VARCHAR(6);
```

### 📦 Новые файлы

#### Основные:
- `bot/handlers_new.py` → `bot/handlers.py` - полностью переписанная логика
- `bot/handlers_old_backup.py` - бэкап старой версии
- `main_webhook.py` - версия с webhook

#### Миграции:
- `alembic/versions/0003_add_new_fields.py` - миграция БД с сохранением данных

#### Документация:
- `MIGRATION_GUIDE.md` - руководство по миграции
- `WEBHOOK_SETUP.md` - настройка webhook
- `CHANGELOG.md` - список изменений (этот файл)

### 🔧 Технические улучшения

1. **Клавиатуры** (`bot/keyboards.py`):
   - `is_student_kb()` - выбор статуса студент/выпускник
   - `faculty_kb()` - выбор факультета
   - `course_kb()` - выбор курса
   - `manage_ticket_kb()` - управление билетом
   - `confirm_cancel_kb()` - подтверждение отмены

2. **Модели** (`db/models.py`):
   - Добавлено 9 новых полей
   - Изменен тип для student_id
   - Добавлен updated_at с автообновлением

3. **Обработчики** (`bot/handlers.py`):
   - Новые state для факультета и курса
   - Обработчики редактирования билета
   - Обработчик отмены билета
   - Улучшенная валидация
   - Исправлена бесконечная загрузка

### 🐛 Исправленные баги

1. ✅ Бесконечная загрузка у кнопки ФИО (не отвечали на callback query)
2. ✅ Сообщение о согласии исчезало (теперь редактируется)
3. ✅ Нет возможности редактировать анкету (добавлена)
4. ✅ Нет возможности отменить билет (добавлена)
5. ✅ Слабая валидация студенческого билета (теперь ровно 6 цифр)

### 🚀 Производительность

Без изменений - архитектура уже была оптимизирована:
- Connection pool: 50+100
- Redis для FSM
- Celery для рассылки
- Rate limiting и anti-flood

---

## 📋 Как обновиться

### Для новых установок:
```bash
git clone <repo>
cd tg_bot_bpl
cp env.example .env
# Настройте .env
docker-compose up -d --build
docker-compose exec bot python init_database.py
```

### Для существующих установок:
```bash
# 1. СОЗДАЙТЕ БЭКАП!
docker-compose exec db pg_dump -U user new_bal_db > backup.sql

# 2. Обновите код
git pull

# 3. Примените миграцию
docker-compose exec bot alembic upgrade head

# 4. Перезапустите
docker-compose down
docker-compose up -d --build
```

**📖 Подробнее:** [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

---

## ⚠️ Breaking Changes

1. **Студенческий билет теперь 6 цифр**
   - Если у вас были записи с более длинными номерами, они будут обрезаны
   - См. MIGRATION_GUIDE.md для решения

2. **Новый порядок вопросов**
   - Старые пользователи увидят новые вопросы при редактировании

3. **Handlers полностью переписан**
   - Если вы вносили свои изменения в `bot/handlers.py`, их придется перенести

---

## 🔮 Планы на будущее

### v2.1 (скоро):
- [ ] Статистика по факультетам в `/stats`
- [ ] Экспорт в Excel для админов
- [ ] Отправка билетов автоматически после регистрации
- [ ] Уведомления админам при достижении 90% заполненности

### v2.2:
- [ ] Многоязычность (RU/EN)
- [ ] Telegram Mini App интерфейс
- [ ] QR-сканер для проверки билетов на входе

### v3.0:
- [ ] Микросервисная архитектура
- [ ] Kubernetes deployment
- [ ] GraphQL API
- [ ] Real-time dashboard

---

## 🙏 Благодарности

Спасибо всем кто тестировал и давал feedback!

---

## 📞 Поддержка

Проблемы? Вопросы?

1. Проверьте [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
2. Посмотрите логи: `docker-compose logs bot`
3. Создайте issue на GitHub

---

**Версия:** 2.0.0  
**Дата:** 26 октября 2025  
**Совместимость:** Требует миграция БД  
**Python:** 3.11+  
**Dependencies:** См. requirements.txt

