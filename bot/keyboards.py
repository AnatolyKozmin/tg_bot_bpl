from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def yes_no_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton(text="Да", callback_data="yes"),
           InlineKeyboardButton(text="Нет", callback_data="no"))
    return kb


def pair_or_single_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton(text="В паре", callback_data="pair"),
           InlineKeyboardButton(text="Один", callback_data="single"))
    return kb


def studying_or_graduated_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton(text="Учится", callback_data="studying"),
           InlineKeyboardButton(text="Закончил", callback_data="graduated"))
    return kb


def confirm_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton(text="Подтвердить", callback_data="confirm"),
           InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return kb


def back_kb(action="back"):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton(text="◀️ Назад", callback_data=action))
    return kb


def back_reply_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton(text="◀️ Назад"))
    return kb


def review_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.add(InlineKeyboardButton(text="Редактировать ФИО", callback_data="edit_fio"),
        InlineKeyboardButton(text="Редактировать группу", callback_data="edit_group"))
    kb.add(InlineKeyboardButton(text="Редактировать студбилет", callback_data="edit_student_id"))
    kb.add(InlineKeyboardButton(text="Подтвердить", callback_data="confirm"),
        InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return kb
