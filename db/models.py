from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True)
    consent = Column(Boolean, default=False)
    
    # Основные данные
    is_student = Column(Boolean, nullable=True)  # Является ли студентом (для первого человека)
    fio = Column(String(255))
    faculty = Column(String(64), nullable=True)  # Факультет
    course = Column(String(32), nullable=True)   # Курс обучения
    group = Column(String(64))
    student_id = Column(String(6), nullable=True)  # Номер студ. билета (6 цифр)
    diploma_number = Column(String(64), nullable=True)  # Номер диплома если не студент
    
    # Telegram данные
    telegram_id = Column(String(64), nullable=True, unique=True, index=True)
    telegram_username = Column(String(255), nullable=True)
    
    # Данные о билете
    pair_or_single = Column(String(16))
    ticket_sent = Column(Boolean, default=False)  # Отправлен ли билет
    ticket_cancelled = Column(Boolean, default=False)  # Отменен ли билет
    
    # Данные партнера
    partner_status = Column(String(32), nullable=True)  # studying/graduated
    partner_fio = Column(String(255), nullable=True)
    partner_faculty = Column(String(64), nullable=True)
    partner_course = Column(String(32), nullable=True)
    partner_group = Column(String(64), nullable=True)
    partner_student_id = Column(String(6), nullable=True)
    partner_diploma = Column(String(64), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RegistrationConfig(Base):
    """
    Конфигурация регистрации с атомарным счетчиком мест.
    Должна содержать ровно одну запись с id=1.
    """
    __tablename__ = "registration_config"
    id = Column(Integer, primary_key=True)
    max_capacity = Column(Integer, default=3500, nullable=False)  # Максимум мест
    current_count = Column(Integer, default=0, nullable=False)    # Текущее количество зарегистрированных
    is_open = Column(Boolean, default=True, nullable=False)       # Открыта ли регистрация
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
