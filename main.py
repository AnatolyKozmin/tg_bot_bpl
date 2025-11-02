import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from bot.handlers import dp, bot
from db.init_db import init_database
import logging

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


async def on_startup():
    """Действия при запуске бота"""
    logger.info("🚀 Bot is starting...")
    
    # Полная инициализация базы данных
    # Создает таблицы если их нет и настраивает конфигурацию
    try:
        await init_database()
        logger.info("✅ Database ready")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
    
    # Регистрируем обработчики для массовой рассылки
    try:
        from bot.broadcast_handlers import register_broadcast_handlers
        await register_broadcast_handlers(dp)
        logger.info("✅ Broadcast handlers registered")
    except Exception as e:
        logger.error(f"❌ Failed to register broadcast handlers: {e}")
        raise


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Bot is shutting down...")
    await bot.session.close()
    logger.info("✅ Bot stopped")


async def main():
    try:
        await on_startup()
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == '__main__':
    asyncio.run(main())
