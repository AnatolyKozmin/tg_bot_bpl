"""
Скрипт для очистки базы данных.
ВНИМАНИЕ: Удаляет все данные регистраций!
"""

import asyncio
from sqlalchemy import select, delete
from db.session import async_session
from db.models import Survey, RegistrationConfig
from db.registration import initialize_registration_config

async def clear_database():
    """Очищает все таблицы БД"""
    
    print("⚠️  ВНИМАНИЕ! Будут удалены ВСЕ данные из базы данных!")
    print("Продолжить? (yes/no): ", end="")
    
    # В Docker нужно использовать переменную окружения для подтверждения
    import os
    if os.getenv("CONFIRM_CLEAR") != "yes":
        confirm = input().strip().lower()
        if confirm != "yes":
            print("❌ Отменено")
            return
    
    async with async_session() as session:
        # Удаляем все анкеты
        print("🗑️  Удаление анкет...")
        result = await session.execute(delete(Survey))
        await session.commit()
        print(f"✅ Удалено анкет: {result.rowcount}")
        
        # Сбрасываем счетчик регистраций
        print("🔄 Сброс счетчика регистраций...")
        result = await session.execute(
            select(RegistrationConfig).filter_by(id=1)
        )
        config = result.scalars().first()
        
        if config:
            config.current_count = 0
            config.is_open = True
            await session.commit()
            print("✅ Счетчик сброшен: 0/3500, регистрация открыта")
        else:
            # Создаем конфигурацию если её нет
            await initialize_registration_config()
            print("✅ Конфигурация создана заново")
    
    print("\n✅ База данных очищена!")

if __name__ == "__main__":
    asyncio.run(clear_database())

