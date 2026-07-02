"""add integrity constraints

- uq_pipe_norm_type: один норматив на тип трубы (dn, pn, sn, with_sand) —
  upsert делал select-then-insert и при гонке плодил дубликаты.
- uq_active_stage_per_pipe: частичный уникальный индекс — у трубы не может
  быть двух незакрытых записей одной стадии (защита от двойного СТАРТА).

Revision ID: b2e3f4a5c6d7
Revises: a1f2c3d4e5b6
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2e3f4a5c6d7'
down_revision: Union[str, Sequence[str], None] = 'a1f2c3d4e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_pipe_norm_type', 'pipe_norms', ['dn', 'pn', 'sn', 'with_sand'],
    )
    op.create_index(
        'uq_active_stage_per_pipe',
        'production_stages',
        ['pipe_id', 'stage'],
        unique=True,
        postgresql_where=sa.text('end_time IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_active_stage_per_pipe', table_name='production_stages')
    op.drop_constraint('uq_pipe_norm_type', 'pipe_norms', type_='unique')
