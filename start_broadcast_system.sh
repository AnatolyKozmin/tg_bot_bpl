#!/bin/bash

# 📢 Скрипт запуска системы массовой рассылки
# Запускает все необходимые компоненты в tmux

set -e

echo "🚀 Запуск системы массовой рассылки..."

# Проверка что tmux установлен
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux не установлен. Установите: sudo apt install tmux"
    exit 1
fi

# Проверка .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден. Создайте из env.example"
    exit 1
fi

# Проверка Redis
echo "📡 Проверка Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis не запущен. Запустите: sudo systemctl start redis"
    exit 1
fi
echo "✅ Redis работает"

# Проверка виртуального окружения
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment не найден. Создаем..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi
echo "✅ Virtual environment активирован"

# Название tmux сессии
SESSION_NAME="broadcast_bot"

# Проверка существующей сессии
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo "⚠️  Сессия $SESSION_NAME уже существует."
    read -p "Завершить и создать новую? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        tmux kill-session -t $SESSION_NAME
    else
        echo "Подключение к существующей сессии..."
        tmux attach-session -t $SESSION_NAME
        exit 0
    fi
fi

# Создание новой tmux сессии
echo "🎬 Создание tmux сессии: $SESSION_NAME"

# Создаем сессию и первое окно (Bot)
tmux new-session -d -s $SESSION_NAME -n "Bot"

# Окно 1: Telegram Bot
tmux send-keys -t $SESSION_NAME:0 "cd $(pwd)" C-m
tmux send-keys -t $SESSION_NAME:0 "source venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME:0 "clear" C-m
tmux send-keys -t $SESSION_NAME:0 "echo '🤖 Telegram Bot'" C-m
tmux send-keys -t $SESSION_NAME:0 "python main.py" C-m

# Окно 2: Celery Workers
tmux new-window -t $SESSION_NAME:1 -n "Celery"
tmux send-keys -t $SESSION_NAME:1 "cd $(pwd)" C-m
tmux send-keys -t $SESSION_NAME:1 "source venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME:1 "clear" C-m
tmux send-keys -t $SESSION_NAME:1 "echo '⚙️  Celery Workers (3 workers)'" C-m
tmux send-keys -t $SESSION_NAME:1 "celery -A tasks worker --loglevel=info --concurrency=3" C-m

# Окно 3: Flower (мониторинг Celery)
tmux new-window -t $SESSION_NAME:2 -n "Flower"
tmux send-keys -t $SESSION_NAME:2 "cd $(pwd)" C-m
tmux send-keys -t $SESSION_NAME:2 "source venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME:2 "clear" C-m
tmux send-keys -t $SESSION_NAME:2 "echo '🌸 Flower (Celery Monitor)'" C-m
tmux send-keys -t $SESSION_NAME:2 "echo 'URL: http://localhost:5555'" C-m
tmux send-keys -t $SESSION_NAME:2 "sleep 3" C-m
tmux send-keys -t $SESSION_NAME:2 "celery -A tasks flower" C-m

# Окно 4: Логи
tmux new-window -t $SESSION_NAME:3 -n "Logs"
tmux send-keys -t $SESSION_NAME:3 "cd $(pwd)" C-m
tmux send-keys -t $SESSION_NAME:3 "clear" C-m
tmux send-keys -t $SESSION_NAME:3 "echo '📋 Логи (обновляются автоматически)'" C-m
tmux send-keys -t $SESSION_NAME:3 "echo ''" C-m
tmux send-keys -t $SESSION_NAME:3 "tail -f bot.log 2>/dev/null || echo 'Ожидание логов...'" C-m

# Выбираем первое окно
tmux select-window -t $SESSION_NAME:0

echo ""
echo "✅ Система запущена в tmux сессии: $SESSION_NAME"
echo ""
echo "📊 Доступные окна:"
echo "  0: Bot       - Telegram бот"
echo "  1: Celery    - Celery воркеры (3 воркера)"
echo "  2: Flower    - Мониторинг Celery (http://localhost:5555)"
echo "  3: Logs      - Логи бота"
echo ""
echo "🔧 Управление tmux:"
echo "  Ctrl+B, 0-3  - Переключение между окнами"
echo "  Ctrl+B, D    - Отключиться (система продолжит работу)"
echo "  Ctrl+B, X    - Закрыть текущее окно"
echo "  Ctrl+B, &    - Закрыть окно с подтверждением"
echo ""
echo "📱 Telegram команды:"
echo "  /broadcast       - Массовая рассылка"
echo "  /broadcast_test  - Тестовая рассылка"
echo "  /stats           - Статистика"
echo ""

# Подключаемся к сессии
sleep 2
tmux attach-session -t $SESSION_NAME

