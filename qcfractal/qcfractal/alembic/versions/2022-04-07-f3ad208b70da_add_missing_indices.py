"""add missing indices

Revision ID: f3ad208b70da
Revises: 37bf1ec2b1d1
Create Date: 2022-04-07 15:45:52.735478

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f3ad208b70da"
down_revision = "37bf1ec2b1d1"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index("ix_record_comment_record_id", "record_comment", ["record_id"], unique=False)
    op.create_index("ix_record_info_backup_record_id", "record_info_backup", ["record_id"], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_record_info_backup_record_id", table_name="record_info_backup")
    op.drop_index("ix_record_comment_record_id", table_name="record_comment")
    # ### end Alembic commands ###
