"""add user_id to trades and signals

Revision ID: 03237cc58a05
Revises: 65f766e41aac
Create Date: 2026-02-24 19:45:27.729644
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '03237cc58a05'
down_revision: Union[str, None] = '65f766e41aac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch mode for SQLite compatibility (foreign key constraints)
    with op.batch_alter_table('signals') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(), nullable=True))
        batch_op.create_index(op.f('ix_signals_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_signals_user_id', 'users', ['user_id'], ['id'])

    with op.batch_alter_table('trades') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(), nullable=True))
        batch_op.create_index(op.f('ix_trades_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_trades_user_id', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('trades') as batch_op:
        batch_op.drop_constraint('fk_trades_user_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_trades_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('signals') as batch_op:
        batch_op.drop_constraint('fk_signals_user_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_signals_user_id'))
        batch_op.drop_column('user_id')
