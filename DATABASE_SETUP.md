# 🗄️ Настройка базы данных

## Методы инициализации

Есть **3 способа** инициализации базы данных. Выберите тот, который вам удобнее.

---

## 1️⃣ Автоматическая инициализация при запуске

**Самый простой способ!** База данных инициализируется автоматически при старте бота.

```bash
python main.py
```

При запуске бот:
- ✅ Проверяет подключение к БД
- ✅ Создает таблицы если их нет
- ✅ Инициализирует конфигурацию регистрации
- ✅ Запускается и начинает работать

**Преимущества:**
- Не нужно ничего делать вручную
- Работает из коробки
- Идеально для разработки и тестирования

---

## 2️⃣ Ручная инициализация скриптом

Запустите скрипт инициализации перед стартом бота:

```bash
python init_database.py
```

**Что делает скрипт:**
```
====================================================
🚀 DATABASE INITIALIZATION SCRIPT
====================================================
🔄 Initializing database...
✅ Database connection successful
✅ Database tables created/verified
✅ Registration config initialized: 3500 seats

====================================================
📋 Verifying database setup...

✅ Table 'surveys': 0 records
✅ Table 'registration_config':
   - Max capacity: 3500
   - Current count: 0
   - Is open: 🟢 Yes

====================================================
✅ DATABASE SETUP COMPLETE!

Next steps:
  1. Start the bot: python main.py
  2. Or use Docker: docker-compose up -d
====================================================
```

**Преимущества:**
- Проверяет корректность настроек
- Показывает детальную информацию
- Можно запустить отдельно от бота
- Идеально перед деплоем в продакшен

**Использование в Docker:**
```bash
docker-compose exec bot python init_database.py
```

---

## 3️⃣ Alembic миграции (профессиональный подход)

Используйте Alembic для версионированных миграций:

```bash
alembic upgrade head
```

**Что это дает:**
- 📚 История всех изменений БД
- 🔄 Возможность откатить изменения (`downgrade`)
- 🎯 Контроль версий схемы БД
- 👥 Удобно для команды разработчиков

**Создание новой миграции:**
```bash
alembic revision -m "add new field"
```

**Просмотр истории миграций:**
```bash
alembic history
```

**Откат последней миграции:**
```bash
alembic downgrade -1
```

**Использование в Docker:**
```bash
docker-compose exec bot alembic upgrade head
```

---

## 🆚 Какой метод выбрать?

| Ситуация | Рекомендация |
|----------|--------------|
| 🚀 Быстрое тестирование | Метод 1 (автоматически) |
| 🔧 Первый запуск в продакшене | Метод 2 (скрипт) |
| 👥 Работа в команде | Метод 3 (Alembic) |
| 🏭 Production с CI/CD | Метод 3 (Alembic) |
| 📚 Нужна история изменений | Метод 3 (Alembic) |

---

## 🔍 Проверка состояния БД

### Через Python:
```python
from db.init_db import verify_setup
import asyncio

asyncio.run(verify_setup())
```

### Через SQL:
```bash
docker-compose exec db psql -U user new_bal_db
```

```sql
-- Проверка таблиц
\dt

-- Количество регистраций
SELECT COUNT(*) FROM surveys;

-- Конфигурация регистрации
SELECT * FROM registration_config;

-- Статистика по типам билетов
SELECT 
    pair_or_single, 
    COUNT(*) as count,
    SUM(CASE WHEN pair_or_single = 'pair' THEN 2 ELSE 1 END) as seats_taken
FROM surveys 
GROUP BY pair_or_single;
```

---

## 🐛 Решение проблем

### Ошибка "relation does not exist"

Таблицы не созданы. Запустите:
```bash
python init_database.py
```

### Ошибка "configuration already exists"

Это нормально! Конфигурация уже создана.

### Таблицы созданы, но регистрация не работает

Проверьте конфигурацию:
```python
from db.registration import get_registration_stats
import asyncio

stats = asyncio.run(get_registration_stats())
print(stats)
```

### База данных не подключается

Проверьте:
1. Запущен ли PostgreSQL: `docker-compose ps db`
2. Правильный ли DATABASE_URL в `.env`
3. Логи: `docker-compose logs db`

---

## 📊 Структура таблиц

### `surveys` - Регистрации пользователей
```sql
CREATE TABLE surveys (
    id SERIAL PRIMARY KEY,
    consent BOOLEAN,
    fio VARCHAR(255),
    group VARCHAR(64),
    student_id VARCHAR(64),
    telegram_id VARCHAR(64) UNIQUE,
    telegram_username VARCHAR(255),
    pair_or_single VARCHAR(16),
    partner_status VARCHAR(32),
    partner_fio VARCHAR(255),
    partner_group VARCHAR(64),
    partner_student_id VARCHAR(64),
    partner_diploma VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX ix_surveys_telegram_id ON surveys(telegram_id);
```

### `registration_config` - Конфигурация регистрации
```sql
CREATE TABLE registration_config (
    id INTEGER PRIMARY KEY,
    max_capacity INTEGER NOT NULL DEFAULT 3500,
    current_count INTEGER NOT NULL DEFAULT 0,
    is_open BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔧 Ручное управление конфигурацией

### Изменить лимит мест:
```sql
UPDATE registration_config 
SET max_capacity = 5000 
WHERE id = 1;
```

### Открыть/закрыть регистрацию:
```sql
-- Закрыть
UPDATE registration_config SET is_open = FALSE WHERE id = 1;

-- Открыть
UPDATE registration_config SET is_open = TRUE WHERE id = 1;
```

### Сбросить счетчик:
```sql
UPDATE registration_config SET current_count = 0 WHERE id = 1;
```

### Пересчитать занятые места:
```sql
UPDATE registration_config 
SET current_count = (
    SELECT COUNT(*) + COUNT(*) FILTER (WHERE pair_or_single = 'pair')
    FROM surveys
)
WHERE id = 1;
```

---

## 🔄 Резервное копирование

### Создание бэкапа:
```bash
# Через Docker
docker-compose exec db pg_dump -U user new_bal_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Локально
pg_dump -h localhost -U user new_bal_db > backup.sql
```

### Восстановление:
```bash
# Через Docker
cat backup.sql | docker-compose exec -T db psql -U user new_bal_db

# Локально
psql -h localhost -U user new_bal_db < backup.sql
```

---

## 📝 Checklist перед продакшеном

- [ ] База данных инициализирована
- [ ] Конфигурация создана (max_capacity, is_open)
- [ ] Индексы созданы (telegram_id)
- [ ] Тестовая регистрация прошла успешно
- [ ] Резервная копия создана
- [ ] Мониторинг настроен
- [ ] Доступ к PgAdmin настроен (опционально)

---

**База данных готова к работе! 🚀**

