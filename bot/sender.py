"""
Модуль для отправки билетов пользователям.
Используется из Celery tasks.
"""

import os
import io
from aiogram import Bot
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv
import logging
import asyncio

load_dotenv()

logger = logging.getLogger(__name__)
TOKEN = os.getenv("BOT_TOKEN")


async def send_ticket_file(telegram_id: str, ticket_path: str, caption: str = None) -> bool:
    """
    Отправляет билет из файла пользователю.
    
    Args:
        telegram_id: Telegram ID пользователя
        ticket_path: Путь к файлу билета
        caption: Текст сообщения
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    bot = Bot(token=TOKEN)
    
    try:
        # Читаем файл
        with open(ticket_path, 'rb') as photo_file:
            input_file = BufferedInputFile(
                file=photo_file.read(),
                filename="ticket.png"
            )
        
        await bot.send_photo(
            chat_id=int(telegram_id),
            photo=input_file,
            caption=caption or "🎉 Ваш билет на мероприятие!\n\n⚠️ Сохраните и предъявите на входе."
        )
        
        logger.info(f"✅ Ticket sent to user {telegram_id}")
        
        # Задержка для соблюдения лимитов Telegram (~30 msg/sec)
        await asyncio.sleep(0.05)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send ticket to user {telegram_id}: {e}")
        return False
        
    finally:
        await bot.session.close()


async def send_ticket_to_user(telegram_id: str, photo: io.BytesIO, caption: str = None) -> bool:
    """
    Отправляет билет из BytesIO пользователю (для обратной совместимости).
    
    Args:
        telegram_id: Telegram ID пользователя
        photo: BytesIO объект с изображением билета
        caption: Текст сообщения
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    bot = Bot(token=TOKEN)
    
    try:
        input_file = BufferedInputFile(
            file=photo.getvalue(),
            filename="ticket.png"
        )
        
        await bot.send_photo(
            chat_id=int(telegram_id),
            photo=input_file,
            caption=caption or "🎉 Ваш билет на мероприятие!"
        )
        
        logger.info(f"✅ Ticket sent to user {telegram_id}")
        await asyncio.sleep(0.05)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send ticket to user {telegram_id}: {e}")
        return False
        
    finally:
        await bot.session.close()


async def send_broadcast_message(telegram_id: str, text: str) -> bool:
    """
    Отправляет текстовое сообщение пользователю (для обычных рассылок).
    
    Args:
        telegram_id: Telegram ID пользователя
        text: Текст сообщения
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    bot = Bot(token=TOKEN)
    
    try:
        await bot.send_message(
            chat_id=int(telegram_id),
            text=text,
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Broadcast message sent to user {telegram_id}")
        
        # Задержка для соблюдения лимитов
        await asyncio.sleep(0.05)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send broadcast to user {telegram_id}: {e}")
        return False
        
    finally:
        await bot.session.close()

