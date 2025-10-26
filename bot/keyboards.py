from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def yes_no_kb():
    """Согласие на обработку персональных данных"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="yes")]
    ])
    return kb


def is_student_kb():
    """Является ли студентом"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🎓 Студент", callback_data="is_student_yes")],
        [InlineKeyboardButton(text="🎓 Выпускник", callback_data="is_student_no")]
    ])
    return kb


def faculty_kb():
    """Выбор факультета"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ИТиАБД", callback_data="faculty_ИТиАБД")],
        [InlineKeyboardButton(text="Финфак", callback_data="faculty_Финфак")],
        [InlineKeyboardButton(text="ВШУ", callback_data="faculty_ВШУ")],
        [InlineKeyboardButton(text="Юрфак", callback_data="faculty_Юрфак")],
        [InlineKeyboardButton(text="НАБ", callback_data="faculty_НАБ")],
        [InlineKeyboardButton(text="ФЭБ", callback_data="faculty_ФЭБ")],
        [InlineKeyboardButton(text="СНиМК", callback_data="faculty_СНиМК")],
        [InlineKeyboardButton(text="МЭО", callback_data="faculty_МЭО")],
        [InlineKeyboardButton(text="Другое", callback_data="faculty_Другое")]
    ])
    return kb


def course_kb():
    """Выбор курса обучения"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 курс Б", callback_data="course_1Б"),
            InlineKeyboardButton(text="2 курс Б", callback_data="course_2Б")
        ],
        [
            InlineKeyboardButton(text="3 курс Б", callback_data="course_3Б"),
            InlineKeyboardButton(text="4 курс Б", callback_data="course_4Б")
        ],
        [
            InlineKeyboardButton(text="1 курс М", callback_data="course_1М"),
            InlineKeyboardButton(text="2 курс М", callback_data="course_2М")
        ]
    ])
    return kb


def pair_or_single_kb():
    """Выбор типа билета"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 В паре", callback_data="pair"), InlineKeyboardButton(text="🙋 Один", callback_data="single")]
    ])
    return kb


def studying_or_graduated_kb():
    """Статус партнера"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🎓 Учится", callback_data="studying"), InlineKeyboardButton(text="🎓 Выпускник", callback_data="graduated")]
    ])
    return kb


def confirm_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить", callback_data="confirm"), InlineKeyboardButton(text="Отмена", callback_data="cancel")]
    ])
    return kb


def back_kb(action="back"):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data=action)]])
    return kb


def back_reply_kb():
    # ReplyKeyboardMarkup in aiogram v3 expects 'keyboard' field (list of rows)
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Назад")]], resize_keyboard=True, one_time_keyboard=True)
    return kb


def review_kb():
    """Клавиатура для проверки анкеты перед отправкой"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать ФИО", callback_data="edit_fio")],
        [InlineKeyboardButton(text="✏️ Редактировать факультет", callback_data="edit_faculty")],
        [InlineKeyboardButton(text="✏️ Редактировать курс", callback_data="edit_course")],
        [InlineKeyboardButton(text="✏️ Редактировать группу", callback_data="edit_group")],
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm"), InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])
    return kb


def manage_ticket_kb():
    """Клавиатура для управления уже зарегистрированным билетом"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать анкету", callback_data="edit_ticket")],
        [InlineKeyboardButton(text="❌ Отменить билет", callback_data="cancel_ticket")]
    ])
    return kb


def confirm_cancel_kb():
    """Подтверждение отмены билета"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отменить", callback_data="confirm_cancel_ticket")],
        [InlineKeyboardButton(text="❌ Нет, оставить", callback_data="keep_ticket")]
    ])
    return kb
