"""
Модуль для экспорта данных регистрации в Google Sheets
"""
import os
import gspread
from google.oauth2.service_account import Credentials
from db.session import async_session
from db.models import Survey
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# Области доступа для Google Sheets API
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_google_client():
    """Создает клиент Google Sheets API"""
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Файл credentials.json не найден по пути: {creds_path}")
    
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client


async def export_to_google_sheets(spreadsheet_id: str) -> dict:
    """
    Экспортирует данные регистрации в Google Sheets
    
    Args:
        spreadsheet_id: ID Google таблицы (из URL)
    
    Returns:
        dict: Статистика экспорта
    """
    try:
        # Получаем данные из БД
        async with async_session() as session:
            result = await session.execute(
                select(Survey).where(Survey.fio.isnot(None))
            )
            surveys = result.scalars().all()
        
        # Разделяем на solo и duo
        solo_data = []
        duo_data = []
        
        for survey in surveys:
            # Определяем статус (студент/выпускник)
            # Если is_student == None, проверяем наличие student_id
            if survey.is_student is True:
                user_status = "Студент"
                user_id = survey.student_id or ""
            elif survey.is_student is False:
                user_status = "Выпускник"
                user_id = survey.diploma_number or ""
            else:
                # Старые записи без явного указания статуса
                # Определяем по наличию student_id или diploma_number
                if survey.student_id:
                    user_status = "Студент"
                    user_id = survey.student_id
                elif survey.diploma_number:
                    user_status = "Выпускник"
                    user_id = survey.diploma_number
                else:
                    user_status = "Не указано"
                    user_id = ""
            
            # Основные данные пользователя
            user_row = [
                survey.id,
                survey.fio or "",
                user_status,
                survey.faculty or "",
                survey.course or "",
                survey.group or "",
                user_id or "",
                survey.telegram_id or "",
                survey.telegram_username or "",
            ]
            
            # Если есть партнер - добавляем в duo
            if survey.partner_fio:
                # Определяем статус партнера
                if survey.partner_status == "studying":
                    partner_status = "Студент"
                    partner_id = survey.partner_student_id or ""
                elif survey.partner_status == "graduated":
                    partner_status = "Выпускник"
                    partner_id = survey.partner_diploma or ""
                else:
                    # Старые записи без явного указания статуса
                    if survey.partner_student_id:
                        partner_status = "Студент"
                        partner_id = survey.partner_student_id
                    elif survey.partner_diploma:
                        partner_status = "Выпускник"
                        partner_id = survey.partner_diploma
                    else:
                        partner_status = "Не указано"
                        partner_id = ""
                
                # Добавляем данные партнера к строке
                duo_row = user_row + [
                    survey.partner_fio or "",
                    partner_status,
                    survey.partner_faculty or "",
                    survey.partner_course or "",
                    survey.partner_group or "",
                    partner_id or "",
                ]
                duo_data.append(duo_row)
            else:
                # Без партнера - в solo
                solo_data.append(user_row)
        
        # Подключаемся к Google Sheets
        client = get_google_client()
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Получаем или создаем листы
        try:
            solo_sheet = spreadsheet.worksheet("solo")
        except gspread.exceptions.WorksheetNotFound:
            solo_sheet = spreadsheet.add_worksheet(title="solo", rows=1000, cols=20)
        
        try:
            duo_sheet = spreadsheet.worksheet("duo")
        except gspread.exceptions.WorksheetNotFound:
            duo_sheet = spreadsheet.add_worksheet(title="duo", rows=1000, cols=20)
        
        # Заголовки для solo
        solo_headers = [
            "ID",
            "ФИО",
            "Статус",
            "Факультет",
            "Курс",
            "Группа",
            "Номер студ. билета/Диплома",
            "Telegram ID",
            "Telegram Username",
        ]
        
        # Заголовки для duo
        duo_headers = [
            "ID",
            "ФИО (1)",
            "Статус (1)",
            "Факультет (1)",
            "Курс (1)",
            "Группа (1)",
            "Номер студ. билета/Диплома (1)",
            "Telegram ID (1)",
            "Telegram Username (1)",
            "ФИО (2)",
            "Статус (2)",
            "Факультет (2)",
            "Курс (2)",
            "Группа (2)",
            "Номер студ. билета/Диплома (2)",
        ]
        
        # Очищаем листы и добавляем данные
        solo_sheet.clear()
        solo_sheet.append_row(solo_headers)
        if solo_data:
            solo_sheet.append_rows(solo_data)
        
        duo_sheet.clear()
        duo_sheet.append_row(duo_headers)
        if duo_data:
            duo_sheet.append_rows(duo_data)
        
        # Форматирование заголовков (жирный шрифт)
        solo_sheet.format("A1:I1", {"textFormat": {"bold": True}})
        duo_sheet.format("A1:O1", {"textFormat": {"bold": True}})
        
        return {
            "success": True,
            "solo_count": len(solo_data),
            "duo_count": len(duo_data),
            "total": len(surveys),
        }
        
    except Exception as e:
        logger.error(f"Ошибка при экспорте в Google Sheets: {e}", exc_info=True)
        raise

