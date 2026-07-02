"""add task photo_file_id

Фото-схема трубы: админ прикреплял её в FSM создания задачи,
но поле в БД отсутствовало и file_id молча терялся.

Revision ID: a1f2c3d4e5b6
Revises: 0241b9e47f20
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5b6'
down_revision: Union[str, Sequence[str], None] = '0241b9e47f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tasks',
        sa.Column(
            'photo_file_id', sa.String(length=200), nullable=True,
            comment='Telegram file_id фото-схемы трубы (прикрепляет Админ)',
        ),
    )


def downgrade() -> None:
    op.drop_column('tasks', 'photo_file_id')
