# 🪟 Настройка и запуск на Windows

## Быстрый запуск

### Автоматический запуск (PowerShell)

1. **Откройте PowerShell от имени администратора**
2. **Разрешите выполнение скриптов** (если еще не разрешено):
   ```powershell
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
3. **Запустите систему**:
   ```powershell
   .\start_broadcast_system.ps1
   ```

Система автоматически откроет 3 окна:
- 🤖 Telegram Bot
- ⚙️ Celery Workers (3 воркера)
- 🌸 Flower (мониторинг на http://localhost:5555)

### Ручной запуск

Если автоматический скрипт не работает, запускайте компоненты вручную:

#### 1️⃣ Активируйте виртуальное окружение

```powershell
.\venv\Scripts\Activate.ps1
```

#### 2️⃣ В первом окне PowerShell - запустите бота:

```powershell
python main.py
```

#### 3️⃣ Откройте второе окно PowerShell и запустите Celery:

```powershell
cd C:\Users\anato\OneDrive\Рабочий стол\tg_bot_bpl
.\venv\Scripts\Activate.ps1
celery -A tasks worker --loglevel=info --concurrency=3 --pool=solo
```

**⚠️ Важно:** На Windows используйте `--pool=solo`

#### 4️⃣ (Опционально) В третьем окне - запустите Flower:

```powershell
cd C:\Users\anato\OneDrive\Рабочий стол\tg_bot_bpl
.\venv\Scripts\Activate.ps1
celery -A tasks flower
```

Откройте http://localhost:5555 в браузере.

## Установка зависимостей

### Redis для Windows

Redis не поддерживается официально на Windows, но есть порт от Microsoft:

1. **Скачайте Redis:**
   - https://github.com/microsoftarchive/redis/releases
   - Выберите последнюю версию (например, Redis-x64-3.2.100.msi)

2. **Установите Redis:**
   - Запустите .msi файл
   - Следуйте инструкциям установщика
   - ✅ Отметьте "Add to PATH"

3. **Запустите Redis:**
   ```powershell
   redis-server
   ```

4. **Проверьте что Redis работает:**
   ```powershell
   redis-cli ping
   # Должен вернуть: PONG
   ```

### PostgreSQL для Windows

1. **Скачайте PostgreSQL:**
   - https://www.postgresql.org/download/windows/
   - Рекомендуется версия 14 или выше

2. **Установите PostgreSQL:**
   - Запустите установщик
   - Задайте пароль для пользователя `postgres`
   - Порт: 5432 (по умолчанию)

3. **Создайте базу данных:**
   ```powershell
   # Откройте SQL Shell (psql)
   CREATE DATABASE event_bot;
   ```

4. **Обновите .env файл:**
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:ваш_пароль@localhost/event_bot
   ```

### Python и виртуальное окружение

1. **Убедитесь что Python установлен:**
   ```powershell
   python --version
   # Должна быть версия 3.10 или выше
   ```

2. **Создайте виртуальное окружение:**
   ```powershell
   python -m venv venv
   ```

3. **Активируйте окружение:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

4. **Установите зависимости:**
   ```powershell
   pip install -r requirements.txt
   ```

## Настройка переменных окружения (.env)

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot
BOT_TOKEN=ваш_bot_token_от_BotFather
ADMIN_IDS=ваш_telegram_id,другой_admin_id

# Database
DATABASE_URL=postgresql+asyncpg://postgres:пароль@localhost/event_bot

# Redis
REDIS_BROKER_URL=redis://localhost:6379/1

# Ticket Template (опционально)
TICKET_TEMPLATE_PATH=ticket_template.png
```

## Использование массовой рассылки

### Команды в боте

1. **`/broadcast`** - Массовая рассылка
   - Выбери тип (текст/фото)
   - Введи содержимое
   - Подтверди

2. **`/broadcast_test`** - Тестовая рассылка
   ```
   /broadcast_test Привет! Это **тест**.
   ```

3. **`/stats`** - Статистика пользователей

### Мониторинг

- **Flower (Celery):** http://localhost:5555
- **Логи:** `.\bot.log` и вывод в окнах PowerShell

## Решение проблем

### ❌ Redis не запускается

**Проблема:** `redis-server` не найден

**Решение:**
1. Убедитесь что Redis установлен
2. Добавьте Redis в PATH:
   - `C:\Program Files\Redis\` (или где вы установили)
3. Перезапустите PowerShell

### ❌ Celery выдает ошибки на Windows

**Проблема:** `celery worker` падает с ошибкой

**Решение:** Используйте `--pool=solo`:
```powershell
celery -A tasks worker --loglevel=info --concurrency=3 --pool=solo
```

### ❌ PowerShell не запускает скрипты

**Проблема:** "Execution of scripts is disabled"

**Решение:**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### ❌ База данных не подключается

**Проблема:** `Connection refused` или `password authentication failed`

**Решение:**
1. Проверьте что PostgreSQL запущен
2. Проверьте пароль в `.env`
3. Проверьте порт (обычно 5432)
4. В .env используйте:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:пароль@localhost:5432/event_bot
   ```

### ❌ ModuleNotFoundError

**Проблема:** Python не находит модули

**Решение:**
```powershell
# Активируйте venv
.\venv\Scripts\Activate.ps1

# Переустановите зависимости
pip install -r requirements.txt
```

## Структура окон после запуска

После запуска `start_broadcast_system.ps1` откроются окна:

```
┌─────────────────────────────┐
│   🤖 Telegram Bot           │
│   Логи бота                 │
└─────────────────────────────┘

┌─────────────────────────────┐
│   ⚙️ Celery Workers         │
│   Обработка рассылок        │
└─────────────────────────────┘

┌─────────────────────────────┐
│   🌸 Flower                 │
│   Мониторинг задач          │
│   http://localhost:5555     │
└─────────────────────────────┘
```

## Остановка системы

1. **Остановите все окна PowerShell** (Ctrl+C в каждом окне)
2. Или просто закройте окна

## Полезные команды PowerShell

### Проверка процессов

```powershell
# Найти все процессы Python
Get-Process python

# Завершить процесс по имени
Stop-Process -Name python -Force
```

### Очистка

```powershell
# Очистить кэш Python
Remove-Item -Recurse -Force __pycache__
Remove-Item -Recurse -Force .pytest_cache

# Очистить логи
Remove-Item bot.log
```

### Проверка портов

```powershell
# Проверить что слушает порт 5555 (Flower)
netstat -ano | findstr :5555

# Проверить что слушает порт 6379 (Redis)
netstat -ano | findstr :6379
```

## Альтернатива: WSL2

Если у вас Windows 10/11, можете использовать WSL2:

1. **Установите WSL2:**
   ```powershell
   wsl --install
   ```

2. **Установите Ubuntu:**
   ```bash
   wsl --install -d Ubuntu
   ```

3. **В WSL используйте обычные Linux команды:**
   ```bash
   ./start_broadcast_system.sh
   ```

## Документация

- 📚 [BROADCAST_README_RU.md](./BROADCAST_README_RU.md) - Краткая инструкция
- 📖 [BROADCAST_GUIDE.md](./BROADCAST_GUIDE.md) - Полное руководство
- 🚀 [BROADCAST_QUICKSTART.md](./BROADCAST_QUICKSTART.md) - Быстрый старт

## Поддержка

При возникновении проблем:

1. Проверьте логи в окнах PowerShell
2. Проверьте файл `bot.log`
3. Проверьте что все сервисы запущены:
   - Redis: `redis-cli ping`
   - PostgreSQL: через pgAdmin или psql
   - Celery: в окне PowerShell должны быть логи

---

**Готово!** 🎉 Теперь можно использовать `/broadcast` в боте!

