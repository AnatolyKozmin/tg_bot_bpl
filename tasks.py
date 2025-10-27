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
        
        # 1. Генерируем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        
        # Данные для QR-кода (можно изменить формат)
        qr_data = f"EVENT_TICKET_{user_data['id']}_{user_data['telegram_id']}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
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
            font_path = os.getenv("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
            font_name = ImageFont.truetype(font_path, 50)
            font_info = ImageFont.truetype(font_path, 35)
            font_small = ImageFont.truetype(font_path, 25)
        except:
            logger.warning("⚠️ Custom font not found, using default")
            font_name = ImageFont.load_default()
            font_info = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # 4. Накладываем текст на билет
        # ВАЖНО: Настройте позиции под ваш шаблон!
        
        # ФИО
        draw.text((100, 150), user_data['fio'], fill="black", font=font_name)
        
        # Группа
        draw.text((100, 250), f"Группа: {user_data['group']}", fill="black", font=font_info)
        
        # Студенческий билет
        draw.text((100, 320), f"Студ. билет: {user_data['student_id']}", fill="black", font=font_info)
        
        # Тип билета
        ticket_type_text = "ОДИНОЧНЫЙ" if user_data['ticket_type'] == 'single' else "ПАРНЫЙ"
        draw.text((100, 390), f"Тип: {ticket_type_text}", fill="black", font=font_info)
        
        # Партнер (если есть)
        if user_data.get('partner_fio'):
            draw.text((100, 460), f"Партнёр: {user_data['partner_fio']}", fill="black", font=font_small)
        
        # 5. Накладываем QR-код
        qr_size = (250, 250)
        qr_img = qr_img.resize(qr_size)
        qr_position = (900, 300)  # Настройте под ваш шаблон
        template.paste(qr_img, qr_position)
        
        # 6. Сохраняем билет на сервер (не отправляем)
        tickets_dir = "tickets"
        os.makedirs(tickets_dir, exist_ok=True)
        
        ticket_filename = f"ticket_{user_data['telegram_id']}.png"
        ticket_path = os.path.join(tickets_dir, ticket_filename)
        
        template.save(ticket_path, 'PNG')
        logger.info(f"✅ Ticket saved: {ticket_path}")
        
        # 7. Обновляем статус в БД
        from db.session import async_session
        from db.models import Survey
        from sqlalchemy import update
        from datetime import datetime
        
        async def update_ticket_status():
            async with async_session() as session:
                await session.execute(
                    update(Survey)
                    .where(Survey.id == user_id)
                    .values(
                        ticket_generated=True,
                        ticket_path=ticket_path,
                        ticket_generated_at=datetime.utcnow()
                    )
                )
                await session.commit()
        
        asyncio.run(update_ticket_status())
        
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
        from db.session import async_session
        from db.models import Survey
        from sqlalchemy import update
        from datetime import datetime
        
        # Проверяем что файл существует
        if not os.path.exists(ticket_path):
            raise FileNotFoundError(f"Ticket not found: {ticket_path}")
        
        # Отправляем билет
        result = asyncio.run(send_ticket_file(telegram_id, ticket_path))
        
        if result:
            # Обновляем статус в БД
            async def update_sent_status():
                async with async_session() as session:
                    await session.execute(
                        update(Survey)
                        .where(Survey.id == user_id)
                        .values(
                            ticket_sent=True,
                            ticket_sent_at=datetime.utcnow()
                        )
                    )
                    await session.commit()
            
            asyncio.run(update_sent_status())
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
    
    logger.info(f"📢 Starting broadcast for {len(tickets_to_send)} users")
    
    # Создаем группу задач для отправки
    job = group(
        send_existing_ticket.s(
            user_id=ticket['user_id'],
            telegram_id=ticket['telegram_id'],
            ticket_path=ticket['ticket_path']
        ) 
        for ticket in tickets_to_send
    )
    result = job.apply_async()
    
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
    
    job = group(
        generate_ticket.s(
            user_id=user['id'],
            user_data=user
        ) 
        for user in users_data
    )
    result = job.apply_async()
    
    return {
        'status': 'started',
        'total_users': len(users_data),
        'message': f'Ticket generation started for {len(users_data)} users'
    }

