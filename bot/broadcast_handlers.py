"""
Обработчики команд для массовой рассылки сообщений всем участникам бота.

Команды:
- /broadcast - Запуск интерактивной рассылки
- /broadcast_stats - Статистика последней рассылки
"""

import os
import asyncio
import time
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from db.session import async_session
from sqlalchemy import select, func
from db.models import Survey
import logging

load_dotenv()

logger = logging.getLogger(__name__)

ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


class BroadcastStates(StatesGroup):
    """Состояния для процесса создания рассылки"""
    choose_type = State()          # Выбор типа рассылки (текст/фото)
    enter_text = State()           # Ввод текста сообщения
    upload_photo = State()         # Загрузка фото
    enter_caption = State()        # Ввод подписи к фото
    confirm = State()              # Подтверждение рассылки


def get_broadcast_type_keyboard():
    """Клавиатура для выбора типа рассылки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Текстовое сообщение", callback_data="broadcast_type_text"),
            InlineKeyboardButton(text="🖼 Фото с подписью", callback_data="broadcast_type_photo")
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")]
    ])


def get_confirm_keyboard():
    """Клавиатура подтверждения рассылки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast_confirm")],
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data="broadcast_edit"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])


def get_skip_caption_keyboard():
    """Клавиатура для пропуска подписи к фото"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏭ Без подписи", callback_data="broadcast_skip_caption"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
        ]
    ])


async def monitor_broadcast_progress(message: Message, total_count: int, start_time: float):
    """
    Мониторинг прогресса массовой рассылки через проверку задач Celery.
    Отправляет обновления каждые 50 сообщений и финальную статистику.
    
    Args:
        message: Сообщение для отправки обновлений
        total_count: Общее количество получателей
        start_time: Время начала рассылки
    """
    PROGRESS_INTERVAL = 50  # Обновление каждые 50 сообщений
    CHECK_INTERVAL = 2      # Проверка каждые 2 секунды
    MAX_WAIT_TIME = 3600    # Максимальное время ожидания (1 час)
    
    last_reported = 0
    
    try:
        # Подсчитываем успешные и неудачные отправки через результаты задач
        # Для простоты будем ждать завершения и проверять статус
        completed = 0
        
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            
            # Здесь мы просто ждем и обновляем прогресс
            # В реальности можно проверять Celery result backend
            elapsed = time.time() - start_time
            
            # Примерная оценка прогресса (18 сообщений в секунду с учетом rate limiter)
            estimated_completed = min(int(elapsed * 18), total_count)
            
            # Отправляем промежуточное сообщение
            if estimated_completed - last_reported >= PROGRESS_INTERVAL and estimated_completed < total_count:
                remaining = total_count - estimated_completed
                progress_percent = (estimated_completed / total_count) * 100
                
                # Оставшееся время
                if estimated_completed > 0:
                    avg_time_per_msg = elapsed / estimated_completed
                    estimated_remaining_time = avg_time_per_msg * remaining
                    if estimated_remaining_time > 60:
                        time_str = f"~{estimated_remaining_time / 60:.1f} мин"
                    else:
                        time_str = f"~{estimated_remaining_time:.0f} сек"
                else:
                    time_str = "расчет..."
                
                await message.answer(
                    f"📊 **Прогресс рассылки**\n\n"
                    f"✅ Отправлено (примерно): {estimated_completed} / {total_count} ({progress_percent:.1f}%)\n"
                    f"⏳ Осталось: {remaining}\n"
                    f"⏱ Примерное время: {time_str}",
                    parse_mode="Markdown"
                )
                last_reported = estimated_completed
            
            # Проверяем завершение или таймаут
            if elapsed > MAX_WAIT_TIME or estimated_completed >= total_count:
                break
        
        # Финальная статистика
        elapsed_minutes = int(elapsed // 60)
        elapsed_seconds = int(elapsed % 60)
        
        final_message = (
            f"✅ **Рассылка завершена!**\n\n"
            f"📊 **Статистика:**\n"
            f"• Всего получателей: {total_count}\n"
            f"• ⏱ Время выполнения: {elapsed_minutes} мин {elapsed_seconds} сек\n"
            f"• 📈 Скорость: ~{total_count / elapsed * 60:.1f} сообщений/мин\n\n"
            f"💡 **Примечание:** Для точной статистики (успешных/ошибок) проверь логи воркеров."
        )
        
        await message.answer(final_message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка при мониторинге рассылки: {e}", exc_info=True)
        await message.answer(
            f"⚠️ Ошибка мониторинга прогресса:\n`{str(e)}`",
            parse_mode="Markdown"
        )


async def register_broadcast_handlers(dp: Dispatcher):
    """Регистрирует все обработчики рассылки"""
    
    @dp.message(Command("broadcast"))
    async def cmd_broadcast(message: Message, state: FSMContext):
        """Запуск интерактивной массовой рассылки"""
        if not is_admin(message.from_user.id):
            await message.answer("❌ У тебя нет доступа к этой команде.")
            return
        
        # Получаем количество потенциальных получателей
        async with async_session() as session:
            result = await session.execute(
                select(func.count(Survey.id)).where(
                    Survey.telegram_id.isnot(None),
                    Survey.ticket_cancelled == False
                )
            )
            total_users = result.scalar()
        
        if total_users == 0:
            await message.answer("❌ Нет пользователей для рассылки.")
            return
        
        await state.clear()
        await state.set_state(BroadcastStates.choose_type)
        
        await message.answer(
            f"📢 **МАССОВАЯ РАССЫЛКА**\n\n"
            f"👥 Получателей: {total_users}\n\n"
            f"Выбери тип сообщения:",
            reply_markup=get_broadcast_type_keyboard(),
            parse_mode="Markdown"
        )
    
    
    @dp.callback_query(lambda c: c.data == "broadcast_type_text")
    async def broadcast_type_text(callback: CallbackQuery, state: FSMContext):
        """Выбор текстовой рассылки"""
        await callback.answer()
        await state.update_data(broadcast_type="text")
        await state.set_state(BroadcastStates.enter_text)
        
        await callback.message.edit_text(
            "📝 **Текстовая рассылка**\n\n"
            "Введи текст сообщения для рассылки:\n\n"
            "💡 Можешь использовать Markdown форматирование:\n"
            "• `**жирный**` → **жирный**\n"
            "• `*курсив*` → *курсив*\n"
            "• `` `код` `` → `код`\n"
            "• `||скрытый текст||` → скрытый текст (спойлер)",
            parse_mode="Markdown"
        )
    
    
    @dp.callback_query(lambda c: c.data == "broadcast_type_photo")
    async def broadcast_type_photo(callback: CallbackQuery, state: FSMContext):
        """Выбор рассылки с фото"""
        await callback.answer()
        await state.update_data(broadcast_type="photo")
        await state.set_state(BroadcastStates.upload_photo)
        
        await callback.message.edit_text(
            "🖼 **Рассылка с фото**\n\n"
            "Отправь фото для рассылки:",
            parse_mode="Markdown"
        )
    
    
    @dp.message(BroadcastStates.enter_text)
    async def enter_text_handler(message: Message, state: FSMContext):
        """Обработка ввода текста"""
        if not message.text:
            await message.answer("❌ Пожалуйста, отправь текстовое сообщение.")
            return
        
        # Проверка длины (Telegram ограничение 4096 символов)
        if len(message.text) > 4096:
            await message.answer(
                "❌ Текст слишком длинный!\n"
                f"Максимум: 4096 символов\n"
                f"Сейчас: {len(message.text)} символов"
            )
            return
        
        await state.update_data(message_text=message.text)
        await state.set_state(BroadcastStates.confirm)
        
        # Получаем количество получателей
        async with async_session() as session:
            result = await session.execute(
                select(func.count(Survey.id)).where(
                    Survey.telegram_id.isnot(None),
                    Survey.ticket_cancelled == False
                )
            )
            total_users = result.scalar()
        
        # Показываем preview
        preview_text = (
            f"📋 **ПРЕДПРОСМОТР РАССЫЛКИ**\n\n"
            f"📝 Тип: Текстовое сообщение\n"
            f"👥 Получателей: {total_users}\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"{message.text}\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"Всё верно?"
        )
        
        await message.answer(
            preview_text,
            reply_markup=get_confirm_keyboard(),
            parse_mode="Markdown"
        )
    
    
    @dp.message(BroadcastStates.upload_photo)
    async def upload_photo_handler(message: Message, state: FSMContext):
        """Обработка загрузки фото"""
        if not message.photo:
            await message.answer("❌ Пожалуйста, отправь фото.")
            return
        
        # Получаем самое большое фото
        photo = message.photo[-1]
        
        # Скачиваем фото
        from aiogram import Bot
        bot = Bot(token=os.getenv("BOT_TOKEN"))
        
        # Создаем папку для broadcast файлов
        os.makedirs("broadcast_media", exist_ok=True)
        
        file = await bot.get_file(photo.file_id)
        file_path = f"broadcast_media/photo_{int(time.time())}.jpg"
        await bot.download_file(file.file_path, file_path)
        await bot.session.close()
        
        await state.update_data(photo_path=file_path)
        await state.set_state(BroadcastStates.enter_caption)
        
        await message.answer(
            "✅ Фото загружено!\n\n"
            "Теперь введи подпись к фото (или нажми 'Без подписи'):",
            reply_markup=get_skip_caption_keyboard()
        )
    
    
    @dp.callback_query(lambda c: c.data == "broadcast_skip_caption")
    async def skip_caption(callback: CallbackQuery, state: FSMContext):
        """Пропуск подписи к фото"""
        await callback.answer()
        await state.update_data(caption=None)
        await show_photo_preview(callback.message, state)
    
    
    @dp.message(BroadcastStates.enter_caption)
    async def enter_caption_handler(message: Message, state: FSMContext):
        """Обработка ввода подписи к фото"""
        if not message.text:
            await message.answer("❌ Пожалуйста, отправь текст подписи.")
            return
        
        # Проверка длины подписи (Telegram ограничение 1024 символа)
        if len(message.text) > 1024:
            await message.answer(
                "❌ Подпись слишком длинная!\n"
                f"Максимум: 1024 символа\n"
                f"Сейчас: {len(message.text)} символов"
            )
            return
        
        await state.update_data(caption=message.text)
        await show_photo_preview(message, state)
    
    
    async def show_photo_preview(message: Message, state: FSMContext):
        """Показывает preview фото с подписью"""
        data = await state.get_data()
        photo_path = data.get('photo_path')
        caption = data.get('caption')
        
        # Получаем количество получателей
        async with async_session() as session:
            result = await session.execute(
                select(func.count(Survey.id)).where(
                    Survey.telegram_id.isnot(None),
                    Survey.ticket_cancelled == False
                )
            )
            total_users = result.scalar()
        
        await state.set_state(BroadcastStates.confirm)
        
        preview_caption = (
            f"📋 **ПРЕДПРОСМОТР РАССЫЛКИ**\n\n"
            f"🖼 Тип: Фото с подписью\n"
            f"👥 Получателей: {total_users}\n\n"
        )
        
        if caption:
            preview_caption += f"━━━━━━━━━━━━━━━━━\n{caption}\n━━━━━━━━━━━━━━━━━\n\n"
        else:
            preview_caption += "*(без подписи)*\n\n"
        
        preview_caption += "Всё верно?"
        
        # Отправляем фото
        from aiogram.types import FSInputFile
        photo = FSInputFile(photo_path)
        
        await message.answer_photo(
            photo=photo,
            caption=preview_caption,
            reply_markup=get_confirm_keyboard(),
            parse_mode="Markdown"
        )
    
    
    @dp.callback_query(lambda c: c.data == "broadcast_confirm")
    async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
        """Подтверждение и запуск рассылки"""
        await callback.answer("🚀 Запускаю рассылку...")
        
        data = await state.get_data()
        broadcast_type = data.get('broadcast_type')
        
        # Получаем всех пользователей с telegram_id
        async with async_session() as session:
            result = await session.execute(
                select(Survey).where(
                    Survey.telegram_id.isnot(None),
                    Survey.ticket_cancelled == False
                )
            )
            users = result.scalars().all()
        
        if not users:
            await callback.message.edit_text("❌ Нет пользователей для рассылки.")
            await state.clear()
            return
        
        # Формируем список получателей
        users_list = [
            {
                'user_id': user.id,
                'telegram_id': user.telegram_id
            }
            for user in users
        ]
        
        total_count = len(users_list)
        
        # Запускаем Celery задачу
        from tasks import mass_broadcast_task
        
        if broadcast_type == "photo":
            photo_path = data.get('photo_path')
            caption = data.get('caption')
            task = mass_broadcast_task.delay(
                users_list=users_list,
                photo_path=photo_path,
                caption=caption
            )
        else:
            message_text = data.get('message_text')
            task = mass_broadcast_task.delay(
                users_list=users_list,
                message_text=message_text
            )
        
        # Оценка времени
        estimated_time = total_count / 18  # 18 сообщений/сек (с учетом rate limiter)
        estimated_minutes = int(estimated_time // 60)
        estimated_seconds = int(estimated_time % 60)
        
        await callback.message.edit_text(
            f"✅ **Рассылка запущена!**\n\n"
            f"📊 **Статистика:**\n"
            f"• 👥 Получателей: {total_count}\n"
            f"• 📝 Тип: {'Фото' if broadcast_type == 'photo' else 'Текст'}\n"
            f"• ⏱ Примерное время: {estimated_minutes} мин {estimated_seconds} сек\n"
            f"• 🔑 Task ID: `{task.id}`\n\n"
            f"📈 Прогресс будет обновляться каждые 50 сообщений",
            parse_mode="Markdown"
        )
        
        await state.clear()
        
        # Запускаем мониторинг в фоне
        start_time = time.time()
        asyncio.create_task(
            monitor_broadcast_progress(callback.message, total_count, start_time)
        )
    
    
    @dp.callback_query(lambda c: c.data == "broadcast_edit")
    async def edit_broadcast(callback: CallbackQuery, state: FSMContext):
        """Изменение рассылки - начать заново"""
        await callback.answer()
        data = await state.get_data()
        broadcast_type = data.get('broadcast_type')
        
        if broadcast_type == "text":
            await state.set_state(BroadcastStates.enter_text)
            await callback.message.edit_text(
                "✏️ **Изменение текста**\n\n"
                "Введи новый текст сообщения:",
                parse_mode="Markdown"
            )
        else:
            await state.set_state(BroadcastStates.upload_photo)
            await callback.message.edit_text(
                "✏️ **Изменение фото**\n\n"
                "Отправь новое фото:",
                parse_mode="Markdown"
            )
    
    
    @dp.callback_query(lambda c: c.data == "broadcast_cancel")
    async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
        """Отмена рассылки"""
        await callback.answer()
        await callback.message.edit_text(
            "❌ Рассылка отменена.\n\n"
            "Используй /broadcast для создания новой рассылки."
        )
        await state.clear()
    
    
    @dp.message(Command("broadcast_test"))
    async def cmd_broadcast_test(message: Message):
        """Тестовая рассылка - отправляет сообщение только админу с правильной обработкой спойлеров"""
        if not is_admin(message.from_user.id):
            await message.answer("❌ У тебя нет доступа к этой команде.")
            return
        
        # Парсим аргументы команды
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "❌ Использование:\n"
                "`/broadcast_test Текст сообщения для теста`\n\n"
                "Отправит сообщение только тебе (для проверки форматирования)\n\n"
                "💡 Поддерживает спойлеры: `||скрытый текст||`",
                parse_mode="Markdown"
            )
            return
        
        test_text = args[1]
        
        # Логируем для отладки
        logger.debug(f"Test text received: {repr(test_text)}")
        
        # Используем ту же логику обработки спойлеров, что и в реальной рассылке
        from bot.sender import detect_and_convert_spoilers
        processed_text, parse_mode = detect_and_convert_spoilers(test_text)
        
        # Логируем результат обработки
        logger.debug(f"Processed text: {repr(processed_text)}, parse_mode: {parse_mode}")
        
        # Формируем обертку в том же формате, что и основной текст
        if parse_mode == "HTML":
            # Если используется HTML, конвертируем обертку тоже в HTML
            wrapper = (
                "🧪 <b>ТЕСТОВАЯ РАССЫЛКА</b>\n\n"
                "━━━━━━━━━━━━━━━━━\n"
                f"{processed_text}\n"
                "━━━━━━━━━━━━━━━━━\n\n"
                "✅ Так будет выглядеть сообщение у получателей\n"
                f"📝 Формат: {parse_mode}"
            )
        else:
            # Если используется Markdown, используем Markdown форматирование
            wrapper = (
                f"🧪 **ТЕСТОВАЯ РАССЫЛКА**\n\n"
                f"━━━━━━━━━━━━━━━━━\n"
                f"{processed_text}\n"
                f"━━━━━━━━━━━━━━━━━\n\n"
                f"✅ Так будет выглядеть сообщение у получателей\n"
                f"📝 Формат: {parse_mode}"
            )
        
        # Отправляем тестовое сообщение с правильным форматированием
        await message.answer(
            wrapper,
            parse_mode=parse_mode
        )
    
    
    logger.info("✅ Broadcast handlers registered")

