import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from redis.asyncio import Redis
from aiogram.fsm.storage.redis import RedisStorage

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite+aiosqlite:///./test.db"
REDIS_URL = os.getenv("REDIS_URL") or "redis://localhost:6379/0"

# Оптимизированный connection pool для PostgreSQL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=50,              # Базовый размер пула (всегда открыто)
    max_overflow=100,          # Дополнительные соединения при пиковой нагрузке
    pool_pre_ping=True,        # Проверка соединений перед использованием
    pool_recycle=3600,         # Переподключение каждый час
    connect_args={
        "timeout": 30,
        "command_timeout": 60,
    } if "postgresql" in DATABASE_URL else {}
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Redis для FSM storage (состояния пользователей)
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
storage = RedisStorage(redis=redis_client)
