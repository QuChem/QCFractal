"""Add check constraints for tags

Revision ID: 37bf1ec2b1d1
Revises: 45b5ec1ed88b
Create Date: 2022-04-03 10:50:30.660492

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import column, func


# revision identifiers, used by Alembic.
revision = "37bf1ec2b1d1"
down_revision = "45b5ec1ed88b"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute(sa.text("UPDATE task_queue SET tag = LOWER(tag)"))
    op.execute(sa.text("UPDATE service_queue SET tag = LOWER(tag)"))
    op.execute(sa.text("UPDATE compute_manager SET tags = LOWER(tags::text)::text[]"))
    op.execute(sa.text("UPDATE compute_manager SET programs = LOWER(programs::text)::json"))

    op.create_check_constraint(
        "ck_task_queue_tag_lower",
        "task_queue",
        column("tag").cast(sa.TEXT) == func.lower(column("tag").cast(sa.TEXT)),
    )

    op.create_check_constraint(
        "ck_service_queue_tag_lower",
        "service_queue",
        column("tag").cast(sa.TEXT) == func.lower(column("tag").cast(sa.TEXT)),
    )

    op.create_check_constraint(
        "ck_compute_manager_programs_lower",
        "compute_manager",
        column("programs").cast(sa.TEXT) == func.lower(column("programs").cast(sa.TEXT)),
    )

    op.create_check_constraint(
        "ck_compute_manager_tags_lower",
        "compute_manager",
        column("tags").cast(sa.TEXT) == func.lower(column("tags").cast(sa.TEXT)),
    )
    # ### end Alembic commands ###


def downgrade():
    raise RuntimeError("Cannot downgrade")