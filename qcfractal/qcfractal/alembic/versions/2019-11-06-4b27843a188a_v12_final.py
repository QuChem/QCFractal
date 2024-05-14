"""Final migration synchronization from v0.11 to v0.12

Revision ID: 4b27843a188a
Revises: 159ba85908fd
Create Date: 2019-11-06 13:48:39.716633

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "4b27843a188a"
down_revision = "159ba85908fd"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "collection", "group", existing_type=sa.VARCHAR(), type_=sa.String(length=100), existing_nullable=False
    )
    op.alter_column("molecule", "geometry", existing_type=postgresql.BYTEA(), nullable=False)
    op.alter_column("molecule", "symbols", existing_type=postgresql.BYTEA(), nullable=False)
    op.alter_column("task_queue", "spec", existing_type=postgresql.BYTEA(), nullable=False)
    op.drop_constraint("task_queue_manager_fkey", "task_queue", type_="foreignkey")
    op.create_foreign_key(
        "task_queue_manager_fkey", "task_queue", "queue_manager", ["manager"], ["name"], ondelete="SET NULL"
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint("task_queue_manager_fkey", "task_queue", type_="foreignkey")
    op.create_foreign_key("task_queue_manager_fkey", "task_queue", "queue_manager", ["manager"], ["name"])
    op.alter_column("task_queue", "spec", existing_type=postgresql.BYTEA(), nullable=True)
    op.alter_column("molecule", "symbols", existing_type=postgresql.BYTEA(), nullable=True)
    op.alter_column("molecule", "geometry", existing_type=postgresql.BYTEA(), nullable=True)
    op.alter_column(
        "collection", "group", existing_type=sa.String(length=100), type_=sa.VARCHAR(), existing_nullable=False
    )
    # ### end Alembic commands ###
