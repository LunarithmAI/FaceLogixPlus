"""add_performance_indexes

Revision ID: a1b2c3d4e5f6
Revises: bb0f836b8a6a
Create Date: 2026-01-04 04:26:36.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'bb0f836b8a6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'face_embeddings_embedding_idx',
        'face_embeddings',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )

    op.create_index(
        'attendance_logs_org_ts_idx',
        'attendance_logs',
        ['org_id', sa.literal_column('ts DESC')],
        unique=False
    )
    op.create_index(
        'attendance_logs_org_type_idx',
        'attendance_logs',
        ['org_id', 'type'],
        unique=False
    )

    op.create_index(
        'users_org_department_idx',
        'users',
        ['org_id', 'department'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('users_org_department_idx', table_name='users')
    op.drop_index('attendance_logs_org_type_idx', table_name='attendance_logs')
    op.drop_index('attendance_logs_org_ts_idx', table_name='attendance_logs')
    op.drop_index('face_embeddings_embedding_idx', table_name='face_embeddings')
