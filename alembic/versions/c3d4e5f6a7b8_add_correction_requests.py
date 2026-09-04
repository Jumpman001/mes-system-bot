"""add correction requests

Заявки на исправление данных. Записи расхода вносятся один раз и не
редактируются; ошибку исправляет только администратор через заявку.
Старое значение остаётся в таблице — получается журнал изменений.

Revision ID: c3d4e5f6a7b8
Revises: b2e3f4a5c6d7
Create Date: 2026-09-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2e3f4a5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'correction_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'target',
            sa.Enum('CHEMISTRY', 'DRY_MATERIAL', 'LAB_TEST', 'RECEIPT', 'QC_PASSPORT',
                    name='correctiontarget', native_enum=False),
            nullable=False,
            comment='Тип записи: chemistry, dry_material, lab_test, receipt, qc_passport',
        ),
        sa.Column('record_id', sa.Integer(), nullable=False, comment='ID исправляемой записи'),
        sa.Column('field_name', sa.String(length=100), nullable=False,
                  comment='Имя поля, которое меняем'),
        sa.Column('old_value', sa.String(length=200), nullable=True,
                  comment='Значение до исправления'),
        sa.Column('new_value', sa.String(length=200), nullable=True,
                  comment='Запрошенное новое значение'),
        sa.Column('reason', sa.Text(), nullable=False,
                  comment='Причина исправления (обязательно)'),
        sa.Column('requested_by', sa.BigInteger(), nullable=False,
                  comment='Telegram ID заявителя'),
        sa.Column('requested_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'APPROVED', 'REJECTED',
                    name='correctionstatus', native_enum=False),
            nullable=False,
        ),
        sa.Column('reviewed_by', sa.BigInteger(), nullable=True,
                  comment='Telegram ID администратора'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_comment', sa.Text(), nullable=True,
                  comment='Комментарий администратора при отклонении'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_correction_requests_status'),
        'correction_requests', ['status'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_correction_requests_status'), table_name='correction_requests')
    op.drop_table('correction_requests')
