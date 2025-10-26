"""add registration config and optimize survey table

Revision ID: 0002
Revises: 0001
Create Date: 2025-10-26
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = '0002'
down_revision = '0001'


def upgrade():
    # 1. Добавляем таблицу для конфигурации регистрации
    op.create_table(
        'registration_config',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('max_capacity', sa.Integer, nullable=False, server_default='3500'),
        sa.Column('current_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_open', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    
    # 2. Инициализируем конфигурацию (вставляем первую запись)
    op.execute("""
        INSERT INTO registration_config (id, max_capacity, current_count, is_open, updated_at)
        VALUES (1, 3500, 0, true, CURRENT_TIMESTAMP)
    """)
    
    # 3. Обновляем таблицу surveys
    # Добавляем индекс на telegram_id для быстрого поиска
    op.create_index('ix_surveys_telegram_id', 'surveys', ['telegram_id'], unique=True)
    
    # Добавляем поле created_at для аналитики
    op.add_column('surveys', sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP')))


def downgrade():
    # Откатываем изменения в обратном порядке
    op.drop_column('surveys', 'created_at')
    op.drop_index('ix_surveys_telegram_id', table_name='surveys')
    op.drop_table('registration_config')

