"""
Webhook версия бота для production.

Преимущества перед Long Polling:
- Поддержка нескольких инстансов (масштабирование)
- Меньшая нагрузка на Telegram API
- Быстрее обрабатывает обновления

Требования:
- Домен с SSL сертификатом
- Открытый порт (рекомендуется 443 или 8443)
- Nginx/Caddy как reverse proxy (опционально)

Использование:
    python main_webhook.py

Переменные окружения:
    WEBHOOK_HOST - внешний домен (https://yourdomain.com)
    WEBHOOK_PATH - путь (по умолчанию /webhook)
    WEBAPP_HOST - внутренний хост (по умолчанию 0.0.0.0)
    WEBAPP_PORT - внутренний порт (по умолчанию 8443)
"""

import os
import asyncio
import logging
from aiohttp import web
from aiogram import types
from dotenv import load_dotenv

load_dotenv()

from bot.handlers import dp, bot
from db.init_db import init_database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Webhook настройки
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://yourdomain.com")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", f"/webhook/{os.getenv('BOT_TOKEN')}")
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Web app настройки
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", 8443))


async def webhook_handler(request: web.Request) -> web.Response:
    """
    Обработчик входящих обновлений от Telegram
    """
    try:
        update = await request.json()
        telegram_update = types.Update(**update)
        await dp.feed_webhook_update(bot, telegram_update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return web.Response(text="Error", status=500)


async def health_check(request: web.Request) -> web.Response:
    """
    Health check endpoint для мониторинга
    """
    return web.json_response({"status": "ok", "service": "telegram_bot"})


async def on_startup(app: web.Application):
    """
    Действия при запуске веб-приложения
    """
    logger.info("🚀 Bot starting (webhook mode)...")
    
    try:
        # Инициализация БД
        await init_database()
        logger.info("✅ Database ready")
        
        # Установка webhook
        webhook_info = await bot.get_webhook_info()
        
        if webhook_info.url != WEBHOOK_URL:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                drop_pending_updates=False,  # Обрабатываем пропущенные обновления
                allowed_updates=["message", "callback_query"]
            )
            logger.info(f"✅ Webhook set: {WEBHOOK_URL}")
        else:
            logger.info(f"✅ Webhook already set: {WEBHOOK_URL}")
            
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")
        raise


async def on_shutdown(app: web.Application):
    """
    Действия при остановке веб-приложения
    """
    logger.info("🛑 Bot shutting down...")
    
    # Удаляем webhook (опционально)
    # await bot.delete_webhook(drop_pending_updates=False)
    
    await bot.session.close()
    logger.info("✅ Bot stopped")


def create_app() -> web.Application:
    """
    Создание веб-приложения
    """
    app = web.Application()
    
    # Маршруты
    app.router.add_post(WEBHOOK_PATH, webhook_handler)
    app.router.add_get("/health", health_check)
    
    # Lifecycle callbacks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    return app


def main():
    """
    Запуск веб-сервера
    """
    logger.info("=" * 60)
    logger.info("🌐 WEBHOOK MODE")
    logger.info(f"📍 URL: {WEBHOOK_URL}")
    logger.info(f"🏠 Listen: {WEBAPP_HOST}:{WEBAPP_PORT}")
    logger.info("=" * 60)
    
    app = create_app()
    web.run_app(
        app,
        host=WEBAPP_HOST,
        port=WEBAPP_PORT,
        print=None  # Отключаем стандартный вывод aiohttp
    )


if __name__ == "__main__":
    main()

