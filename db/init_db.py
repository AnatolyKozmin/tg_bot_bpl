"""
Инициализация базы данных.
Создает таблицы и начальные данные.
"""

import asyncio
import logging
from sqlalchemy import text
from db.models import Base, RegistrationConfig
from db.session import engine, async_session

logger = logging.getLogger(__name__)


async def create_tables():
    """
    Создает все таблицы если их нет.
    Использует metadata из моделей.
    """
    try:
        async with engine.begin() as conn:
            # Создаем таблицы
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise


async def initialize_config():
    """
    Инициализирует конфигурацию регистрации.
    Создает запись с id=1 если её нет.
    """
    try:
        async with async_session() as session:
            async with session.begin():
                # Проверяем существует ли конфигурация
                result = await session.execute(
                    text("SELECT COUNT(*) FROM registration_config WHERE id = 1")
                )
                count = result.scalar()
                
                if count == 0:
                    # Создаем начальную конфигурацию
                    config = RegistrationConfig(
                        id=1,
                        max_capacity=3500,
                        current_count=0,
                        is_open=True
                    )
                    session.add(config)
                    await session.commit()
                    logger.info("✅ Registration config initialized: 3500 seats")
                else:
                    logger.info("✅ Registration config already exists")
                    
    except Exception as e:
        logger.error(f"❌ Error initializing config: {e}")
        raise


async def check_database_connection():
    """
    Проверяет подключение к базе данных.
    """
    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            logger.info("✅ Database connection successful")
            return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


async def init_database():
    """
    Полная инициализация базы данных:
    1. Проверка подключения
    2. Создание таблиц
    3. Инициализация конфигурации
    """
    logger.info("🔄 Initializing database...")
    
    # Проверяем подключение
    connected = await check_database_connection()
    if not connected:
        logger.error("❌ Cannot connect to database!")
        raise ConnectionError("Database connection failed")
    
    # Создаем таблицы
    await create_tables()
    
    # Инициализируем конфигурацию
    await initialize_config()
    
    logger.info("✅ Database initialization complete!")


if __name__ == "__main__":
    # Можно запустить отдельно для инициализации БД
    asyncio.run(init_database())

