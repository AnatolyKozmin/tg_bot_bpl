# 🔄 Руководство по миграции на новую версию

## 📋 Что изменилось?

### Новые поля в базе данных:
- ✅ `is_student` - является ли студентом
- ✅ `faculty` - факультет обучения
- ✅ `course` - курс обучения
- ✅ `diploma_number` - номер диплома (для выпускников)
- ✅ `ticket_sent` - отправлен ли билет
- ✅ `ticket_cancelled` - отменен ли билет
- ✅ `partner_faculty` - факультет партнера
- ✅ `partner_course` - курс партнера
- ✅ `updated_at` - дата последнего обновления

### Изменения в полях:
- ⚠️ `student_id` - теперь **ровно 6 цифр** (было 64 символа)
- ⚠️ `partner_student_id` - теперь **ровно 6 цифр**

### Новая логика бота:
1. Вопрос о персональных данных **не исчезает** (редактируется с подтверждением)
2. Добавлен вопрос **"Является ли студентом?"**
3. Добавлены поля **Факультет** и **Курс** (кнопками)
4. Валидация студ. билета - **ровно 6 цифр**
5. Группа в кавычках в примере: `"ПИ23-1"`
6. Возможность **редактировать анкету** после отправки
7. Возможность **отменить билет** с предупреждением

---

## 🚀 Процесс миграции

### ⚠️ ВАЖНО: Создайте бэкап!

```bash
# Создайте бэкап базы данных
docker-compose exec db pg_dump -U user new_bal_db > backup_before_migration_$(date +%Y%m%d_%H%M%S).sql

# Или если БД локальная
pg_dump -h localhost -U user new_bal_db > backup_before_migration.sql
```

### Шаг 1: Обновите код

```bash
# Убедитесь что у вас последняя версия
git pull  # или скачайте новые файлы
```

### Шаг 2: Примените миграцию

#### Вариант A: Через Alembic (рекомендуется)

```bash
# Остановите бота
docker-compose stop bot

# Примените миграцию
docker-compose exec db bash
alembic upgrade head

# Или локально
alembic upgrade head
```

#### Вариант B: Вручную через SQL

```bash
docker-compose exec db psql -U user new_bal_db
```

```sql
-- Добавляем новые поля
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS is_student BOOLEAN;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS faculty VARCHAR(64);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS course VARCHAR(32);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS diploma_number VARCHAR(64);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS ticket_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS ticket_cancelled BOOLEAN DEFAULT FALSE;
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS partner_faculty VARCHAR(64);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS partner_course VARCHAR(32);
ALTER TABLE surveys ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Изменяем длину поля student_id (если есть длинные значения, они обрежутся!)
ALTER TABLE surveys ALTER COLUMN student_id TYPE VARCHAR(6);
ALTER TABLE surveys ALTER COLUMN partner_student_id TYPE VARCHAR(6);

-- Для существующих записей устанавливаем is_student=TRUE если есть student_id
UPDATE surveys 
SET is_student = TRUE 
WHERE student_id IS NOT NULL AND student_id != '';

-- Выход
\q
```

### Шаг 3: Проверьте миграцию

```bash
docker-compose exec db psql -U user new_bal_db
```

```sql
-- Проверьте структуру таблицы
\d surveys

-- Проверьте что данные сохранились
SELECT COUNT(*) FROM surveys;
SELECT COUNT(*) FROM surveys WHERE is_student IS NOT NULL;
```

### Шаг 4: Запустите бота

```bash
# Перезапустите все сервисы
docker-compose down
docker-compose up -d --build

# Проверьте логи
docker-compose logs -f bot
```

---

## 🔍 Проверка работоспособности

### 1. Проверьте что бот запустился

```bash
docker-compose ps
```

Должно быть:
```
NAME       STATUS
bot        Up
db         Up
redis      Up
```

### 2. Протестируйте регистрацию

1. Напишите боту `/start`
2. Пройдите полный цикл регистрации
3. Проверьте новые вопросы:
   - Является ли студентом?
   - Факультет
   - Курс обучения

### 3. Проверьте старые регистрации

```bash
docker-compose exec db psql -U user new_bal_db
```

```sql
-- Посмотрите на существующие записи
SELECT id, fio, is_student, faculty, course FROM surveys LIMIT 5;

-- Должны быть:
-- - Старые записи с is_student=TRUE (если был student_id)
-- - faculty и course = NULL (для старых записей - это норм)
```

### 4. Проверьте управление билетом

Для пользователя который уже зарегистрирован:
1. Напишите `/start`
2. Должна появиться кнопка "✏️ Редактировать анкету"
3. Должна появиться кнопка "❌ Отменить билет"

---

## 🐛 Возможные проблемы

### Проблема 1: Миграция не применяется

**Симптомы:**
```
ERROR: column "is_student" does not exist
```

**Решение:**
```bash
# Проверьте версию миграции
docker-compose exec bot alembic current

# Должно быть: 0003

# Если нет, примените миграцию
docker-compose exec bot alembic upgrade head
```

### Проблема 2: Студенческие билеты длиннее 6 символов

**Симптомы:**
```
ERROR: value too long for type character varying(6)
```

**Решение:**
```sql
-- Найдите проблемные записи
SELECT id, fio, student_id, LENGTH(student_id) as len 
FROM surveys 
WHERE LENGTH(student_id) > 6;

-- Обрежьте или исправьте вручную
UPDATE surveys 
SET student_id = RIGHT(student_id, 6)  -- Берем последние 6 цифр
WHERE LENGTH(student_id) > 6;

-- Или удалите невалидные
UPDATE surveys 
SET student_id = NULL 
WHERE LENGTH(student_id) > 6;
```

### Проблема 3: Бот не отвечает

**Симптомы:**
Бот не реагирует на сообщения

**Решение:**
```bash
# Проверьте логи
docker-compose logs --tail=50 bot

# Перезапустите
docker-compose restart bot

# Проверьте Redis
docker-compose exec redis redis-cli ping
```

### Проблема 4: Бесконечная загрузка на кнопке

**Симптомы:**
Кнопка крутится бесконечно

**Решение:**
Это было исправлено! Теперь все callback queries отвечают.

Если проблема осталась:
```bash
# Обновите handlers.py
docker-compose down
docker-compose up -d --build
```

---

## 🔙 Откат миграции (если что-то пошло не так)

### Шаг 1: Остановите бота

```bash
docker-compose down
```

### Шаг 2: Восстановите бэкап

```bash
# Удалите текущую БД (ОСТОРОЖНО!)
docker-compose exec db psql -U user -c "DROP DATABASE new_bal_db;"
docker-compose exec db psql -U user -c "CREATE DATABASE new_bal_db;"

# Восстановите бэкап
cat backup_before_migration.sql | docker-compose exec -T db psql -U user new_bal_db
```

### Шаг 3: Откатите код

```bash
# Используйте старую версию handlers
cp bot/handlers_old_backup.py bot/handlers.py

# Откатите миграцию Alembic
alembic downgrade -1  # на одну версию назад
# или
alembic downgrade 0002  # до конкретной версии
```

### Шаг 4: Запустите старую версию

```bash
docker-compose up -d
```

---

## 📊 Статистика после миграции

```sql
-- Общая статистика
SELECT 
    COUNT(*) as total,
    COUNT(CASE WHEN is_student = TRUE THEN 1 END) as students,
    COUNT(CASE WHEN is_student = FALSE THEN 1 END) as graduates,
    COUNT(CASE WHEN faculty IS NOT NULL THEN 1 END) as with_faculty,
    COUNT(CASE WHEN ticket_cancelled = TRUE THEN 1 END) as cancelled
FROM surveys;

-- Распределение по факультетам
SELECT faculty, COUNT(*) as count
FROM surveys
WHERE faculty IS NOT NULL
GROUP BY faculty
ORDER BY count DESC;

-- Распределение по курсам
SELECT course, COUNT(*) as count
FROM surveys
WHERE course IS NOT NULL
GROUP BY course
ORDER BY count DESC;
```

---

## ✅ Checklist после миграции

- [ ] Бэкап создан
- [ ] Миграция применена успешно
- [ ] Все сервисы запущены
- [ ] Бот отвечает на /start
- [ ] Новые вопросы работают
- [ ] Старые регистрации сохранились
- [ ] Редактирование билета работает
- [ ] Отмена билета работает
- [ ] Валидация 6 цифр работает
- [ ] Логи проверены
- [ ] Тестовая регистрация прошла

---

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте логи: `docker-compose logs bot`
2. Проверьте БД: `docker-compose exec db psql -U user new_bal_db`
3. Восстановите бэкап если нужно
4. Создайте issue с описанием проблемы

---

**Успешной миграции! 🚀**

