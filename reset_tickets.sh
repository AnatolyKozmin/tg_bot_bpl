#!/bin/bash

# ===============================================================
# Скрипт для сброса билетов (перегенерация с новым дизайном)
# ===============================================================

echo "🗑️  СБРОС БИЛЕТОВ"
echo "========================================"
echo ""
echo "⚠️  Это действие:"
echo "   - Удалит все файлы билетов из tickets/"
echo "   - Сбросит флаги ticket_generated и ticket_sent"
echo "   - НЕ удалит анкеты из БД"
echo ""
read -p "Продолжить? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Отменено"
    exit 0
fi

echo ""
echo "1️⃣  Удаление файлов билетов..."
rm -rf tickets/*
echo "   ✅ Удалено: tickets/*"

echo ""
echo "2️⃣  Сброс флагов в БД..."
docker-compose exec -T db psql -U user -d new_bal_db << EOF
UPDATE surveys 
SET 
    ticket_generated = FALSE,
    ticket_sent = FALSE,
    ticket_path = NULL,
    ticket_generated_at = NULL,
    ticket_sent_at = NULL
WHERE ticket_cancelled = FALSE;

SELECT COUNT(*) as reset_count FROM surveys WHERE ticket_cancelled = FALSE;
EOF

echo ""
echo "3️⃣  Проверка результата..."
count=$(ls tickets/ 2>/dev/null | wc -l)
echo "   📁 Билетов в tickets/: $count"

db_count=$(docker-compose exec -T db psql -U user -d new_bal_db -t -c "SELECT COUNT(*) FROM surveys WHERE ticket_generated = FALSE AND ticket_cancelled = FALSE;")
echo "   🗄️  Анкет без билетов в БД: $db_count"

echo ""
echo "✅ ГОТОВО!"
echo "========================================"
echo ""
echo "💡 Что делать дальше:"
echo "   1. Перезапустить сервисы с новыми настройками:"
echo "      docker-compose down"
echo "      docker-compose up -d --build"
echo ""
echo "   2. Сгенерировать билеты заново:"
echo "      /generate_tickets (в боте как админ)"
echo ""
echo "   3. Разослать билеты:"
echo "      /rass (в боте как админ)"
echo ""

