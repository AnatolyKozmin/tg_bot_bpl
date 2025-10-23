from sqlalchemy import Column, Integer, String, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True)
    consent = Column(Boolean, default=False)
    fio = Column(String(255))
    group = Column(String(64))
    student_id = Column(String(64))
    telegram_id = Column(String(64), nullable=True)
    telegram_username = Column(String(255), nullable=True)
    pair_or_single = Column(String(16))
    partner_status = Column(String(32), nullable=True)
    partner_fio = Column(String(255), nullable=True)
    partner_group = Column(String(64), nullable=True)
    partner_student_id = Column(String(64), nullable=True)
    partner_diploma = Column(String(64), nullable=True)
