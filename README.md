# 🎫 High-Load Event Registration Bot

Высоконагруженный Telegram бот для регистрации на большие мероприятия с автоматической рассылкой билетов.

## ✨ Ключевые возможности

- ⚡ **Высокая производительность**: Обработка до 1000 регистраций за 30 секунд
- 🔒 **Атомарный счетчик мест**: Гарантированное ограничение 3500 участников
- 🛡️ **Защита от флуда**: Rate limiting и anti-flood middleware
- 🎫 **Умная система билетов**: 
  - Генерация после регистрации (фоном, не блокирует)
  - Хранение на сервере до рассылки
  - Рассылка по команде `/rass`
  - Отмена с уведомлением незавершенных регистраций
- 📨 **Массовая рассылка билетов**: Асинхронная отправка 3500+ билетов за 3 минуты
- 📢 **Массовая рассылка объявлений**: 
  - Текстовые сообщения с Markdown форматированием
  - Фото с подписью
  - Интерактивный интерфейс с предпросмотром
  - Автоматическое соблюдение лимитов Telegram API (18 сообщений/сек)
  - Мониторинг прогресса в реальном времени
- ⏱️ **Полное отслеживание**: Время начала, завершения, генерации, отправки, отмены
- 🔄 **Redis storage**: Состояния не теряются при перезапуске
- 📊 **Мониторинг**: Веб-интерфейсы для Celery (Flower) и PostgreSQL (PgAdmin)
- 🚀 **Масштабируемость**: До 5 инстансов бота одновременно

## 🏗 Архитектура

```
Telegram Bot (1-5 инстансов)
    │
    ├─► Redis (FSM + Celery broker)
    ├─► PostgreSQL (connection pool: 50+100)
    └─► Celery Workers (5 concurrent tasks)
```

## 🚀 Быстрый старт

### Вариант 1: Docker (рекомендуется)

```bash
# 1. Настройте переменные окружения
cp env.example .env
nano .env  # Добавьте BOT_TOKEN и ADMIN_IDS

# 2. Запустите все сервисы
docker-compose up -d --build

# 3. Инициализируйте базу данных (выберите один вариант)
# Вариант A: Автоматическая инициализация (рекомендуется)
docker-compose exec bot python init_database.py

# Вариант B: Через Alembic миграции
docker-compose exec bot alembic upgrade head

# 4. Создайте тестовый шаблон билета
docker-compose exec bot python create_test_template.py
```

Готово! Бот запущен и готов к работе.

### Вариант 2: Локальная установка

```bash
# 1. Установите зависимости
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Запустите Redis и PostgreSQL
docker-compose up -d redis db

# 3. Настройте .env
cp env.example .env
# Отредактируйте .env

# 4. Инициализируйте базу данных
python init_database.py
# Или через Alembic: alembic upgrade head

# 5. Запустите бота
python main.py
# БД инициализируется автоматически при старте если это не было сделано

# 6. В отдельном терминале запустите Celery
celery -A tasks worker --loglevel=info --concurrency=5
```

## 📋 Требования

- Docker 20.10+ и Docker Compose 2.0+
- **ИЛИ** Python 3.11+, Redis, PostgreSQL

### Рекомендуемые ресурсы сервера:
- CPU: 4-6 ядер
- RAM: 8 GB
- Disk: 20 GB SSD
- Сеть: 100 Мбит/с

## 🎯 Основные функции

### Для пользователей:
- `/start` - Начать регистрацию
- Поддержка сольных и парных билетов
- Валидация данных в реальном времени:
  - Студенческий билет - **ровно 6 цифр**
  - ФИО без цифр
  - Обязательные поля
- Выбор факультета и курса кнопками
- ✏️ **Редактирование анкеты** после отправки
- ❌ **Отмена билета** (с предупреждением о невозможности повторной регистрации)

### Для администраторов:
- `/stats` - Статистика регистрации (занято мест, процент заполнения)
- `/rass` - Запуск рассылки билетов (только сгенерированные и неотправленные)
- `/broadcast` - 📢 Массовая рассылка объявлений всем участникам (текст/фото)
- `/broadcast_test` - Тестовая отправка сообщения (только админу)
- `/tickets_status` - Статус генерации и рассылки билетов
- `/generate_tickets` - Запуск генерации всех билетов
- `/create_google_shit` - Экспорт данных в Google Sheets

### Новый порядок вопросов:
1. Согласие на обработку персональных данных
2. Является ли студентом / выпускником
3. ФИО
4. Факультет (9 вариантов + Другое)
5. Курс обучения (4 бакалавриат + 2 магистратура)
6. Группа
7. Номер студенческого (6 цифр) или диплома
8. В паре или один
9. Для пары - аналогично пп. 2-7

## 🎫 Настройка билетов

1. Создайте шаблон билета (1200x600 px):
   ```bash
   python create_test_template.py
   ```

2. Или используйте свой дизайн:
   - Разместите файл `ticket_template.png` в корне проекта
   - QR-код будет добавлен автоматически в позицию (900, 300)

## 📊 Мониторинг

После запуска доступны веб-интерфейсы:

- **Celery Flower**: http://localhost:5555 (мониторинг рассылки)
- **PgAdmin**: http://localhost:8080 (управление БД)
- **Логи**: `docker-compose logs -f bot`

## 🔧 Настройка лимита мест

По умолчанию: **3500 мест**

Изменить можно двумя способами:

1. **В коде** (`db/models.py`):
   ```python
   max_capacity = Column(Integer, default=5000)
   ```

2. **В базе данных**:
   ```sql
   UPDATE registration_config SET max_capacity = 5000 WHERE id = 1;
   ```

## 📚 Документация

### Начало работы:
- [QUICKSTART.md](QUICKSTART.md) - Быстрый старт за 5 минут
- [DATABASE_SETUP.md](DATABASE_SETUP.md) - Инициализация и настройка БД
- [env.example](env.example) - Пример переменных окружения

### Миграция и обновление:
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - Миграция на новую версию
- [CHANGELOG.md](CHANGELOG.md) - История изменений
- [SUMMARY.md](SUMMARY.md) - Итоговая сводка изменений

### Система билетов:
- [TICKET_SYSTEM.md](TICKET_SYSTEM.md) - Полная документация системы билетов
- [TICKET_SUMMARY.md](TICKET_SUMMARY.md) - Краткая сводка

### Массовая рассылка:
- [BROADCAST_QUICKSTART.md](BROADCAST_QUICKSTART.md) - 📢 Быстрый старт рассылки
- [BROADCAST_GUIDE.md](BROADCAST_GUIDE.md) - Полное руководство по рассылке

### Production:
- [DEPLOYMENT.md](DEPLOYMENT.md) - Полное руководство по развертыванию
- [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md) - Настройка Webhook для масштабирования
- [OPTIMIZATION.md](OPTIMIZATION.md) - Оптимизация для production

## 🛠 Технологический стек

- **Bot Framework**: aiogram 3.x
- **Database**: PostgreSQL 16 + SQLAlchemy (async)
- **Cache/Queue**: Redis 7
- **Task Queue**: Celery
- **Image Processing**: Pillow, qrcode
- **Migrations**: Alembic
- **Containerization**: Docker, Docker Compose

## 📈 Производительность

Тестовые показатели:
- ⚡ **1000 регистраций** за 30 секунд
- 📨 **3500 билетов** рассылаются за ~3-5 минут
- 🔒 **0% race conditions** благодаря атомарному счетчику
- 💾 **Connection pool**: 50 базовых + 100 overflow

## 🔐 Безопасность

- Rate limiting: 5 сообщений/сек на пользователя
- Anti-flood: блокировка при 20 сообщениях/минуту
- Атомарные транзакции с `SELECT FOR UPDATE`
- Валидация всех входных данных
- Защита команд администратора

## 🐛 Решение проблем

```bash
# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f bot

# Перезапуск
docker-compose restart bot

# Полная остановка и очистка
docker-compose down -v
```

## 📝 Переменные окружения

Создайте файл `.env` на основе `env.example`:

```env
# Обязательные
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=123456789,987654321

# Опциональные (есть значения по умолчанию)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/new_bal_db
REDIS_URL=redis://localhost:6379/0
REDIS_BROKER_URL=redis://localhost:6379/1
```

## 🤝 Контрибьюция

Pull requests приветствуются! Для больших изменений сначала откройте issue.

## 📄 Лицензия

MIT License - см. файл LICENSE

## 🆘 Поддержка

При возникновении проблем:
1. Проверьте [DEPLOYMENT.md](DEPLOYMENT.md)
2. Просмотрите логи: `docker-compose logs`
3. Создайте issue с описанием проблемы

---

**Готово к обработке высокой нагрузки! 🚀**
