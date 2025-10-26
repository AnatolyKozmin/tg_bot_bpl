"""
Middleware для защиты бота от спама и DDoS атак.
"""

from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Ограничивает количество сообщений от одного пользователя.
    
    Защищает от:
    - Спама
    - Случайных double-clicks
    - Простых DDoS атак
    
    Параметры:
        rate_limit: Максимум сообщений в секунду от одного пользователя
    """
    
    def __init__(self, rate_limit: int = 5):
        super().__init__()
        self.rate_limit = rate_limit
        self.user_timestamps: Dict[int, list[datetime]] = {}
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        now = datetime.now()
        
        # Инициализация для нового пользователя
        if user_id not in self.user_timestamps:
            self.user_timestamps[user_id] = []
        
        # Очищаем timestamps старше 1 секунды
        self.user_timestamps[user_id] = [
            ts for ts in self.user_timestamps[user_id]
            if now - ts < timedelta(seconds=1)
        ]
        
        # Проверка лимита
        if len(self.user_timestamps[user_id]) >= self.rate_limit:
            logger.warning(
                f"⚠️ Rate limit exceeded: user_id={user_id}, "
                f"username={event.from_user.username}, "
                f"count={len(self.user_timestamps[user_id])}"
            )
            
            # Отправляем предупреждение
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Слишком быстро! Подождите секунду.\n"
                    "Если вы не спамите, просто подождите немного."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Слишком быстро! Подождите секунду.",
                    show_alert=True
                )
            return
        
        # Добавляем текущий timestamp
        self.user_timestamps[user_id].append(now)
        
        # Продолжаем обработку
        return await handler(event, data)


class AntiFloodMiddleware(BaseMiddleware):
    """
    Блокирует пользователей, которые превышают лимит сообщений.
    Более строгая защита чем RateLimitMiddleware.
    
    Параметры:
        max_messages: Максимум сообщений за period
        period: Период в секундах
        ban_time: Время блокировки в секундах
    """
    
    def __init__(self, max_messages: int = 20, period: int = 60, ban_time: int = 300):
        super().__init__()
        self.max_messages = max_messages
        self.period = period
        self.ban_time = ban_time
        self.user_messages: Dict[int, list[datetime]] = {}
        self.banned_users: Dict[int, datetime] = {}
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        now = datetime.now()
        
        # Проверка: забанен ли пользователь
        if user_id in self.banned_users:
            ban_end = self.banned_users[user_id]
            if now < ban_end:
                # Еще забанен
                remaining = int((ban_end - now).total_seconds())
                if isinstance(event, Message):
                    await event.answer(
                        f"🚫 Вы временно заблокированы за флуд.\n"
                        f"Осталось: {remaining} секунд."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        f"🚫 Заблокированы за флуд ({remaining} сек)",
                        show_alert=True
                    )
                return
            else:
                # Бан истек
                del self.banned_users[user_id]
                logger.info(f"✅ User {user_id} unbanned")
        
        # Инициализация
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        
        # Очищаем старые сообщения
        cutoff = now - timedelta(seconds=self.period)
        self.user_messages[user_id] = [
            ts for ts in self.user_messages[user_id]
            if ts > cutoff
        ]
        
        # Проверка лимита
        if len(self.user_messages[user_id]) >= self.max_messages:
            # ФЛУД! Баним пользователя
            ban_until = now + timedelta(seconds=self.ban_time)
            self.banned_users[user_id] = ban_until
            
            logger.error(
                f"🚫 FLOOD DETECTED: user_id={user_id}, "
                f"username={event.from_user.username}, "
                f"messages={len(self.user_messages[user_id])}/{self.max_messages}, "
                f"banned_until={ban_until}"
            )
            
            if isinstance(event, Message):
                await event.answer(
                    f"🚫 Обнаружен флуд! Вы заблокированы на {self.ban_time} секунд.\n"
                    f"При повторных нарушениях блокировка будет постоянной."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    f"🚫 Флуд! Блокировка {self.ban_time} сек",
                    show_alert=True
                )
            return
        
        # Добавляем текущее сообщение
        self.user_messages[user_id].append(now)
        
        # Продолжаем обработку
        return await handler(event, data)

