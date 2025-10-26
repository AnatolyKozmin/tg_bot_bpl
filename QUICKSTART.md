# ⚡ Быстрый старт за 5 минут

## Шаг 1: Создайте .env файл

```bash
cp env.example .env
```

Отредактируйте `.env` и заполните:

```env
# Получите токен от @BotFather в Telegram
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Ваш Telegram ID (узнайте через @userinfobot)
ADMIN_IDS=123456789
```

## Шаг 2: Запустите Docker

```bash
docker-compose up -d --build
```

## Шаг 3: Инициализируйте базу данных

Есть два варианта:

**Вариант A (быстрый):**
```bash
docker-compose exec bot python init_database.py
```

**Вариант B (через Alembic миграции):**
```bash
docker-compose exec bot alembic upgrade head
```

Оба варианта создают таблицы и настраивают систему.

## Шаг 4: Проверьте работу

```bash
# Проверьте статус всех сервисов
docker-compose ps

# Все должны быть "Up" или "healthy"
```

## Шаг 5: Тестируйте бота

1. Откройте Telegram
2. Напишите боту `/start`
3. Пройдите регистрацию

## Команды администратора

- `/stats` - Статистика регистрации
- `/rass` - Запустить рассылку билетов

## 🎫 Настройка шаблона билета

1. Создайте изображение 1200x600 px
2. Сохраните как `ticket_template.png` в корне проекта
3. QR-код будет автоматически добавлен в позицию (900, 300)

## Полезные команды Docker

```bash
# Просмотр логов
docker-compose logs -f bot

# Перезапуск бота
docker-compose restart bot

# Остановка всех сервисов
docker-compose down

# Остановка с удалением данных
docker-compose down -v
```

## Структура проекта

```
tg_bot_bpl/
├── bot/
│   ├── handlers.py      # Обработчики команд
│   ├── keyboards.py     # Клавиатуры
│   ├── middleware.py    # Rate limiting
│   └── sender.py        # Отправка билетов
├── db/
│   ├── models.py        # Модели БД
│   ├── session.py       # Подключение к БД
│   └── registration.py  # Атомарная регистрация
├── tasks.py             # Celery задачи
├── main.py              # Точка входа
└── docker-compose.yml   # Docker конфигурация
```

## 🚀 Готово!

Для детальной информации смотрите [DEPLOYMENT.md](DEPLOYMENT.md)

## Возникли проблемы?

1. Проверьте логи: `docker-compose logs bot`
2. Убедитесь что BOT_TOKEN правильный
3. Проверьте что все сервисы запущены: `docker-compose ps`
4. Перезапустите: `docker-compose restart`

---

**Важно:** Перед запуском мероприятия обязательно:
- ✅ Протестируйте полный цикл регистрации
- ✅ Проверьте шаблон билета
- ✅ Настройте лимит мест (по умолчанию 3500)
- ✅ Добавьте свой ADMIN_ID в .env

