#!/usr/bin/env python
"""
Скрипт для инициализации базы данных.

Использование:
    python init_database.py

Что делает:
    1. Проверяет подключение к БД
    2. Создает все таблицы (если их нет)
    3. Инициализирует конфигурацию регистрации
    4. Проверяет корректность настроек

Альтернатива Alembic миграциям для быстрого старта.
Для продакшена рекомендуется использовать: alembic upgrade head
"""

import asyncio
import sys
import logging
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

from db.init_db import init_database, check_database_connection
from db.session import async_session, engine
from sqlalchemy import text

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def verify_setup():
    """Проверяет что все настроено корректно"""
    logger.info("\n📋 Verifying database setup...\n")
    
    try:
        async with async_session() as session:
            # Проверка таблицы surveys
            result = await session.execute(
                text("SELECT COUNT(*) FROM surveys")
            )
            surveys_count = result.scalar()
            logger.info(f"✅ Table 'surveys': {surveys_count} records")
            
            # Проверка таблицы registration_config
            result = await session.execute(
                text("SELECT id, max_capacity, current_count, is_open FROM registration_config WHERE id = 1")
            )
            config = result.first()
            
            if config:
                logger.info(f"✅ Table 'registration_config':")
                logger.info(f"   - Max capacity: {config[1]}")
                logger.info(f"   - Current count: {config[2]}")
                logger.info(f"   - Is open: {'🟢 Yes' if config[3] else '🔴 No'}")
            else:
                logger.warning("⚠️  Registration config not found")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False


async def main():
    """Главная функция инициализации"""
    logger.info("=" * 60)
    logger.info("🚀 DATABASE INITIALIZATION SCRIPT")
    logger.info("=" * 60)
    
    try:
        # Инициализация
        await init_database()
        
        logger.info("\n" + "=" * 60)
        
        # Проверка
        success = await verify_setup()
        
        logger.info("\n" + "=" * 60)
        
        if success:
            logger.info("✅ DATABASE SETUP COMPLETE!")
            logger.info("\nNext steps:")
            logger.info("  1. Start the bot: python main.py")
            logger.info("  2. Or use Docker: docker-compose up -d")
            logger.info("=" * 60)
            return 0
        else:
            logger.error("❌ SETUP INCOMPLETE - Please check errors above")
            logger.info("=" * 60)
            return 1
            
    except Exception as e:
        logger.error(f"\n❌ FATAL ERROR: {e}")
        logger.info("=" * 60)
        return 1
    finally:
        # Закрываем соединение
        await engine.dispose()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

