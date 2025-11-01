-- Миграция: делаем поле "group" nullable для выпускников
-- Дата: 2025-10-30
-- Причина: Выпускникам не нужно указывать факультет, курс и группу

-- Изменяем колонку group на nullable
ALTER TABLE surveys ALTER COLUMN "group" DROP NOT NULL;

-- Проверяем результат
\d surveys

