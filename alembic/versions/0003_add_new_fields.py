"""add new fields for improved registration flow

Revision ID: 0003
Revises: 0002
Create Date: 2025-10-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'


def upgrade():
    # Добавляем новые поля с сохранением существующих данных
    
    # Новые поля для основного участника
    op.add_column('surveys', sa.Column('is_student', sa.Boolean(), nullable=True))
    op.add_column('surveys', sa.Column('faculty', sa.String(length=64), nullable=True))
    op.add_column('surveys', sa.Column('course', sa.String(length=32), nullable=True))
    op.add_column('surveys', sa.Column('diploma_number', sa.String(length=64), nullable=True))
    
    # Поля для управления билетами
    op.add_column('surveys', sa.Column('ticket_sent', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('surveys', sa.Column('ticket_cancelled', sa.Boolean(), server_default='false', nullable=False))
    
    # Новые поля для партнера
    op.add_column('surveys', sa.Column('partner_faculty', sa.String(length=64), nullable=True))
    op.add_column('surveys', sa.Column('partner_course', sa.String(length=32), nullable=True))
    
    # Метаданные
    op.add_column('surveys', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True))
    
    # Изменяем длину поля student_id до 6 символов (было 64)
    # Сначала для основного
    op.alter_column('surveys', 'student_id',
                    existing_type=sa.String(length=64),
                    type_=sa.String(length=6),
                    existing_nullable=True)
    
    # Затем для партнера
    op.alter_column('surveys', 'partner_student_id',
                    existing_type=sa.String(length=64),
                    type_=sa.String(length=6),
                    existing_nullable=True)
    
    # Для существующих записей устанавливаем is_student=True если есть student_id
    op.execute("""
        UPDATE surveys 
        SET is_student = TRUE 
        WHERE student_id IS NOT NULL AND student_id != ''
    """)


def downgrade():
    # Откат изменений
    op.drop_column('surveys', 'updated_at')
    op.drop_column('surveys', 'partner_course')
    op.drop_column('surveys', 'partner_faculty')
    op.drop_column('surveys', 'ticket_cancelled')
    op.drop_column('surveys', 'ticket_sent')
    op.drop_column('surveys', 'diploma_number')
    op.drop_column('surveys', 'course')
    op.drop_column('surveys', 'faculty')
    op.drop_column('surveys', 'is_student')
    
    # Возвращаем длину полей student_id
    op.alter_column('surveys', 'student_id',
                    existing_type=sa.String(length=6),
                    type_=sa.String(length=64),
                    existing_nullable=True)
    
    op.alter_column('surveys', 'partner_student_id',
                    existing_type=sa.String(length=6),
                    type_=sa.String(length=64),
                    existing_nullable=True)

