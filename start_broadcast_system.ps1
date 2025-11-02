# 📢 PowerShell скрипт запуска системы массовой рассылки для Windows
# Запускает все необходимые компоненты в отдельных окнах

Write-Host "🚀 Запуск системы массовой рассылки..." -ForegroundColor Green

# Проверка .env файла
if (-Not (Test-Path ".env")) {
    Write-Host "❌ Файл .env не найден. Создайте из env.example" -ForegroundColor Red
    exit 1
}

# Проверка виртуального окружения
if (-Not (Test-Path "venv")) {
    Write-Host "⚠️  Virtual environment не найден. Создаем..." -ForegroundColor Yellow
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
}

Write-Host "✅ Virtual environment готов" -ForegroundColor Green

# Проверка Redis
Write-Host "📡 Проверяя Redis..." -ForegroundColor Cyan
try {
    $redisCheck = redis-cli ping 2>&1
    if ($redisCheck -match "PONG") {
        Write-Host "✅ Redis работает" -ForegroundColor Green
    } else {
        Write-Host "❌ Redis не отвечает. Убедитесь что он запущен." -ForegroundColor Red
        Write-Host "   Скачайте Redis для Windows: https://github.com/microsoftarchive/redis/releases" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ Redis не установлен или не запущен" -ForegroundColor Red
    Write-Host "   Скачайте Redis для Windows: https://github.com/microsoftarchive/redis/releases" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "🎬 Запуск компонентов системы..." -ForegroundColor Green
Write-Host ""

# Получаем текущую директорию
$currentDir = Get-Location

# 1. Запуск Telegram Bot
Write-Host "🤖 Запуск Telegram Bot..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$currentDir'; .\venv\Scripts\Activate.ps1; Write-Host '🤖 Telegram Bot' -ForegroundColor Green; python main.py"
) -WindowStyle Normal

Start-Sleep -Seconds 2

# 2. Запуск Celery Workers
Write-Host "⚙️  Запуск Celery Workers (3 workers)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$currentDir'; .\venv\Scripts\Activate.ps1; Write-Host '⚙️  Celery Workers' -ForegroundColor Green; celery -A tasks worker --loglevel=info --concurrency=3 --pool=solo"
) -WindowStyle Normal

Start-Sleep -Seconds 2

# 3. Запуск Flower (мониторинг)
Write-Host "🌸 Запуск Flower (Celery Monitor)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$currentDir'; .\venv\Scripts\Activate.ps1; Write-Host '🌸 Flower - Celery Monitor' -ForegroundColor Green; Write-Host 'URL: http://localhost:5555' -ForegroundColor Yellow; Start-Sleep -Seconds 3; celery -A tasks flower"
) -WindowStyle Normal

Write-Host ""
Write-Host "✅ Все компоненты запущены!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Открытые окна:" -ForegroundColor Cyan
Write-Host "  • Telegram Bot      - Главный бот" -ForegroundColor White
Write-Host "  • Celery Workers    - 3 воркера для рассылки" -ForegroundColor White
Write-Host "  • Flower            - Мониторинг (http://localhost:5555)" -ForegroundColor White
Write-Host ""
Write-Host "📱 Доступные команды в боте:" -ForegroundColor Cyan
Write-Host "  /broadcast       - 📢 Массовая рассылка" -ForegroundColor White
Write-Host "  /broadcast_test  - 🧪 Тестовая рассылка" -ForegroundColor White
Write-Host "  /stats           - 📊 Статистика" -ForegroundColor White
Write-Host ""
Write-Host "🛑 Для остановки:" -ForegroundColor Yellow
Write-Host "  Закройте все окна PowerShell" -ForegroundColor White
Write-Host ""
Write-Host "📚 Документация:" -ForegroundColor Cyan
Write-Host "  BROADCAST_README_RU.md   - Краткая инструкция" -ForegroundColor White
Write-Host "  BROADCAST_GUIDE.md       - Полное руководство" -ForegroundColor White
Write-Host ""

# Ожидание перед закрытием
Write-Host "Нажмите любую клавишу для выхода..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

