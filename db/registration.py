"""
Модуль для атомарной регистрации с проверкой мест.
Обеспечивает безопасность при высокой конкурентной нагрузке.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import RegistrationConfig
from db.session import async_session
import logging

logger = logging.getLogger(__name__)


async def initialize_registration_config() -> None:
    """
    Инициализирует конфигурацию регистрации при первом запуске.
    Создает запись с id=1 если её не существует.
    """
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(RegistrationConfig).filter_by(id=1)
            )
            config = result.scalars().first()
            
            if not config:
                config = RegistrationConfig(
                    id=1,
                    max_capacity=3500,
                    current_count=0,
                    is_open=True
                )
                session.add(config)
                await session.commit()
                logger.info("✅ Конфигурация регистрации инициализирована: 3500 мест")


async def try_register(ticket_type: str) -> tuple[bool, str]:
    """
    Атомарно проверяет и резервирует места для регистрации.
    
    Args:
        ticket_type: "single" или "pair"
    
    Returns:
        tuple: (успешно: bool, сообщение: str)
        
    Примеры:
        >>> success, msg = await try_register("single")
        >>> if success:
        ...     # Продолжить регистрацию
        ... else:
        ...     # Показать сообщение об ошибке
    """
    places_needed = 2 if ticket_type == "pair" else 1
    
    async with async_session() as session:
        async with session.begin():
            # SELECT FOR UPDATE блокирует строку до конца транзакции
            # Это предотвращает race condition при параллельных запросах
            result = await session.execute(
                select(RegistrationConfig)
                .filter_by(id=1)
                .with_for_update()  # 🔒 КРИТИЧНО для атомарности!
            )
            config = result.scalars().first()
            
            if not config:
                logger.error("❌ Конфигурация регистрации не найдена!")
                return False, "Ошибка системы. Обратитесь к администратору."
            
            # Проверка: открыта ли регистрация
            if not config.is_open:
                remaining = config.max_capacity - config.current_count
                return False, f"❌ Регистрация закрыта. Все {config.max_capacity} мест заняты."
            
            # Проверка: достаточно ли мест
            if config.current_count + places_needed > config.max_capacity:
                remaining = config.max_capacity - config.current_count
                if remaining > 0:
                    msg = f"❌ Недостаточно мест. Осталось {remaining} мест, а вы запрашиваете {places_needed}."
                else:
                    msg = f"❌ Все {config.max_capacity} мест заняты!"
                
                # Автоматически закрываем регистрацию
                config.is_open = False
                await session.commit()
                return False, msg
            
            # ✅ Резервируем места
            config.current_count += places_needed
            
            # Автозакрытие при достижении лимита
            if config.current_count >= config.max_capacity:
                config.is_open = False
                logger.warning(f"🚫 Регистрация автоматически закрыта! Достигнут лимит: {config.max_capacity}")
            
            await session.commit()
            
            remaining = config.max_capacity - config.current_count
            logger.info(
                f"✅ Зарегистрировано {places_needed} мест. "
                f"Всего занято: {config.current_count}/{config.max_capacity}. "
                f"Осталось: {remaining}"
            )
            
            return True, f"✅ Успешно! Зарегистрировано мест: {places_needed}."


async def get_registration_stats() -> dict:
    """
    Получает статистику регистрации.
    
    Returns:
        dict: {
            'max_capacity': int,
            'current_count': int,
            'remaining': int,
            'is_open': bool,
            'percentage': float
        }
    """
    async with async_session() as session:
        result = await session.execute(
            select(RegistrationConfig).filter_by(id=1)
        )
        config = result.scalars().first()
        
        if not config:
            return {
                'max_capacity': 0,
                'current_count': 0,
                'remaining': 0,
                'is_open': False,
                'percentage': 0.0
            }
        
        remaining = config.max_capacity - config.current_count
        percentage = (config.current_count / config.max_capacity) * 100 if config.max_capacity > 0 else 0
        
        return {
            'max_capacity': config.max_capacity,
            'current_count': config.current_count,
            'remaining': remaining,
            'is_open': config.is_open,
            'percentage': round(percentage, 2)
        }


async def toggle_registration(is_open: bool) -> bool:
    """
    Открывает/закрывает регистрацию вручную (для админов).
    
    Args:
        is_open: True - открыть, False - закрыть
    
    Returns:
        bool: Успешно ли выполнена операция
    """
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(RegistrationConfig).filter_by(id=1)
            )
            config = result.scalars().first()
            
            if not config:
                return False
            
            config.is_open = is_open
            await session.commit()
            
            status = "открыта" if is_open else "закрыта"
            logger.info(f"🔄 Регистрация {status} вручную администратором")
            return True

