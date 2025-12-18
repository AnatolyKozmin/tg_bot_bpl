"""
Модуль для отправки билетов пользователям.
Используется из Celery tasks.
"""

import os
import io
import time
import re
from aiogram import Bot
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv
import logging
import asyncio
import redis

load_dotenv()

logger = logging.getLogger(__name__)
TOKEN = os.getenv("BOT_TOKEN")
REDIS_BROKER_URL = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/1")

# Rate limiter для Telegram API (20 запросов/сек)
# Используем Redis для синхронизации между всеми воркерами
class TelegramRateLimiter:
    """
    Распределенный rate limiter через Redis.
    Ограничивает до 20 запросов в секунду на весь бот (все воркеры вместе).
    """
    def __init__(self, max_per_second: int = 18):  # 18 для безопасности (оставляем запас)
        self.max_per_second = max_per_second
        self.redis_client = None
        self._connect_redis()
    
    def _connect_redis(self):
        """Подключаемся к Redis"""
        try:
            # Парсим URL redis://host:port/db
            if REDIS_BROKER_URL.startswith("redis://"):
                url = REDIS_BROKER_URL.replace("redis://", "")
                if "/" in url:
                    host_port, db = url.split("/")
                else:
                    host_port, db = url, "0"
                
                if ":" in host_port:
                    host, port = host_port.split(":")
                else:
                    host, port = host_port, "6379"
                
                self.redis_client = redis.Redis(
                    host=host,
                    port=int(port),
                    db=int(db) if db.isdigit() else 0,
                    decode_responses=False,
                    socket_connect_timeout=2
                )
                # Проверяем подключение
                self.redis_client.ping()
                logger.info(f"✅ Redis rate limiter connected: {host}:{port}/{db}")
            else:
                logger.warning("⚠️ Invalid Redis URL, rate limiter disabled")
                self.redis_client = None
        except Exception as e:
            logger.warning(f"⚠️ Failed to connect Redis for rate limiter: {e}. Using fallback.")
            self.redis_client = None
    
    async def acquire(self):
        """
        Ожидает разрешения на отправку запроса.
        Использует sliding window через Redis.
        """
        if not self.redis_client:
            # Fallback: просто задержка если Redis недоступен
            await asyncio.sleep(1.0 / self.max_per_second)
            return
        
        try:
            current_time = time.time()
            window_start = current_time - 1.0  # Окно в 1 секунду
            
            # Используем Redis sorted set для хранения timestamps
            key = "telegram_rate_limit:requests"
            
            # Удаляем старые записи (старше 1 секунды)
            self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Проверяем количество запросов в текущем окне
            count = self.redis_client.zcard(key)
            
            if count >= self.max_per_second:
                # Нужно подождать
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    wait_time = 1.0 - (current_time - oldest_time)
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                        # Удаляем старый timestamp после ожидания
                        self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Добавляем текущий запрос
            self.redis_client.zadd(key, {str(current_time): current_time})
            # Устанавливаем TTL на ключ (на случай если он останется)
            self.redis_client.expire(key, 2)
            
        except Exception as e:
            logger.warning(f"⚠️ Rate limiter error: {e}. Using fallback delay.")
            # Fallback при ошибке Redis
            await asyncio.sleep(1.0 / self.max_per_second)

# Глобальный экземпляр rate limiter
_rate_limiter = TelegramRateLimiter(max_per_second=18)


def detect_and_convert_spoilers(text: str) -> tuple[str, str]:
    """
    Автоматически определяет формат текста и конвертирует спойлеры.
    
    Поддерживает:
    - Markdown спойлеры: ||текст|| → HTML <spoiler>текст</spoiler>
    - HTML спойлеры: <spoiler>текст</spoiler> (оставляет как есть)
    
    Если обнаружены спойлеры, весь текст конвертируется в HTML формат.
    
    Args:
        text: Исходный текст
    
    Returns:
        tuple[str, str]: (обработанный текст, parse_mode)
    """
    # Проверяем наличие HTML спойлеров (если уже в HTML формате)
    if '<spoiler>' in text or '<tg-spoiler>' in text:
        return text, "HTML"
    
    # Проверяем наличие Markdown спойлеров ||текст||
    # Используем более надежное регулярное выражение
    spoiler_pattern = r'\|\|.*?\|\|'
    if re.search(spoiler_pattern, text, re.DOTALL):
        # Сохраняем спойлеры во временные плейсхолдеры, чтобы не сломать их при конвертации Markdown
        spoiler_placeholders = {}
        spoiler_counter = 0
        
        def save_spoiler(match):
            nonlocal spoiler_counter
            placeholder = f"__SPOILER_{spoiler_counter}__"
            spoiler_placeholders[placeholder] = match.group(1)  # Сохраняем только содержимое
            spoiler_counter += 1
            return placeholder
        
        # Временно заменяем спойлеры на плейсхолдеры
        # Используем нежадный поиск для правильной обработки нескольких спойлеров
        text = re.sub(r'\|\|(.*?)\|\|', save_spoiler, text, flags=re.DOTALL)
        
        # Конвертируем Markdown форматирование в HTML
        # **жирный** → <b>жирный</b>
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # *курсив* → <i>курсив</i> (но не если это часть **)
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<i>\1</i>', text)
        # `код` → <code>код</code>
        text = re.sub(r'`([^`]+?)`', r'<code>\1</code>', text)
        
        # Восстанавливаем спойлеры и конвертируем их в HTML
        # Экранируем HTML символы в содержимом спойлеров
        def escape_html(text_to_escape):
            text_to_escape = text_to_escape.replace('&', '&amp;')
            text_to_escape = text_to_escape.replace('<', '&lt;')
            text_to_escape = text_to_escape.replace('>', '&gt;')
            return text_to_escape
        
        for placeholder, spoiler_content in spoiler_placeholders.items():
            escaped_content = escape_html(spoiler_content)
            text = text.replace(placeholder, f'<spoiler>{escaped_content}</spoiler>')
        
        return text, "HTML"
    
    # По умолчанию используем Markdown
    return text, "Markdown"


async def send_ticket_file(telegram_id: str, ticket_path: str, caption: str = None) -> bool:
    """
    Отправляет билет из файла пользователю.
    Использует распределенный rate limiter для соблюдения лимитов Telegram API.
    
    Args:
        telegram_id: Telegram ID пользователя
        ticket_path: Путь к файлу билета
        caption: Текст сообщения
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    bot = Bot(token=TOKEN)
    
    try:
        # Получаем разрешение от rate limiter (ожидает если нужно)
        await _rate_limiter.acquire()
        
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
        # Получаем разрешение от rate limiter
        await _rate_limiter.acquire()
        
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
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send ticket to user {telegram_id}: {e}")
        return False
        
    finally:
        await bot.session.close()


async def send_broadcast_message(telegram_id: str, text: str, parse_mode: str = "Markdown") -> tuple[bool, str]:
    """
    Отправляет текстовое сообщение пользователю (для обычных рассылок).
    Автоматически определяет и конвертирует спойлеры (||текст|| → <spoiler>текст</spoiler>).
    
    Args:
        telegram_id: Telegram ID пользователя
        text: Текст сообщения
        parse_mode: Режим парсинга (Markdown, HTML или None). Если "auto", определяется автоматически.
    
    Returns:
        tuple[bool, str]: (успешно, сообщение об ошибке если есть)
    """
    bot = Bot(token=TOKEN)
    
    try:
        # Автоматически определяем формат и конвертируем спойлеры
        # Если parse_mode не указан явно как HTML или None, проверяем на спойлеры
        if parse_mode in ("auto", "Markdown") or (parse_mode is None):
            processed_text, detected_mode = detect_and_convert_spoilers(text)
            parse_mode = detected_mode
            text = processed_text
        
        # Получаем разрешение от rate limiter
        await _rate_limiter.acquire()
        
        await bot.send_message(
            chat_id=int(telegram_id),
            text=text,
            parse_mode=parse_mode if parse_mode and parse_mode != "None" else None
        )
        
        logger.info(f"✅ Broadcast message sent to user {telegram_id}")
        
        return True, ""
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Failed to send broadcast to user {telegram_id}: {error_msg}")
        return False, error_msg
        
    finally:
        await bot.session.close()


async def send_broadcast_photo(telegram_id: str, photo_path: str, caption: str = None, parse_mode: str = "Markdown") -> tuple[bool, str]:
    """
    Отправляет фото с подписью пользователю (для рассылок с изображениями).
    Автоматически определяет и конвертирует спойлеры в подписи (||текст|| → <spoiler>текст</spoiler>).
    
    Args:
        telegram_id: Telegram ID пользователя
        photo_path: Путь к файлу изображения
        caption: Текст подписи к фото
        parse_mode: Режим парсинга (Markdown, HTML или None). Если "auto", определяется автоматически.
    
    Returns:
        tuple[bool, str]: (успешно, сообщение об ошибке если есть)
    """
    bot = Bot(token=TOKEN)
    
    try:
        # Автоматически определяем формат и конвертируем спойлеры в подписи
        processed_caption = caption
        if caption:
            # Если parse_mode не указан явно как HTML или None, проверяем на спойлеры
            if parse_mode in ("auto", "Markdown") or (parse_mode is None):
                processed_caption, detected_mode = detect_and_convert_spoilers(caption)
                parse_mode = detected_mode
            else:
                processed_caption = caption
        
        # Получаем разрешение от rate limiter
        await _rate_limiter.acquire()
        
        # Проверяем существование файла
        if not os.path.exists(photo_path):
            raise FileNotFoundError(f"Photo file not found: {photo_path}")
        
        # Читаем и отправляем файл
        with open(photo_path, 'rb') as photo_file:
            from aiogram.types import BufferedInputFile
            input_file = BufferedInputFile(
                file=photo_file.read(),
                filename=os.path.basename(photo_path)
            )
            
            await bot.send_photo(
                chat_id=int(telegram_id),
                photo=input_file,
                caption=processed_caption,
                parse_mode=parse_mode if parse_mode and parse_mode != "None" else None
            )
        
        logger.info(f"✅ Broadcast photo sent to user {telegram_id}")
        
        return True, ""
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Failed to send broadcast photo to user {telegram_id}: {error_msg}")
        return False, error_msg
        
    finally:
        await bot.session.close()

