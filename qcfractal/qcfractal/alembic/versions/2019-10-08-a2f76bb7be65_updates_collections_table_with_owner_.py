"""Updates collections table with owner and visibility

Revision ID: a2f76bb7be65
Revises: c194a8ef6acf
Create Date: 2019-10-08 11:06:15.438742

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a2f76bb7be65"
down_revision = "c194a8ef6acf"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("collection", sa.Column("description", sa.String(), nullable=True))

    op.add_column("collection", sa.Column("group", sa.String(), nullable=False, server_default="default"))
    op.alter_column("collection", "group", server_default=None)

    op.add_column("collection", sa.Column("view_url_hdf5", sa.String(), nullable=True))
    op.add_column("collection", sa.Column("view_url_plaintext", sa.String(), nullable=True))
    op.add_column("collection", sa.Column("view_metadata", sa.JSON(), nullable=True))

    op.add_column("collection", sa.Column("view_available", sa.Boolean(), nullable=True))
    op.execute("UPDATE collection SET view_available=false")
    op.alter_column("collection", "view_available", nullable=False)

    op.add_column("collection", sa.Column("visibility", sa.Boolean(), nullable=True))
    op.execute("UPDATE collection SET visibility=true")
    op.alter_column("collection", "visibility", nullable=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("collection", "visibility")
    op.drop_column("collection", "view_url_hdf5")
    op.drop_column("collection", "view_url_plaintext")
    op.drop_column("collection", "view_metadata")
    op.drop_column("collection", "view_available")
    op.drop_column("collection", "group")
    op.drop_column("collection", "metadata")
    op.drop_column("collection", "description")
    # ### end Alembic commands ###
