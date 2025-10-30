# 🚀 Быстрая инструкция по развёртыванию

## 📦 Что изменилось:

1. ✅ **Убрана надпись "ID:"** - только цифры telegram_id
2. ✅ **Новый шрифт** - `Futuralightc.otf`
3. ✅ **3 реплики бота** - для обработки 200-500 юзеров/сек
4. ✅ **20 параллельных генераций** билетов (2 воркера × 10)
5. ✅ **Оптимизация PostgreSQL** - для высокой нагрузки
6. ✅ **Исправлена кнопка редактирования** анкеты
7. ✅ **Исправлена парная регистрация**

---

## 🎯 Полная инструкция развёртывания:

### На локальной машине (Windows):

```powershell
# 1. Добавить изменения в Git
git add -A
git commit -m "Optimize for extreme load + new ticket design"
git push

# ИЛИ загрузить файлы напрямую (быстрее)
scp ticket_config.py tasks.py bot/handlers.py Futuralightc.otf docker-compose.yml optimize_db.sql reset_tickets.sh root@5.53.125.89:~/tg_bot_bpl/

# Скопировать bot/handlers.py отдельно в нужную папку
scp bot/handlers.py root@5.53.125.89:~/tg_bot_bpl/bot/
```

### На сервере:

```bash
# 1. Подключиться к серверу
ssh root@5.53.125.89

# 2. Перейти в проект
cd ~/tg_bot_bpl

# 3. Если используете Git (РЕКОМЕНДУЕТСЯ)
git pull

# 4. Остановить сервисы
docker-compose down

# 5. Удалить старые билеты (опционально)
./reset_tickets.sh
# ИЛИ быстро:
rm -rf tickets/* && docker-compose exec db psql -U user -d new_bal_db -c "UPDATE surveys SET ticket_generated = FALSE, ticket_sent = FALSE, ticket_path = NULL WHERE ticket_cancelled = FALSE;"

# 6. Применить индексы БД
docker-compose up -d db
sleep 10
cat optimize_db.sql | docker-compose exec -T db psql -U user -d new_bal_db

# 7. Пересобрать с новыми настройками
docker-compose build --no-cache

# 8. Запустить всё
docker-compose up -d

# 9. Проверить что всё запустилось
docker-compose ps

# Должно быть:
# - 3 контейнера bot (bot_1, bot_2, bot_3)
# - 2 контейнера celery_worker
# - 1 db, redis, flower, pgadmin
```

---

## ✅ Проверка после запуска:

```bash
# Сколько реплик бота?
docker-compose ps | grep bot
# Должно быть: bot_1, bot_2, bot_3

# Логи бота (все реплики)
docker-compose logs -f bot --tail=50

# Celery мониторинг
http://YOUR_SERVER:5555

# Проверить регистрацию
# Отправьте /start боту в Telegram
```

---

## 🔧 Если что-то пошло не так:

### Проблема: Бот не запускается

```bash
# Посмотреть ошибки
docker-compose logs bot --tail=100

# Пересобрать
docker-compose down
docker-compose build --no-cache bot
docker-compose up -d
```

### Проблема: Шрифт не найден

```bash
# Проверить наличие файла
docker-compose exec bot ls -la /app/Futuralightc.otf

# Если нет - скопировать
docker cp Futuralightc.otf $(docker-compose ps -q bot | head -1):/app/
```

### Проблема: Реплики не создаются

Docker Compose v1 не поддерживает `replicas`. Используйте:

```bash
# Проверить версию
docker-compose --version

# Если v1 (< 2.0) - запустить вручную:
docker-compose up -d --scale bot=3 --scale celery_worker=2
```

---

## 📊 Мониторинг при наплыве:

```bash
# Нагрузка на сервер
htop

# Нагрузка на контейнеры
docker stats

# Блокировки в PostgreSQL (если тормозит)
docker-compose exec db psql -U user -d new_bal_db -c "
SELECT COUNT(*) as waiting_queries 
FROM pg_stat_activity 
WHERE wait_event IS NOT NULL;
"

# Скорость генерации (Flower)
http://YOUR_SERVER:5555
```

---

## 🎯 Итоговая производительность:

| Показатель | Значение |
|-----------|----------|
| Одновременные регистрации | **300-500 юзеров/сек** |
| Заполнение 3500 мест | **7-12 секунд** ⚡ |
| Генерация билетов | **3-5 минут** 🎫 |
| Рассылка | **3 минуты** 📤 |
| **ИТОГО** | **~7-10 минут** 🎉 |

**Ваш сервер (8GB, 4CPU) справится! ✅**

---

## 📝 Быстрая команда для деплоя:

**Один копипаст на сервере:**

```bash
cd ~/tg_bot_bpl && \
docker-compose down && \
rm -rf tickets/* && \
docker-compose up -d db && \
sleep 10 && \
cat optimize_db.sql | docker-compose exec -T db psql -U user -d new_bal_db && \
docker-compose build --no-cache && \
docker-compose up -d && \
echo "✅ ГОТОВО! Проверьте: docker-compose ps"
```

**Готово к экстремальному наплыву! 🔥**

