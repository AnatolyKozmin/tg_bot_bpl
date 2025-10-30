# ===============================================================
# Скрипт для сброса билетов (Windows PowerShell)
# ===============================================================

Write-Host "🗑️  СБРОС БИЛЕТОВ" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  Это действие:" -ForegroundColor Red
Write-Host "   - Удалит все файлы билетов из tickets/"
Write-Host "   - Сбросит флаги ticket_generated и ticket_sent"
Write-Host "   - НЕ удалит анкеты из БД"
Write-Host ""

$confirm = Read-Host "Продолжить? (yes/no)"

if ($confirm -ne "yes") {
    Write-Host "❌ Отменено" -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "1️⃣  Удаление файлов билетов..." -ForegroundColor Cyan
if (Test-Path "tickets") {
    Remove-Item -Path "tickets\*" -Recurse -Force
    Write-Host "   ✅ Удалено: tickets\*" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Папка tickets не найдена" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "2️⃣  Сброс флагов в БД..." -ForegroundColor Cyan
Write-Host "   (Выполните на сервере SSH команду ниже)" -ForegroundColor Yellow
Write-Host ""
Write-Host @"
docker-compose exec db psql -U user -d new_bal_db -c "
UPDATE surveys 
SET 
    ticket_generated = FALSE,
    ticket_sent = FALSE,
    ticket_path = NULL,
    ticket_generated_at = NULL,
    ticket_sent_at = NULL
WHERE ticket_cancelled = FALSE;
"
"@ -ForegroundColor White

Write-Host ""
Write-Host "✅ Локальная часть готова!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "💡 Что делать дальше:" -ForegroundColor Cyan
Write-Host "   1. Выполнить SQL команду выше на сервере"
Write-Host "   2. Загрузить обновлённые файлы:"
Write-Host "      scp ticket_config.py tasks.py Futuralightc.otf root@5.53.125.89:~/tg_bot_bpl/"
Write-Host ""
Write-Host "   3. На сервере:"
Write-Host "      cd ~/tg_bot_bpl"
Write-Host "      docker-compose down"
Write-Host "      docker-compose up -d --build"
Write-Host ""

