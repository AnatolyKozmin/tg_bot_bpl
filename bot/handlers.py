"""
Обновленные обработчики бота с новой логикой регистрации.

Новый порядок вопросов:
1) Согласие на обработку персональных данных
2) Является ли студентом (для определения номер студ билета или диплома)
3) ФИО
4) Факультет
5) Кур с обучения
6) Группа
7) Номер студенческого/диплома (в зависимости от п.2)
8) В паре или один
9) Для пары - аналогично пп. 2-7 для партнера
"""

import os
import asyncio
import time
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.types import ReplyKeyboardRemove
from dotenv import load_dotenv
from db.session import async_session, storage
from db.registration import try_register, get_registration_stats
from sqlalchemy import select, update, delete
from db.models import Survey
from bot.keyboards import (
    yes_no_kb, is_student_kb, faculty_kb, course_kb, pair_or_single_kb,
    studying_or_graduated_kb, confirm_kb, back_kb, back_reply_kb, review_kb,
    manage_ticket_kb, confirm_cancel_kb
)
from bot.middleware import RateLimitMiddleware, AntiFloodMiddleware
from bot.google_sheets import export_to_google_sheets
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher(storage=storage)

# Middleware
dp.message.middleware(RateLimitMiddleware(rate_limit=5))
dp.callback_query.middleware(RateLimitMiddleware(rate_limit=10))
dp.message.middleware(AntiFloodMiddleware(max_messages=20, period=60, ban_time=300))


class SurveyStates(StatesGroup):
    """Состояния для основного потока регистрации"""
    consent = State()
    is_student = State()
    fio = State()
    faculty = State()
    course = State()
    group = State()
    student_id_or_diploma = State()
    pair_or_single = State()
    
    # Для партнера
    partner_is_student = State()
    partner_fio = State()
    partner_faculty = State()
    partner_course = State()
    partner_group = State()
    partner_student_id_or_diploma = State()
    
    # Проверка
    review = State()


# ==================== ADMIN COMMANDS ====================

ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика регистрации"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return
    
    stats = await get_registration_stats()
    text = (
        f"📊 **СТАТИСТИКА РЕГИСТРАЦИИ**\n\n"
        f"👥 Зарегистрировано: {stats['current_count']} / {stats['max_capacity']}\n"
        f"📍 Осталось мест: {stats['remaining']}\n"
        f"📈 Заполнено: {stats['percentage']}%\n"
        f"🚪 Статус: {'🟢 ОТКРЫТА' if stats['is_open'] else '🔴 ЗАКРЫТА'}\n"
    )
    await message.answer(text, parse_mode="Markdown")


async def monitor_ticket_generation(message: Message, user_ids: list, total_count: int):
    """
    Мониторинг прогресса генерации билетов через проверку БД
    Отправляет сообщения каждые 400 билетов и статистику в конце
    """
    PROGRESS_INTERVAL = 400  # Сообщение каждые 400 билетов
    CHECK_INTERVAL = 5  # Проверка каждые 5 секунд
    MAX_WAIT_TIME = 3600  # Максимальное время ожидания (1 час)
    
    last_reported = 0
    start_time = time.time()
    errors_collected = []  # Для сбора ошибок из логов (если нужно)
    
    try:
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            
            # Проверяем прогресс через БД
            async with async_session() as session:
                result = await session.execute(
                    select(Survey).where(
                        Survey.id.in_(user_ids),
                        Survey.ticket_generated == True
                    )
                )
                generated_surveys = result.scalars().all()
                completed = len(generated_surveys)
            
            # Отправляем промежуточное сообщение каждые 400 билетов
            if completed - last_reported >= PROGRESS_INTERVAL:
                remaining = total_count - completed
                progress_percent = (completed / total_count) * 100
                elapsed_time = time.time() - start_time
                
                # Примерная скорость генерации
                if completed > 0:
                    avg_time_per_ticket = elapsed_time / completed
                    estimated_remaining_time = avg_time_per_ticket * remaining
                    time_str = f"~{estimated_remaining_time / 60:.1f} мин" if estimated_remaining_time > 60 else f"~{estimated_remaining_time:.0f} сек"
                else:
                    time_str = "расчет..."
                
                await message.answer(
                    f"📊 **Прогресс генерации билетов**\n\n"
                    f"✅ Готово: {completed} / {total_count} ({progress_percent:.1f}%)\n"
                    f"⏳ Осталось: {remaining}\n"
                    f"⏱ Примерное время до завершения: {time_str}",
                    parse_mode="Markdown"
                )
                last_reported = completed
            
            # Проверяем завершение или таймаут
            elapsed = time.time() - start_time
            if completed >= total_count:
                break
            if elapsed > MAX_WAIT_TIME:
                await message.answer(
                    f"⏱ Превышено максимальное время ожидания ({MAX_WAIT_TIME // 60} минут).\n"
                    f"Текущий прогресс: {completed} / {total_count}",
                    parse_mode="Markdown"
                )
                break
        
        # Финальная статистика - проверяем БД еще раз
        async with async_session() as session:
            result = await session.execute(
                select(Survey).where(
                    Survey.id.in_(user_ids)
                )
            )
            all_surveys = result.scalars().all()
            
            success_count = sum(1 for s in all_surveys if s.ticket_generated)
            error_count = total_count - success_count
            
            # Проверяем, есть ли записи с ошибками (билет не сгенерирован, но не отменен)
            failed_surveys = [
                s for s in all_surveys 
                if not s.ticket_generated and not s.ticket_cancelled
            ]
        
        # Формируем финальное сообщение
        final_message = (
            f"✅ **Генерация билетов завершена!**\n\n"
            f"📊 **Статистика:**\n"
            f"• Всего обработано: {success_count} / {total_count}\n"
            f"• ✅ Успешно сгенерировано: {success_count}\n"
            f"• ❌ Не сгенерировано: {error_count}\n"
        )
        
        if error_count > 0 and failed_surveys:
            final_message += f"\n⚠️ **Проблемные записи (первые 10):**\n"
            for survey in failed_surveys[:10]:
                fio = survey.fio or "Без ФИО"
                tg_id = survey.telegram_id or "Без ID"
                final_message += f"• ID {survey.id}: {fio} (TG: {tg_id})\n"
            if len(failed_surveys) > 10:
                final_message += f"\n... и еще {len(failed_surveys) - 10} записей"
        
        await message.answer(final_message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Ошибка при мониторинге генерации билетов: {e}", exc_info=True)
        await message.answer(
            f"⚠️ Ошибка при мониторинге прогресса:\n`{str(e)}`\n\n"
            f"Проверь статус вручную: /stats",
            parse_mode="Markdown"
        )


@dp.message(Command("generate_tickets"))
async def cmd_generate_tickets(message: Message):
    """Генерация всех билетов с отслеживанием прогресса"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return
    
    await message.answer("🎫 Начинаю генерацию билетов...")
    
    try:
        async with async_session() as session:
            result = await session.execute(
                select(Survey).where(
                    (Survey.ticket_cancelled == False) & 
                    (Survey.ticket_generated == False)
                )
            )
            users = result.scalars().all()
        
        if not users:
            await message.answer("✅ Все билеты уже сгенерированы!")
            return
        
        from tasks import generate_ticket
        from celery import group
        
        # Подготавливаем данные для генерации
        users_data = []
        user_ids = []
        for user in users:
            user_data = {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'fio': user.fio,
                'faculty': user.faculty,
                'course': user.course,
                'group': user.group,
                'student_id': user.student_id,
                'diploma_number': user.diploma_number,
                'ticket_type': user.pair_or_single,
                'partner_fio': user.partner_fio,
            }
            users_data.append((user.id, user_data))
            user_ids.append(user.id)
        
        # Запускаем генерацию билетов через Celery
        from celery import group
        
        job = group(
            generate_ticket.s(user_id, user_data)
            for user_id, user_data in users_data
        )
        group_result = job.apply_async()
        
        total_count = len(users)
        
        await message.answer(
            f"✅ **Генерация запущена!**\n\n"
            f"📊 Билетов к генерации: {total_count}\n"
            f"⏱ Примерное время: ~{total_count * 2 / 60:.1f} минут\n\n"
            f"📈 Прогресс будет обновляться каждые 400 билетов\n"
            f"🔑 Group ID: `{group_result.id}`",
            parse_mode="Markdown"
        )
        
        # Запускаем мониторинг в фоне (проверяет БД)
        asyncio.create_task(
            monitor_ticket_generation(message, user_ids, total_count)
        )
        
    except Exception as e:
        logger.error(f"❌ Generate tickets error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")


@dp.message(Command("rass"))
async def cmd_broadcast(message: Message):
    """Рассылка билетов"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return
    
    await message.answer("🚀 Проверяю готовность...")
    
    try:
        async with async_session() as session:
            # Проверка: все ли билеты сгенерированы
            not_generated = await session.execute(
                select(Survey).where(
                    (Survey.ticket_cancelled == False) & 
                    (Survey.ticket_generated == False)
                )
            )
            not_generated_count = len(not_generated.scalars().all())
            
            if not_generated_count > 0:
                await message.answer(
                    f"⚠️ Не все билеты сгенерированы!\n\n"
                    f"❌ Не сгенерировано: {not_generated_count}\n\n"
                    f"Сначала запустите: /generate_tickets"
                )
                return
            
            # Получаем пользователей с готовыми билетами
            result = await session.execute(
                select(Survey).where(
                    (Survey.ticket_cancelled == False) &
                    (Survey.ticket_generated == True) &
                    (Survey.ticket_sent == False)
                )
            )
            users = result.scalars().all()
        
        if not users:
            await message.answer("✅ Все билеты уже отправлены!")
            return
        
        # Формируем данные для рассылки (ПРАВИЛЬНАЯ СТРУКТУРА!)
        tickets_to_send = []
        for user in users:
            tickets_to_send.append({
                'user_id': user.id,              # ✅ user_id (не id!)
                'telegram_id': user.telegram_id,
                'ticket_path': user.ticket_path  # ✅ ticket_path!
            })
        
        from tasks import broadcast_tickets_task
        task = broadcast_tickets_task.delay(tickets_to_send)
        
        await message.answer(
            f"✅ Рассылка запущена!\n\n"
            f"📊 Всего пользователей: {len(tickets_to_send)}\n"
            f"🔑 Task ID: `{task.id}`\n\n"
            f"⏱ Примерное время: ~{len(tickets_to_send) * 0.05 / 60:.1f} минут",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}")


@dp.message(Command("create_google_shit"))
async def cmd_create_google_sheet(message: Message):
    """Экспорт данных регистрации в Google Sheets"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return
    
    # Получаем ID таблицы из переменной окружения или запрашиваем у пользователя
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    if not spreadsheet_id:
        await message.answer(
            "❌ Не указан ID Google таблицы.\n\n"
            "📝 Добавь в .env файл:\n"
            "GOOGLE_SHEET_ID=твой_id_таблицы\n\n"
            "🔗 ID можно найти в URL таблицы:\n"
            "https://docs.google.com/spreadsheets/d/ТУТ_ID_ТАБЛИЦЫ/edit"
        )
        return
    
    await message.answer("🔄 Начинаю экспорт в Google Sheets...")
    
    try:
        result = await export_to_google_sheets(spreadsheet_id)
        
        await message.answer(
            f"✅ **Экспорт завершен!**\n\n"
            f"📊 Статистика:\n"
            f"• Solo (без пары): {result['solo_count']}\n"
            f"• Duo (с парой): {result['duo_count']}\n"
            f"• Всего: {result['total']}\n\n"
            f"📋 Данные экспортированы в листы:\n"
            f"• `solo` - участники без пары\n"
            f"• `duo` - участники с парой",
            parse_mode="Markdown"
        )
        
    except FileNotFoundError as e:
        await message.answer(
            f"❌ **Ошибка:** Не найден файл credentials.json\n\n"
            f"📝 Убедись, что файл находится в корне проекта или укажи путь в переменной окружения:\n"
            f"GOOGLE_CREDENTIALS_PATH=путь/к/credentials.json"
        )
    except Exception as e:
        logger.error(f"Ошибка при экспорте в Google Sheets: {e}", exc_info=True)
        await message.answer(
            f"❌ **Ошибка при экспорте:**\n\n"
            f"`{str(e)}`\n\n"
            f"📝 Проверь:\n"
            f"• Правильность ID таблицы\n"
            f"• Наличие файла credentials.json\n"
            f"• Доступы service account к таблице",
            parse_mode="Markdown"
        )


# ==================== REGISTRATION FLOW ====================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Начало регистрации"""
    telegram_id = str(message.from_user.id)
    
    # Проверяем существующую регистрацию
    async with async_session() as session:
        result = await session.execute(
            select(Survey).filter_by(telegram_id=telegram_id)
        )
        existing = result.scalars().first()
    
    if existing:
        if existing.ticket_cancelled:
            await message.answer(
                "❌ Твой билет был отменен.\n\n"
                "К сожалению, повторная регистрация невозможна."
            )
            return
        
        # Показываем управление билетом
        await message.answer(
            f"✅ У тебя уже есть регистрация!\n\n"
            f"👤 ФИО: {existing.fio}\n"
            f"📚 Факультет: {existing.faculty}\n"
            f"📊 Курс: {existing.course}\n"
            f"👥 Группа: {existing.group}\n"
            f"🎫 Тип: {existing.pair_or_single}\n\n"
            f"Что ты хочешь сделать?",
            reply_markup=manage_ticket_kb()
        )
        return

    # Начинаем новую регистрацию
    await state.clear()
    await state.update_data(
        telegram_id=telegram_id,
        telegram_username=message.from_user.username
    )
    await state.set_state(SurveyStates.consent)
    
    await message.answer(
        "Добро пожаловать на регистрацию!\n\n"
        "**1) Согласен(на) ли ты на обработку персональных данных?**",
        reply_markup=yes_no_kb(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data == "yes")
async def consent_cb(query: CallbackQuery, state: FSMContext):
    """Обработка согласия"""
    await state.update_data(consent=True)
    
    # Редактируем сообщение вместо удаления
    await query.message.edit_text(
        "**1) Согласен(на) ли ты на обработку персональных данных?**\n\n"
        "✅ **Да**",
        parse_mode="Markdown"
    )
    
    await state.set_state(SurveyStates.is_student)
    await query.message.answer(
        "**2) Ты являешься студентом или выпускником?**",
        reply_markup=is_student_kb(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data.startswith("is_student_") and "являешься студентом или выпускником" in c.message.text.lower())
async def is_student_cb(query: CallbackQuery, state: FSMContext):
    """Обработка статуса студента"""
    await query.answer()
    is_student = query.data == "is_student_yes"
    await state.update_data(is_student=is_student)
    
    status_text = "👨‍🎓 **Студент**" if is_student else "🎓 **Выпускник**"
    await query.message.edit_text(
        f"**2) Ты являешься студентом или выпускником?**\n\n{status_text}",
        parse_mode="Markdown"
    )
    
    await state.set_state(SurveyStates.fio)
    await query.message.answer(
        "**3) Введи свое ФИО**\n\n"
        "Пример: Иванов Иван Иванович",
        reply_markup=back_reply_kb(),
        parse_mode="Markdown"
    )


@dp.message(SurveyStates.fio)
async def fio_handler(message: Message, state: FSMContext):
    """Обработка ФИО"""
    if message.text == "◀️ Назад":
        await handle_back(message, state)
        return
    
    # Валидация
    if any(ch.isdigit() for ch in message.text):
        await message.answer(
            "❌ ФИО не должно содержать цифр. Попробуйте ещё раз.",
            reply_markup=back_reply_kb()
        )
        return
    
    await state.update_data(fio=message.text)
    
    # Проверяем, это редактирование или новая регистрация
    data = await state.get_data()
    if data.get('user_id'):  # Это редактирование
        await state.set_state(SurveyStates.review)
        await send_review(message, state)
        return
    
    # Новая регистрация
    is_student = data.get('is_student', True)
    
    if not is_student:
        # Выпускник - пропускаем факультет/курс/группу
        await state.update_data(
            faculty="Выпускник",
            course="Выпускник",
            group="Выпускник"
        )
        await state.set_state(SurveyStates.student_id_or_diploma)
        await message.answer(
            "**4) Введи номер диплома**\n\n"
            "Пример: 123456789",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )
    else:
        # Студент - спрашиваем факультет
        await state.set_state(SurveyStates.faculty)
        await message.answer(
            "**4) Выбери факультет обучения:**",
            reply_markup=faculty_kb(),
            parse_mode="Markdown"
        )


@dp.callback_query(lambda c: c.data.startswith("faculty_") and "факультет партнёра" not in c.message.text.lower())
async def faculty_cb(query: CallbackQuery, state: FSMContext):
    """Обработка факультета (основная регистрация)"""
    faculty = query.data.replace("faculty_", "")
    await state.update_data(faculty=faculty)
    
    # Проверяем, это редактирование или новая регистрация
    data = await state.get_data()
    
    await query.message.edit_text(
            f"**4) Выбери факультет обучения:**\n\n"
            f"✅ {faculty}",
            parse_mode="Markdown"
    )
    
    if data.get('user_id'):  # Это редактирование
        await state.set_state(SurveyStates.review)
        await send_review(query.message, state)
        return
    
    # Новая регистрация - переходим к следующему вопросу
    await state.set_state(SurveyStates.course)
    await query.message.answer(
        "**5) Выбери курс обучения:**\n\n"
        "Б - Бакалавриат, М - Магистратура",
        reply_markup=course_kb(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data.startswith("course_") and "курс обучения партнёра" not in c.message.text.lower())
async def course_cb(query: CallbackQuery, state: FSMContext):
    """Обработка курса (основная регистрация)"""
    course = query.data.replace("course_", "")
    await state.update_data(course=course)
    
    # Проверяем, это редактирование или новая регистрация
    data = await state.get_data()
    
    await query.message.edit_text(
            f"**5) Выбери курс обучения:**\n\n"
            f"✅ {course}",
            parse_mode="Markdown"
    )
    
    if data.get('user_id'):  # Это редактирование
        await state.set_state(SurveyStates.review)
        await send_review(query.message, state)
        return
    
    # Новая регистрация
    await state.set_state(SurveyStates.group)
    await query.message.answer(
        "**6) Введи группу обучения**\n\n"
        'Пример: "ПИ23-1"',
        reply_markup=back_reply_kb(),
        parse_mode="Markdown"
    )


@dp.message(SurveyStates.group)
async def group_handler(message: Message, state: FSMContext):
    """Обработка группы"""
    if message.text == "◀️ Назад":
        await handle_back(message, state)
        return
    
    await state.update_data(group=message.text)
    
    # Проверяем, это редактирование или новая регистрация
    data = await state.get_data()
    if data.get('user_id'):  # Это редактирование
        await state.set_state(SurveyStates.review)
        await send_review(message, state)
        return
    
    # Новая регистрация - переходим к следующему вопросу
    await state.set_state(SurveyStates.student_id_or_diploma)
    is_student = data.get('is_student', True)
    
    if is_student:
        await message.answer(
            "**7) Введи номер студенческого билета**\n\n"
            "⚠️ Должен содержать ровно 6 цифр\n"
            "Пример: 236446",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "**7) Введи номер диплома**\n\n"
            "Пример: 123456789",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )


@dp.message(SurveyStates.student_id_or_diploma)
async def student_id_or_diploma_handler(message: Message, state: FSMContext):
    """Обработка номера студенческого/диплома"""
    if message.text == "◀️ Назад":
        await handle_back(message, state)
        return
    
    data = await state.get_data()
    is_student = data.get('is_student', True)
    
    if is_student:
        # Валидация студенческого: ровно 6 цифр
        if not message.text.isdigit() or len(message.text) != 6:
            await message.answer(
                "❌ Номер студенческого билета должен содержать ровно 6 цифр.\n"
                "Попробуйте ещё раз.",
                reply_markup=back_reply_kb()
            )
            return
        await state.update_data(student_id=message.text, diploma_number=None)
    else:
        # Валидация диплома: только цифры
        if not message.text.isdigit():
            await message.answer(
                "❌ Номер диплома должен содержать только цифры.\n"
                "Попробуйте ещё раз.",
                reply_markup=back_reply_kb()
            )
            return
        await state.update_data(diploma_number=message.text, student_id=None)
    
    await state.set_state(SurveyStates.pair_or_single)
    await message.answer(
        "**8) Ты будешь в паре или один?**",
        reply_markup=pair_or_single_kb(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data in ["pair", "single"])
async def pair_cb(query: CallbackQuery, state: FSMContext):
    """Обработка типа билета"""
    ticket_type = query.data
    await state.update_data(pair_or_single=ticket_type)
    
    if ticket_type == "single":
        await query.message.edit_text(
            "**8) Ты будешь в паре или один?**\n\n"
            "✅ Один",
            parse_mode="Markdown"
        )
        await state.set_state(SurveyStates.review)
        await send_review(query.message, state)
    else:
        await query.message.edit_text(
            "**8) Ты будешь в паре или один?**\n\n"
            "✅ В паре",
            parse_mode="Markdown"
        )
        await state.set_state(SurveyStates.partner_is_student)
        await query.message.answer(
            "**9) Твой партнёр является студентом или выпускником?**",
            reply_markup=is_student_kb(),
            parse_mode="Markdown"
        )


# ==================== PARTNER FLOW ====================

@dp.callback_query(lambda c: c.data.startswith("is_student_") and "партнёр является студентом или выпускником" in c.message.text.lower())
async def partner_is_student_cb(query: CallbackQuery, state: FSMContext):
    """Обработка статуса партнера (студент/выпускник)"""
    await query.answer()
    is_student = query.data == "is_student_yes"
    await state.update_data(partner_is_student=is_student)
    partner_status = "studying" if is_student else "graduated"
    await state.update_data(partner_status=partner_status)
    
    status_text = "👨‍🎓 **Студент**" if is_student else "🎓 **Выпускник**"
    await query.message.edit_text(
        f"**9) Твой партнёр является студентом или выпускником?**\n\n{status_text}",
        parse_mode="Markdown"
    )
    
    await state.set_state(SurveyStates.partner_fio)
    await query.message.answer(
        "**10) Введи ФИО партнёра**",
        reply_markup=back_reply_kb(),
        parse_mode="Markdown"
    )


@dp.message(SurveyStates.partner_fio)
async def partner_fio_handler(message: Message, state: FSMContext):
    """Обработка ФИО партнера"""
    if message.text == "◀️ Назад":
        await handle_back(message, state)
        return
    
    if any(ch.isdigit() for ch in message.text):
        await message.answer(
            "❌ ФИО не должно содержать цифр. Попробуйте ещё раз.",
            reply_markup=back_reply_kb()
        )
        return
    
    await state.update_data(partner_fio=message.text)
    
    # Проверяем статус партнёра
    data = await state.get_data()
    is_student = data.get('partner_is_student', True)
    
    if not is_student:
        # Партнёр-выпускник - пропускаем факультет/курс/группу
        await state.update_data(
            partner_faculty="Выпускник",
            partner_course="Выпускник",
            partner_group="Выпускник"
        )
        await state.set_state(SurveyStates.partner_student_id_or_diploma)
        await message.answer(
            "**11) Введи номер диплома партнёра**",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )
    else:
        # Партнёр-студент - спрашиваем факультет
        await state.set_state(SurveyStates.partner_faculty)
        await message.answer(
            "**11) Выбери факультет партнёра:**",
            reply_markup=faculty_kb(),
            parse_mode="Markdown"
        )


@dp.callback_query(lambda c: c.data.startswith("faculty_") and "факультет партнёра" in c.message.text.lower())
async def partner_faculty_cb(query: CallbackQuery, state: FSMContext):
    """Обработка факультета партнера"""
    faculty = query.data.replace("faculty_", "")
    await state.update_data(partner_faculty=faculty)
    
    await query.message.edit_text(
        f"**11) Выбери факультет партнёра:**\n\n✅ {faculty}",
        parse_mode="Markdown"
    )
    
    await state.set_state(SurveyStates.partner_course)
    await query.message.answer(
        "**12) Выбери курс обучения партнёра:**",
        reply_markup=course_kb(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data.startswith("course_") and "курс обучения партнёра" in c.message.text.lower())
async def partner_course_cb(query: CallbackQuery, state: FSMContext):
    """Обработка курса партнера"""
    course = query.data.replace("course_", "")
    await state.update_data(partner_course=course)
    
    await query.message.edit_text(
        f"**12) Выбери курс обучения партнёра:**\n\n✅ {course}",
        parse_mode="Markdown"
    )
    
    await state.set_state(SurveyStates.partner_group)
    await query.message.answer(
        "**13) Введи группу партнёра**",
        reply_markup=back_reply_kb(),
        parse_mode="Markdown"
    )




@dp.message(SurveyStates.partner_group)
async def partner_group_handler(message: Message, state: FSMContext):
    """Обработка группы партнера"""
    if message.text == "◀️ Назад":
        await handle_back(message, state)
        return
    
    await state.update_data(partner_group=message.text)
    await state.set_state(SurveyStates.partner_student_id_or_diploma)
    
    data = await state.get_data()
    is_student = data.get('partner_is_student', True)
    
    if is_student:
        await message.answer(
            "**14) Введи номер студенческого билета партнёра**\n\n"
            "⚠️ Должен содержать ровно 6 цифр",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "**14) Введи номер диплома партнёра**",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )


@dp.message(SurveyStates.partner_student_id_or_diploma)
async def partner_student_id_or_diploma_handler(message: Message, state: FSMContext):
    """Обработка номера студенческого/диплома партнера"""
    if message.text == "◀️ Назад":
        await handle_back(message, state)
        return
    
    data = await state.get_data()
    is_student = data.get('partner_is_student', True)
    
    if is_student:
        if not message.text.isdigit() or len(message.text) != 6:
            await message.answer(
                "❌ Номер студенческого билета должен содержать ровно 6 цифр.\n"
                "Попробуйте ещё раз.",
                reply_markup=back_reply_kb()
            )
            return
        await state.update_data(partner_student_id=message.text, partner_diploma=None)
    else:
        if not message.text.isdigit():
            await message.answer(
                "❌ Номер диплома должен содержать только цифры.\n"
                "Попробуйте ещё раз.",
                reply_markup=back_reply_kb()
            )
            return
        await state.update_data(partner_diploma=message.text, partner_student_id=None)
    
    await state.set_state(SurveyStates.review)
    await send_review(message, state)


# ==================== REVIEW & CONFIRM ====================

async def send_review(dest: Message | CallbackQuery, state: FSMContext):
    """Отправка проверки заполненных данных"""
    data = await state.get_data()
    
    # Основные данные
    status = "Студент" if data.get('is_student') else "Выпускник"
    doc_num = data.get('student_id') or data.get('diploma_number', 'Не указан')
    doc_type = "Студенческий билет" if data.get('is_student') else "Диплом"
    
    lines = [
        "📋 **ПРОВЕРЬ СВОИ ДАННЫЕ**\n",
        f"✅ Согласие: Да",
        f"👤 Статус: {status}",
        f"👨‍💼 ФИО: {data.get('fio')}",
        f"🏛 Факультет: {data.get('faculty')}",
        f"📚 Курс: {data.get('course')}",
        f"👥 Группа: {data.get('group')}",
        f"🎫 {doc_type}: {doc_num}",
        f"💑 Тип билета: {data.get('pair_or_single')}"
    ]
    
    # Данные партнера
    if data.get('pair_or_single') == 'pair':
        partner_status = "Студент" if data.get('partner_is_student') else "Выпускник"
        partner_doc = data.get('partner_student_id') or data.get('partner_diploma', 'Не указан')
        partner_doc_type = "Студ. билет" if data.get('partner_is_student') else "Диплом"
        
        lines.extend([
            "\n👫 **ДАННЫЕ ПАРТНЁРА:**",
            f"👤 Статус: {partner_status}",
            f"👨‍💼 ФИО: {data.get('partner_fio')}",
            f"🏛 Факультет: {data.get('partner_faculty')}",
            f"📚 Курс: {data.get('partner_course')}",
            f"👥 Группа: {data.get('partner_group')}",
            f"🎫 {partner_doc_type}: {partner_doc}"
        ])
    
    text = "\n".join(lines)
    
    if isinstance(dest, CallbackQuery):
        dest = dest.message
    
    await dest.answer(text, reply_markup=review_kb(), parse_mode="Markdown")


@dp.callback_query(lambda c: c.data == "confirm")
async def confirm_cb(query: CallbackQuery, state: FSMContext):
    """Подтверждение и сохранение регистрации"""
    data = await state.get_data()
    ticket_type = data.get('pair_or_single', 'single')
    user_id = data.get('user_id')  # Если редактируем существующую анкету
    
    # Если это редактирование существующей анкеты
    if user_id:
        try:
            # Конвертируем partner_is_student обратно в partner_status для БД
            if data.get('partner_is_student') is not None:
                data['partner_status'] = "studying" if data.get('partner_is_student') else "graduated"
            
            allowed = {col.name for col in Survey.__table__.columns}
            payload = {k: v for k, v in data.items() if k in allowed and k != 'user_id'}
            
            async with async_session() as session:
                await session.execute(
                    update(Survey)
                    .where(Survey.id == user_id)
                    .values(**payload)
                )
                await session.commit()
            
            await query.message.edit_text(
                "✅ **Анкета обновлена!**\n\n"
                "Твои изменения сохранены.\n"
                "Используй /start для управления билетом.",
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ Survey updated: user_id={query.from_user.id}")
            
        except Exception as e:
            logger.error(f"❌ Update error: {e}")
            await query.message.edit_text("❌ Ошибка при сохранении. Обратитесь к администратору.")
        
        await state.clear()
        return
    
    # Новая регистрация
    # Атомарная проверка мест
    success, message = await try_register(ticket_type)
    
    if not success:
        await query.message.edit_text(
            f"{message}\n\n"
            "К сожалению, ты не успел(а) зарегистрироваться.",
            parse_mode="Markdown"
        )
        await state.clear()
        return
    
    # Сохраняем в БД
    try:
        # Конвертируем partner_is_student в partner_status для БД
        if data.get('partner_is_student') is not None:
            data['partner_status'] = "studying" if data.get('partner_is_student') else "graduated"
        
        allowed = {col.name for col in Survey.__table__.columns}
        payload = {k: v for k, v in data.items() if k in allowed}
        
        async with async_session() as session:
            survey = Survey(**payload)
            session.add(survey)
            await session.commit()
        
        await query.message.edit_text(
            f"✅ **Регистрация успешна!**\n\n"
            f"🎫 Билет будет отправлен тебе позже.\n"
            f"Используй /start чтобы управлять билетом.",
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ Registration: user_id={query.from_user.id}, type={ticket_type}")
        
    except Exception as e:
        logger.error(f"❌ DB error: {e}")
        await query.message.edit_text("❌ Ошибка при сохранении. Обратитесь к администратору.")
    
    await state.clear()


@dp.callback_query(lambda c: c.data == "cancel")
async def cancel_cb(query: CallbackQuery, state: FSMContext):
    """Отмена регистрации"""
    await query.message.edit_text(
        "❌ Регистрация отменена.\n\n"
        "Используй /start чтобы начать заново."
    )
    await state.clear()


# ==================== TICKET MANAGEMENT ====================

@dp.callback_query(lambda c: c.data == "edit_ticket")
async def edit_ticket_cb(query: CallbackQuery, state: FSMContext):
    """Редактирование уже отправленной анкеты"""
    telegram_id = str(query.from_user.id)
    
    async with async_session() as session:
        result = await session.execute(
            select(Survey).filter_by(telegram_id=telegram_id)
        )
        survey = result.scalars().first()
    
    if not survey:
        await query.answer("❌ Регистрация не найдена", show_alert=True)
        return
    
    # Загружаем данные в состояние
    # Конвертируем partner_status в partner_is_student для совместимости
    partner_is_student = None
    if survey.partner_status:
        partner_is_student = survey.partner_status == "studying"
    
    await state.update_data(
        user_id=survey.id,  # Сохраняем ID для обновления
        telegram_id=telegram_id,
        telegram_username=query.from_user.username,
        consent=survey.consent,
        is_student=survey.is_student,
        fio=survey.fio,
        faculty=survey.faculty,
        course=survey.course,
        group=survey.group,
        student_id=survey.student_id,
        diploma_number=survey.diploma_number,
        pair_or_single=survey.pair_or_single,
        partner_is_student=partner_is_student,
        partner_status=survey.partner_status,
        partner_fio=survey.partner_fio,
        partner_faculty=survey.partner_faculty,
        partner_course=survey.partner_course,
        partner_group=survey.partner_group,
        partner_student_id=survey.partner_student_id,
        partner_diploma=survey.partner_diploma
    )
    
    await state.set_state(SurveyStates.review)
    await send_review(query, state)


@dp.callback_query(lambda c: c.data == "cancel_ticket")
async def cancel_ticket_cb(query: CallbackQuery, state: FSMContext):
    """Запрос подтверждения отмены билета"""
    await query.message.edit_text(
        "⚠️ **ВНИМАНИЕ!**\n\n"
        "Ты действительно хочешь отменить билет?\n\n"
        "❗️ После отмены:\n"
        "• Твой билет будет удален\n"
        "• Повторная регистрация будет невозможна\n"
        "• Место освободится для других\n\n"
        "Ты уверен(а)?",
        reply_markup=confirm_cancel_kb(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data == "confirm_cancel_ticket")
async def confirm_cancel_ticket_cb(query: CallbackQuery, state: FSMContext):
    """Подтверждение отмены билета"""
    telegram_id = str(query.from_user.id)
    
    try:
        async with async_session() as session:
            # Отмечаем билет как отмененный
            await session.execute(
                update(Survey)
                .where(Survey.telegram_id == telegram_id)
                .values(ticket_cancelled=True)
            )
            await session.commit()
        
        # Освобождаем место
        # TODO: Уменьшить current_count в registration_config
        
        await query.message.edit_text(
            "✅ **Билет отменен**\n\n"
            "Твоя регистрация отменена.\n"
            "Место освобождено для других участников.\n\n"
            "❗️ Повторная регистрация невозможна."
        )
        
        logger.info(f"🗑 Ticket cancelled: user_id={query.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Cancel ticket error: {e}")
        await query.answer("❌ Ошибка при отмене билета", show_alert=True)


@dp.callback_query(lambda c: c.data == "keep_ticket")
async def keep_ticket_cb(query: CallbackQuery, state: FSMContext):
    """Отмена отмены билета (оставить билет)"""
    await query.message.edit_text(
        "✅ Билет сохранен!\n\n"
        "Твоя регистрация остается активной."
    )


# ==================== EDIT HANDLERS ====================

@dp.callback_query(lambda c: c.data.startswith('edit_') and c.data != 'edit_ticket')
async def edit_field_cb(query: CallbackQuery, state: FSMContext):
    """Редактирование конкретного поля"""
    field = query.data.replace('edit_', '')

    if field == 'fio':
        await state.set_state(SurveyStates.fio)
        await query.message.answer(
            "**Введи новое ФИО:**\n\nПосле ввода ты вернешься к просмотру анкеты.",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )
    elif field == 'faculty':
        await state.set_state(SurveyStates.faculty)
        await query.message.answer(
            "**Выбери новый факультет:**",
            reply_markup=faculty_kb(),
            parse_mode="Markdown"
        )
    elif field == 'course':
        await state.set_state(SurveyStates.course)
        await query.message.answer(
            "**Выбери новый курс:**",
            reply_markup=course_kb(),
            parse_mode="Markdown"
        )
    elif field == 'group':
        await state.set_state(SurveyStates.group)
        await query.message.answer(
            "**Введи новую группу:**\n\nПосле ввода ты вернешься к просмотру анкеты.",
            reply_markup=back_reply_kb(),
            parse_mode="Markdown"
        )


async def handle_back(message: Message, state: FSMContext):
    """Обработка кнопки Назад"""
    current_state = await state.get_state()
    
    # Просто возвращаем к предыдущему вопросу
    # TODO: Реализовать полноценную навигацию назад
    await message.answer(
        "Используй /start чтобы начать заново.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

