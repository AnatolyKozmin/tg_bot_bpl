-- ===============================================================
-- Оптимизация БД для высокой нагрузки (200-500 юзеров/сек)
-- ===============================================================

-- 1. Индекс для быстрой проверки существующей регистрации
CREATE INDEX IF NOT EXISTS idx_surveys_telegram_id 
ON surveys(telegram_id) 
WHERE ticket_cancelled = FALSE;

-- 2. Индекс для генерации билетов
CREATE INDEX IF NOT EXISTS idx_surveys_ticket_generation 
ON surveys(ticket_generated, ticket_cancelled) 
WHERE ticket_cancelled = FALSE;

-- 3. Индекс для рассылки
CREATE INDEX IF NOT EXISTS idx_surveys_ticket_sending 
ON surveys(ticket_sent, ticket_generated, ticket_cancelled) 
WHERE ticket_cancelled = FALSE;

-- 4. Анализ таблиц для обновления статистики
ANALYZE surveys;
ANALYZE registration_config;

-- 5. Вывод информации
SELECT 
    schemaname,
    tablename,
    indexname
FROM pg_indexes 
WHERE tablename IN ('surveys', 'registration_config')
ORDER BY tablename, indexname;

-- 6. Статистика размера таблиц
SELECT 
    relname as table_name,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
    pg_size_pretty(pg_relation_size(relid)) as table_size,
    pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) as indexes_size
FROM pg_catalog.pg_statio_user_tables 
WHERE relname IN ('surveys', 'registration_config')
ORDER BY pg_total_relation_size(relid) DESC;

