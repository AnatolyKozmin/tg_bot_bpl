"""initial

Revision ID: 0001
Revises: 
Create Date: 2025-10-23
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'


def upgrade():
    op.create_table(
        'surveys',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('consent', sa.Boolean, nullable=False),
        sa.Column('fio', sa.String(length=255), nullable=True),
        sa.Column('group', sa.String(length=64), nullable=True),
        sa.Column('student_id', sa.String(length=64), nullable=True),
    sa.Column('telegram_id', sa.String(length=64), nullable=True),
    sa.Column('telegram_username', sa.String(length=255), nullable=True),
        sa.Column('pair_or_single', sa.String(length=16), nullable=True),
        sa.Column('partner_status', sa.String(length=32), nullable=True),
        sa.Column('partner_fio', sa.String(length=255), nullable=True),
        sa.Column('partner_group', sa.String(length=64), nullable=True),
        sa.Column('partner_student_id', sa.String(length=64), nullable=True),
        sa.Column('partner_diploma', sa.String(length=64), nullable=True),
    )


def downgrade():
    op.drop_table('surveys')
