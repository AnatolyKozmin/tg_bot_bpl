import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from dotenv import load_dotenv
from db.session import async_session, storage
from db.registration import try_register, get_registration_stats, initialize_registration_config
from sqlalchemy import select
from db.models import Survey, Base
from bot.keyboards import (yes_no_kb, pair_or_single_kb, studying_or_graduated_kb,
                           confirm_kb, back_kb, back_reply_kb, review_kb)
from bot.middleware import RateLimitMiddleware, AntiFloodMiddleware
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(TOKEN)
# Используем Redis storage вместо MemoryStorage
dp = Dispatcher(storage=storage)

# Подключаем middleware для защиты от спама
dp.message.middleware(RateLimitMiddleware(rate_limit=5))
dp.callback_query.middleware(RateLimitMiddleware(rate_limit=10))
dp.message.middleware(AntiFloodMiddleware(max_messages=20, period=60, ban_time=300))

class SurveyStates(StatesGroup):
    consent = State()
    fio = State()
    group = State()
    student_id = State()
    pair_or_single = State()
    partner_status = State()
    partner_fio = State()
    partner_group = State()
    partner_student_id = State()
    partner_diploma = State()
    review = State()


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # prevent re-registration if user already submitted
    telegram_id = str(message.from_user.id)
    async with async_session() as session:
        q = await session.execute(select(Survey).filter_by(telegram_id=telegram_id))
        existing = q.scalars().first()
    if existing:
        await message.answer("Вы уже заполнили анкету — повторная регистрация запрещена. Если нужно изменить данные, обратитесь к администратору.")
        return

    await state.clear()
    # initialize history stack and store telegram identifiers
    await state.update_data(_history=[], telegram_id=telegram_id, telegram_username=message.from_user.username)
    await state.set_state(SurveyStates.consent)
    await message.answer("1) Согласны ли вы со сбором персональных данных?", reply_markup=yes_no_kb())


@dp.callback_query(lambda c: c.data == "yes")
async def consent_cb(query: CallbackQuery, state: FSMContext):
    # only positive consent is available in the keyboard
    await state.update_data(consent=True)
    # push previous state
    data = await state.get_data()
    history = data.get("_history", [])
    history.append(SurveyStates.consent.state)
    await state.update_data(_history=history)
    await state.set_state(SurveyStates.fio)
    await query.message.edit_text("2) Введите своё ФИО", reply_markup=back_kb())


@dp.message(lambda m: True)
async def generic_message_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    current = await state.get_state()
    # Simple routing by state
    # text "◀️ Назад" pressed (reply keyboard)
    if message.text == "◀️ Назад":
        await handle_back(message, state)
        return

    if current == SurveyStates.fio:
        # validate fio: no digits
        if any(ch.isdigit() for ch in message.text):
            await message.answer("ФИО не должно содержать цифр. Попробуйте ещё раз.", reply_markup=back_reply_kb())
            return
        await state.update_data(fio=message.text)
        # push history
        history = data.get("_history", [])
        history.append(SurveyStates.fio.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.group)
        await message.answer("3) Введите группу обучения (пример ПИ23-1)", reply_markup=back_reply_kb())
    elif current == SurveyStates.group:
        await state.update_data(group=message.text)
        history = data.get("_history", [])
        history.append(SurveyStates.group.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.student_id)
        await message.answer("4) Введите номер студенческого билета (пример 236446)", reply_markup=back_reply_kb())
    elif current == SurveyStates.student_id:
        # validate digits only
        if not message.text.isdigit():
            await message.answer("Номер студенческого должен содержать только цифры. Попробуйте ещё раз.", reply_markup=back_reply_kb())
            return
        await state.update_data(student_id=message.text)
        history = data.get("_history", [])
        history.append(SurveyStates.student_id.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.pair_or_single)
        await message.answer("5) Вы будете в паре или один?", reply_markup=pair_or_single_kb())
    elif current == SurveyStates.partner_fio:
        if any(ch.isdigit() for ch in message.text):
            await message.answer("ФИО партнёра не должно содержать цифр. Попробуйте ещё раз.", reply_markup=back_reply_kb())
            return
        await state.update_data(partner_fio=message.text)
        history = data.get("_history", [])
        history.append(SurveyStates.partner_fio.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.partner_group)
        await message.answer("Введите группу партнёра", reply_markup=back_reply_kb())
    elif current == SurveyStates.partner_group:
        await state.update_data(partner_group=message.text)
        history = data.get("_history", [])
        history.append(SurveyStates.partner_group.state)
        await state.update_data(_history=history)
        # next depends on partner_status
        partner_status = data.get('partner_status')
        if partner_status == 'studying':
            await state.set_state(SurveyStates.partner_student_id)
            await message.answer("Введите номер студенческого билета партнёра", reply_markup=back_reply_kb())
        else:
            await state.set_state(SurveyStates.partner_diploma)
            await message.answer("Введите номер диплома партнёра", reply_markup=back_reply_kb())
    elif current == SurveyStates.partner_student_id:
        if not message.text.isdigit():
            await message.answer("Номер студенческого партнёра должен содержать только цифры. Попробуйте ещё раз.", reply_markup=back_reply_kb())
            return
        await state.update_data(partner_student_id=message.text)
        history = data.get("_history", [])
        history.append(SurveyStates.partner_student_id.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.review)
        await send_review(message, state)
    elif current == SurveyStates.partner_diploma:
        if not message.text.isdigit():
            await message.answer("Номер диплома должен содержать только цифры. Попробуйте ещё раз.", reply_markup=back_reply_kb())
            return
        await state.update_data(partner_diploma=message.text)
        history = data.get("_history", [])
        history.append(SurveyStates.partner_diploma.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.review)
        await send_review(message, state)
    else:
        await message.answer("Нажмите /start чтобы начать анкету")


@dp.callback_query(lambda c: c.data == "pair" or c.data == "single")
async def pair_cb(query: CallbackQuery, state: FSMContext):
    if query.data == "single":
        await state.update_data(pair_or_single="single")
        data = await state.get_data()
        history = data.get("_history", [])
        history.append(SurveyStates.pair_or_single.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.review)
        await query.message.edit_text("Вы выбрали — Один")
        await send_review(query.message, state)
        return
    await state.update_data(pair_or_single="pair")
    data = await state.get_data()
    history = data.get("_history", [])
    history.append(SurveyStates.pair_or_single.state)
    await state.update_data(_history=history)
    await state.set_state(SurveyStates.partner_status)
    await query.message.edit_text("6) Ваш парнёр учится или уже закончил Финансовый университет ?", reply_markup=studying_or_graduated_kb())


@dp.callback_query(lambda c: c.data in ["studying", "graduated"])
async def partner_status_cb(query: CallbackQuery, state: FSMContext):
    if query.data == "studying":
        await state.update_data(partner_status="studying")
        data = await state.get_data()
        history = data.get("_history", [])
        history.append(SurveyStates.partner_status.state)
        await state.update_data(_history=history)
        await state.set_state(SurveyStates.partner_fio)
        await query.message.edit_text("7) Введите ФИО партнёра", reply_markup=back_kb())
        return
    await state.update_data(partner_status="graduated")
    data = await state.get_data()
    history = data.get("_history", [])
    history.append(SurveyStates.partner_status.state)
    await state.update_data(_history=history)
    await state.set_state(SurveyStates.partner_fio)
    await query.message.edit_text("8) Введите ФИО партнёра", reply_markup=back_kb())


@dp.callback_query(lambda c: c.data == "confirm" or c.data == "cancel")
async def confirm_cb(query: CallbackQuery, state: FSMContext):
    if query.data == "cancel":
        await query.message.edit_text("Отменено. Пришлите /start чтобы начать заново.")
        await state.clear()
        return
    
    data = await state.get_data()
    ticket_type = data.get('pair_or_single', 'single')
    
    # ⚠️ АТОМАРНАЯ ПРОВЕРКА И РЕЗЕРВИРОВАНИЕ МЕСТ
    success, message = await try_register(ticket_type)
    
    if not success:
        # Мест нет - отклоняем регистрацию
        await query.message.edit_text(
            f"{message}\n\n"
            "К сожалению, вы не успели зарегистрироваться. "
            "Следите за анонсами - возможно появятся дополнительные места."
        )
        await state.clear()
        logger.warning(
            f"❌ Registration rejected: user_id={query.from_user.id}, "
            f"ticket_type={ticket_type}, reason=no_seats"
        )
        return
    
    # ✅ Места зарезервированы - сохраняем в БД
    try:
        allowed = {col.name for col in Survey.__table__.columns}
        payload = {k: v for k, v in data.items() if k in allowed}
        
        async with async_session() as session:
            survey = Survey(**payload)
            session.add(survey)
            await session.commit()
        
        await query.message.edit_text(
            f"✅ Спасибо! Регистрация успешна!\n\n"
            f"{message}\n\n"
            f"Билет будет отправлен вам позже через команду рассылки."
        )
        
        logger.info(
            f"✅ Registration successful: user_id={query.from_user.id}, "
            f"username={query.from_user.username}, ticket_type={ticket_type}, "
            f"fio={data.get('fio')}"
        )
        
    except Exception as e:
        logger.error(f"❌ Database error during registration: {e}")
        await query.message.edit_text(
            "❌ Произошла ошибка при сохранении данных. "
            "Обратитесь к администратору."
        )
    
    await state.clear()


async def send_review(dest, state: FSMContext):
    data = await state.get_data()
    lines = [f"Согласие: {data.get('consent')}", f"ФИО: {data.get('fio')}", f"Группа: {data.get('group')}",
             f"Студенческий: {data.get('student_id')}", f"В паре: {data.get('pair_or_single')}"]
    if data.get('pair_or_single') == 'pair':
        lines += [f"Партнёр статус: {data.get('partner_status')}",
                  f"Партнёр ФИО: {data.get('partner_fio')}",
                  f"Партнёр группа: {data.get('partner_group')}",
                  f"Партнёр студенческий/диплом: {data.get('partner_student_id') or data.get('partner_diploma')}"]
    text = "\n".join(lines)
    await dest.answer(text, reply_markup=review_kb())


@dp.callback_query(lambda c: c.data and c.data.startswith('edit_'))
async def edit_field_cb(query: CallbackQuery, state: FSMContext):
    # allow editing specific fields from review
    field = query.data[len('edit_'):]
    # push current state to history so user can go back
    data = await state.get_data()
    history = data.get('_history', [])
    history.append((await state.get_state()) or SurveyStates.review.state)
    await state.update_data(_history=history)

    if field == 'fio':
        await state.set_state(SurveyStates.fio)
        await query.message.edit_text('2) Введите своё ФИО', reply_markup=back_kb())
        return
    if field == 'group':
        await state.set_state(SurveyStates.group)
        await query.message.edit_text('3) Введите группу обучения (пример ПИ23-1)', reply_markup=back_kb())
        return
    if field == 'student_id':
        await state.set_state(SurveyStates.student_id)
        await query.message.edit_text('4) Введите номер студенческого билета (пример 236446)', reply_markup=back_kb())
        return


async def handle_back(message: Message | CallbackQuery, state: FSMContext):
    """Pop previous state from history and restore it."""
    data = await state.get_data()
    history = data.get("_history", [])
    if not history:
        # nothing to go back to
        if isinstance(message, CallbackQuery):
            await message.answer("Нечего отменять.")
        else:
            await message.answer("Нечего отменять.")
        return

    prev_state = history.pop()  # last pushed
    await state.update_data(_history=history)
    # set previous state
    await state.set_state(prev_state)

    # inform user of restored prompt
    # map state to prompt
    prompts = {
        SurveyStates.consent.state: ("1) Согласны ли вы со сбором персональных данных?", yes_no_kb()),
        SurveyStates.fio.state: ("2) Введите своё ФИО", back_kb()),
        SurveyStates.group.state: ("3) Введите группу обучения (пример ПИ23-1)", back_reply_kb()),
        SurveyStates.student_id.state: ("4) Введите номер студенческого билета (пример 236446)", back_reply_kb()),
        SurveyStates.pair_or_single.state: ("5) Вы будете в паре или один?", pair_or_single_kb()),
        SurveyStates.partner_status.state: ("6) Ваш парнёр учится или уже закончил Финансовый университет ?", studying_or_graduated_kb()),
        SurveyStates.partner_fio.state: ("7/8) Введите ФИО партнёра", back_reply_kb()),
        SurveyStates.partner_group.state: ("Введите группу партнёра", back_reply_kb()),
        SurveyStates.partner_student_id.state: ("Введите номер студенческого билета партнёра", back_reply_kb()),
        SurveyStates.partner_diploma.state: ("Введите номер диплома партнёра", back_reply_kb()),
    }

    prompt = prompts.get(prev_state)
    if prompt:
        text, kb = prompt
        if isinstance(message, CallbackQuery):
            await message.message.edit_text(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)


# ==================== ADMIN COMMANDS ====================

# Список ID администраторов (добавьте свои ID)
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]


def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика регистрации (только для админов)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
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


@dp.message(Command("rass"))
async def cmd_broadcast(message: Message):
    """
    Запускает рассылку билетов всем зарегистрированным пользователям.
    Только для админов!
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    await message.answer("🚀 Начинаю рассылку билетов...\nЭто может занять некоторое время.")
    
    try:
        # Получаем всех зарегистрированных пользователей
        async with async_session() as session:
            result = await session.execute(select(Survey))
            users = result.scalars().all()
        
        if not users:
            await message.answer("❌ Нет зарегистрированных пользователей.")
            return
        
        # Подготавливаем данные для Celery
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'telegram_id': user.telegram_id,
                'fio': user.fio,
                'group': user.group,
                'student_id': user.student_id,
                'ticket_type': user.pair_or_single,
                'partner_fio': user.partner_fio
            })
        
        # Импортируем Celery task
        from tasks import broadcast_tickets_task
        
        # Запускаем задачу в фоне
        task = broadcast_tickets_task.delay(users_data)
        
        await message.answer(
            f"✅ Рассылка запущена!\n\n"
            f"📊 Всего пользователей: {len(users_data)}\n"
            f"🔑 Task ID: `{task.id}`\n\n"
            f"⏱ Примерное время: ~{len(users_data) * 0.05 / 60:.1f} минут\n\n"
            f"💡 Прогресс можно отслеживать в логах Celery worker.",
            parse_mode="Markdown"
        )
        
        logger.info(
            f"📢 Broadcast initiated by admin {message.from_user.id} ({message.from_user.username}). "
            f"Users: {len(users_data)}, Task ID: {task.id}"
        )
        
    except Exception as e:
        logger.error(f"❌ Broadcast error: {e}")
        await message.answer(
            f"❌ Ошибка при запуске рассылки:\n`{str(e)}`\n\n"
            f"Проверьте, что Celery worker запущен!",
            parse_mode="Markdown"
        )
