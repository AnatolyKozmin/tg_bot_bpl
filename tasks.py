"""
Celery tasks для асинхронной генерации и рассылки билетов.

Запуск воркеров:
    celery -A tasks worker --loglevel=info --concurrency=5

Для мониторинга:
    celery -A tasks flower
"""

import os
import io
import asyncio
from celery import Celery
from PIL import Image, ImageDraw, ImageFont
import qrcode
from dotenv import load_dotenv
import logging
from datetime import datetime
from sqlalchemy import update

# Импорт db модулей (нужны в начале для Celery!)
from db.session import sync_session  # Используем SYNC сессию для Celery!
from db.models import Survey

load_dotenv()

# Настройка Celery
REDIS_BROKER_URL = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/1")
celery_app = Celery('tasks', broker=REDIS_BROKER_URL, backend=REDIS_BROKER_URL)

# Настройки Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,              # Подтверждение после выполнения
    worker_prefetch_multiplier=1,     # Берем по одной задаче
    task_time_limit=300,              # Таймаут задачи 5 минут
    task_soft_time_limit=240,         # Мягкий таймаут 4 минуты
    broker_connection_retry_on_startup=True,  # Убирает warning Celery 6.0
)

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_ticket(self, user_id: int, user_data: dict):
    """
    Генерирует билет с QR-кодом и СОХРАНЯЕТ на сервере (не отправляет).
    Отправка будет по команде /rass.
    
    Args:
        user_data: {
            'id': int,
            'telegram_id': str,
            'fio': str,
            'group': str,
            'student_id': str,
            'ticket_type': 'single' | 'pair',
            'partner_fio': str | None
        }
    
    Returns:
        dict: {'status': 'success' | 'error', 'user_id': int, 'message': str}
    """
    try:
        logger.info(f"🎫 Generating ticket for user {user_data['id']}: {user_data['fio']}")
        
        # 1. Загружаем конфигурацию
        try:
            from ticket_config import (
                FONT_PATH, FONT_PATH_FALLBACK, FONT_SIZES, TEXT_POSITIONS, 
                TEXT_COLORS, QR_CONFIG, QR_DATA_FORMAT
            )
        except ImportError:
            logger.warning("⚠️ ticket_config.py not found, using defaults")
            FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            FONT_PATH_FALLBACK = FONT_PATH
            FONT_SIZES = {'name': 45, 'telegram_id': 35}
            TEXT_POSITIONS = {
                'qr_code': (600, 250),
                'telegram_id': (600, 480),
                'name': (600, 540)
            }
            TEXT_COLORS = {'name': 'black', 'telegram_id': '#555555'}
            QR_CONFIG = {'size': (250, 250), 'box_size': 10, 'border': 2}
            QR_DATA_FORMAT = "{telegram_id}"
        
        # 2. Генерируем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=QR_CONFIG.get('box_size', 10),
            border=QR_CONFIG.get('border', 2),
        )
        
        # Данные для QR-кода (только telegram_id)
        qr_data = QR_DATA_FORMAT.format(telegram_id=user_data['telegram_id'])
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Разбиваем ФИО на части (Фамилия Имя)
        fio_parts = user_data.get('fio', '').strip().split()
        if len(fio_parts) >= 2:
            name_text = f"{fio_parts[0]} {fio_parts[1]}"  # Фамилия Имя
        elif len(fio_parts) == 1:
            name_text = fio_parts[0]  # Только фамилия
        else:
            name_text = "Участник"  # Fallback
        
        # 2. Загружаем шаблон билета
        template_path = os.getenv("TICKET_TEMPLATE_PATH", "ticket_template.png")
        
        if not os.path.exists(template_path):
            logger.warning(f"⚠️ Template not found: {template_path}. Creating blank ticket.")
            # Создаем простой билет если шаблона нет
            template = Image.new('RGB', (1200, 600), color='white')
        else:
            template = Image.open(template_path).convert('RGB')
        
        draw = ImageDraw.Draw(template)
        
        # 3. Загружаем шрифты
        try:
            # Пытаемся загрузить кастомный шрифт
            font_name = ImageFont.truetype(FONT_PATH, FONT_SIZES['name'])
            font_tg_id = ImageFont.truetype(FONT_PATH, FONT_SIZES['telegram_id'])
            logger.info(f"✅ Loaded custom font: {FONT_PATH}")
        except Exception as e:
            logger.warning(f"⚠️ Custom font not found: {e}, trying fallback")
            try:
                # Пытаемся загрузить запасной шрифт
                font_name = ImageFont.truetype(FONT_PATH_FALLBACK, FONT_SIZES['name'])
                font_tg_id = ImageFont.truetype(FONT_PATH_FALLBACK, FONT_SIZES['telegram_id'])
                logger.info(f"✅ Loaded fallback font: {FONT_PATH_FALLBACK}")
            except:
                # Используем системный шрифт по умолчанию
                logger.warning("⚠️ Using default system font")
                font_name = ImageFont.load_default()
                font_tg_id = ImageFont.load_default()
        
        # 4. Размещаем QR-код по центру
        qr_img_resized = qr_img.resize(QR_CONFIG['size'])
        
        # Вычисляем позицию для центрирования QR
        qr_center = TEXT_POSITIONS['qr_code']
        qr_paste_position = (
            qr_center[0] - QR_CONFIG['size'][0] // 2,  # x - половина ширины
            qr_center[1] - QR_CONFIG['size'][1] // 2   # y - половина высоты
        )
        template.paste(qr_img_resized, qr_paste_position)
        
        # 5. Размещаем текст с ИДЕАЛЬНЫМ центрированием
        
        # Telegram ID (под QR-кодом) - только цифры
        tg_id_text = user_data['telegram_id']
        
        # Вычисляем размер текста telegram_id
        try:
            # Для новых версий Pillow
            bbox_tg_id = draw.textbbox((0, 0), tg_id_text, font=font_tg_id)
            tg_id_width = bbox_tg_id[2] - bbox_tg_id[0]
            tg_id_height = bbox_tg_id[3] - bbox_tg_id[1]
        except AttributeError:
            # Для старых версий Pillow
            tg_id_width, tg_id_height = draw.textsize(tg_id_text, font=font_tg_id)
        
        # Центрируем telegram_id
        tg_id_x = TEXT_POSITIONS['telegram_id'][0] - tg_id_width // 2
        tg_id_y = TEXT_POSITIONS['telegram_id'][1] - tg_id_height // 2
        
        draw.text(
            (tg_id_x, tg_id_y),
            tg_id_text,
            fill=TEXT_COLORS.get('telegram_id', '#555555'),
            font=font_tg_id
        )
        
        # Фамилия и Имя (под telegram_id)
        
        # Вычисляем размер текста имени
        try:
            bbox_name = draw.textbbox((0, 0), name_text, font=font_name)
            name_width = bbox_name[2] - bbox_name[0]
            name_height = bbox_name[3] - bbox_name[1]
        except AttributeError:
            name_width, name_height = draw.textsize(name_text, font=font_name)
        
        # Центрируем имя
        name_x = TEXT_POSITIONS['name'][0] - name_width // 2
        name_y = TEXT_POSITIONS['name'][1] - name_height // 2
        
        draw.text(
            (name_x, name_y),
            name_text,
            fill=TEXT_COLORS.get('name', 'black'),
            font=font_name
        )
        
        # 6. Сохраняем билет на сервер (не отправляем)
        tickets_dir = "tickets"
        os.makedirs(tickets_dir, exist_ok=True)
        
        ticket_filename = f"ticket_{user_data['telegram_id']}.png"
        ticket_path = os.path.join(tickets_dir, ticket_filename)
        
        template.save(ticket_path, 'PNG')
        logger.info(f"✅ Ticket saved: {ticket_path}")
        
        # 7. Обновляем статус в БД (СИНХРОННО для Celery!)
        with sync_session() as session:
            session.execute(
                update(Survey)
                .where(Survey.id == user_id)
                .values(
                    ticket_generated=True,
                    ticket_path=ticket_path,
                    ticket_generated_at=datetime.utcnow()
                )
            )
            session.commit()
        
        logger.info(f"✅ Ticket generated for user {user_data['id']}: {ticket_path}")
        return {
            'status': 'success', 
            'user_id': user_data['id'], 
            'ticket_path': ticket_path,
            'message': 'Ticket generated and saved'
        }
        
    except Exception as exc:
        logger.error(f"❌ Error generating ticket for user {user_data['id']}: {exc}")
        
        # Повторная попытка
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retrying task for user {user_data['id']}, attempt {self.request.retries + 1}")
            raise self.retry(exc=exc, countdown=60)
        else:
            logger.error(f"💀 Failed permanently for user {user_data['id']}")
            return {'status': 'error', 'user_id': user_data['id'], 'message': str(exc)}


@celery_app.task(bind=True, max_retries=3)
def send_existing_ticket(self, user_id: int, telegram_id: str, ticket_path: str):
    """
    Отправляет УЖЕ СОЗДАННЫЙ билет пользователю.
    Используется при команде /rass.
    """
    try:
        from bot.sender import send_ticket_file
        
        # Проверяем что файл существует
        if not os.path.exists(ticket_path):
            raise FileNotFoundError(f"Ticket not found: {ticket_path}")
        
        # Отправляем билет (async операция)
        result = asyncio.run(send_ticket_file(telegram_id, ticket_path))
        
        if result:
            # Обновляем статус в БД (СИНХРОННО для Celery!)
            with sync_session() as session:
                session.execute(
                    update(Survey)
                    .where(Survey.id == user_id)
                    .values(
                        ticket_sent=True,
                        ticket_sent_at=datetime.utcnow()
                    )
                )
                session.commit()
            
            logger.info(f"✅ Ticket sent to user {telegram_id}")
            return {'status': 'success', 'user_id': user_id}
        else:
            raise Exception("Failed to send ticket")
            
    except Exception as exc:
        logger.error(f"❌ Error sending ticket to {telegram_id}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60)
        return {'status': 'error', 'user_id': user_id, 'message': str(exc)}


@celery_app.task
def broadcast_tickets_task(tickets_to_send: list):
    """
    Отправляет готовые билеты всем пользователям.
    Используется при команде /rass.
    
    Args:
        tickets_to_send: Список [{'user_id': int, 'telegram_id': str, 'ticket_path': str}, ...]
    """
    from celery import group
    
    # DEBUG: Логируем ДО ВСЕГО
    logger.info(f"🚀 broadcast_tickets_task STARTED! Type: {type(tickets_to_send)}, Length: {len(tickets_to_send) if tickets_to_send else 0}")
    logger.info(f"📢 Starting broadcast for {len(tickets_to_send)} users")
    
    # DEBUG: Показываем первые 3 записи
    if tickets_to_send:
        logger.info(f"🔍 First ticket example: {tickets_to_send[0]}")
    
    # Создаем группу задач для отправки (позиционные аргументы!)
    tasks_list = []
    for ticket in tickets_to_send:
        task_sig = send_existing_ticket.s(
            ticket['user_id'],
            ticket['telegram_id'],
            ticket['ticket_path']
        )
        tasks_list.append(task_sig)
        logger.info(f"✅ Created task for user {ticket['user_id']} (TG: {ticket['telegram_id']})")
    
    logger.info(f"📋 Total tasks created: {len(tasks_list)}")
    
    job = group(tasks_list)
    result = job.apply_async()
    
    logger.info(f"🚀 Group applied, result ID: {result.id if hasattr(result, 'id') else 'N/A'}")
    
    return {
        'status': 'started',
        'total_users': len(tickets_to_send),
        'message': f'Broadcast started for {len(tickets_to_send)} users'
    }


@celery_app.task
def generate_tickets_batch(users_data: list):
    """
    Генерирует билеты для списка пользователей (после регистрации).
    НЕ отправляет, только создает и сохраняет.
    """
    from celery import group
    
    logger.info(f"🎫 Generating tickets for {len(users_data)} users")
    
    # Создаем группу задач (позиционные аргументы!)
    job = group(
        generate_ticket.s(
            user['id'],
            user
        ) 
        for user in users_data
    )
    result = job.apply_async()
    
    return {
        'status': 'started',
        'total_users': len(users_data),
        'message': f'Ticket generation started for {len(users_data)} users'
    }


# ==================== BROADCAST TASKS ====================

@celery_app.task(bind=True, max_retries=3)
def send_broadcast_message_task(self, user_id: int, telegram_id: str, message_text: str, parse_mode: str = "Markdown"):
    """
    Отправляет текстовое сообщение одному пользователю (Celery задача).
    
    Args:
        user_id: ID пользователя в БД
        telegram_id: Telegram ID пользователя
        message_text: Текст сообщения
        parse_mode: Режим парсинга (Markdown, HTML или None)
    
    Returns:
        dict: Результат отправки
    """
    try:
        from bot.sender import send_broadcast_message
        
        # Отправляем сообщение (async операция)
        success, error_msg = asyncio.run(send_broadcast_message(telegram_id, message_text, parse_mode))
        
        if success:
            logger.info(f"✅ Broadcast sent to user {telegram_id} (ID: {user_id})")
            return {
                'status': 'success',
                'user_id': user_id,
                'telegram_id': telegram_id
            }
        else:
            raise Exception(f"Send failed: {error_msg}")
            
    except Exception as exc:
        logger.error(f"❌ Error sending broadcast to {telegram_id}: {exc}")
        
        # Повторная попытка при ошибке
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retrying broadcast for user {telegram_id}, attempt {self.request.retries + 1}")
            raise self.retry(exc=exc, countdown=30)
        else:
            logger.error(f"💀 Failed permanently for user {telegram_id}")
            return {
                'status': 'error',
                'user_id': user_id,
                'telegram_id': telegram_id,
                'error': str(exc)
            }


@celery_app.task(bind=True, max_retries=3)
def send_broadcast_photo_task(self, user_id: int, telegram_id: str, photo_path: str, caption: str = None, parse_mode: str = "Markdown"):
    """
    Отправляет фото с подписью одному пользователю (Celery задача).
    
    Args:
        user_id: ID пользователя в БД
        telegram_id: Telegram ID пользователя
        photo_path: Путь к файлу изображения
        caption: Текст подписи
        parse_mode: Режим парсинга (Markdown, HTML или None)
    
    Returns:
        dict: Результат отправки
    """
    try:
        from bot.sender import send_broadcast_photo
        
        # Проверяем существование файла
        if not os.path.exists(photo_path):
            raise FileNotFoundError(f"Photo file not found: {photo_path}")
        
        # Отправляем фото (async операция)
        success, error_msg = asyncio.run(send_broadcast_photo(telegram_id, photo_path, caption, parse_mode))
        
        if success:
            logger.info(f"✅ Broadcast photo sent to user {telegram_id} (ID: {user_id})")
            return {
                'status': 'success',
                'user_id': user_id,
                'telegram_id': telegram_id
            }
        else:
            raise Exception(f"Send failed: {error_msg}")
            
    except Exception as exc:
        logger.error(f"❌ Error sending broadcast photo to {telegram_id}: {exc}")
        
        # Повторная попытка при ошибке
        if self.request.retries < self.max_retries:
            logger.info(f"🔄 Retrying broadcast photo for user {telegram_id}, attempt {self.request.retries + 1}")
            raise self.retry(exc=exc, countdown=30)
        else:
            logger.error(f"💀 Failed permanently for user {telegram_id}")
            return {
                'status': 'error',
                'user_id': user_id,
                'telegram_id': telegram_id,
                'error': str(exc)
            }


@celery_app.task
def mass_broadcast_task(users_list: list, message_text: str = None, photo_path: str = None, caption: str = None, parse_mode: str = "Markdown"):
    """
    Запускает массовую рассылку сообщений всем пользователям.
    Может отправлять текст или фото с подписью.
    
    Args:
        users_list: Список [{'user_id': int, 'telegram_id': str}, ...]
        message_text: Текст сообщения (если отправляем текст)
        photo_path: Путь к изображению (если отправляем фото)
        caption: Подпись к фото
        parse_mode: Режим парсинга (Markdown, HTML или None)
    
    Returns:
        dict: Статус запуска рассылки
    """
    from celery import group
    
    logger.info(f"📢 Starting mass broadcast for {len(users_list)} users")
    logger.info(f"📝 Message type: {'photo' if photo_path else 'text'}")
    
    # Создаем группу задач для отправки
    tasks_list = []
    
    if photo_path:
        # Рассылка фото
        for user in users_list:
            task_sig = send_broadcast_photo_task.s(
                user['user_id'],
                user['telegram_id'],
                photo_path,
                caption,
                parse_mode
            )
            tasks_list.append(task_sig)
    else:
        # Рассылка текста
        for user in users_list:
            task_sig = send_broadcast_message_task.s(
                user['user_id'],
                user['telegram_id'],
                message_text,
                parse_mode
            )
            tasks_list.append(task_sig)
    
    logger.info(f"📋 Total tasks created: {len(tasks_list)}")
    
    # Запускаем группу задач
    job = group(tasks_list)
    result = job.apply_async()
    
    logger.info(f"🚀 Mass broadcast group started, result ID: {result.id if hasattr(result, 'id') else 'N/A'}")
    
    return {
        'status': 'started',
        'total_users': len(users_list),
        'message_type': 'photo' if photo_path else 'text',
        'message': f'Mass broadcast started for {len(users_list)} users'
    }
