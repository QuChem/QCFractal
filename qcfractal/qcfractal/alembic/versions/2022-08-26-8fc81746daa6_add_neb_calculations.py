"""add neb calculations

Revision ID: 8fc81746daa6
Revises: f512f2e7ec3d
Create Date: 2022-08-26 16:49:14.688346

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "8fc81746daa6"
down_revision = "f512f2e7ec3d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "neb_dataset",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["base_dataset.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "neb_specification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program", sa.String(length=100), nullable=False),
        sa.Column("singlepoint_specification_id", sa.Integer(), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["singlepoint_specification_id"],
            ["qc_specification.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program", "singlepoint_specification_id", "keywords", name="ux_neb_specification_keys"),
    )
    op.create_index("ix_neb_specification_keywords", "neb_specification", ["keywords"], unique=False)
    op.create_index("ix_neb_specification_program", "neb_specification", ["program"], unique=False)
    op.create_index(
        "ix_neb_specification_singlepoint_specification_id",
        "neb_specification",
        ["singlepoint_specification_id"],
        unique=False,
    )
    op.create_table(
        "neb_dataset_entry",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("additional_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["neb_dataset.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("dataset_id", "name"),
    )
    op.create_index("ix_neb_dataset_entry_dataset_id", "neb_dataset_entry", ["dataset_id"], unique=False)
    op.create_index("ix_neb_dataset_entry_name", "neb_dataset_entry", ["name"], unique=False)
    op.create_table(
        "neb_dataset_specification",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("specification_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["neb_dataset.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["specification_id"],
            ["neb_specification.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "name"),
    )
    op.create_index(
        "ix_neb_dataset_specification_dataset_id", "neb_dataset_specification", ["dataset_id"], unique=False
    )
    op.create_index("ix_neb_dataset_specification_name", "neb_dataset_specification", ["name"], unique=False)
    op.create_index(
        "ix_neb_dataset_specification_specification_id", "neb_dataset_specification", ["specification_id"], unique=False
    )
    op.create_table(
        "neb_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("specification_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["base_record.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["specification_id"],
            ["neb_specification.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "neb_dataset_molecule",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("entry_name", sa.String(), nullable=False),
        sa.Column("molecule_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id", "entry_name"],
            ["neb_dataset_entry.dataset_id", "neb_dataset_entry.name"],
            onupdate="cascade",
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(
            ["molecule_id"],
            ["molecule.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "entry_name", "molecule_id", "position"),
    )
    op.create_index("ix_neb_dataset_molecule_dataset_id", "neb_dataset_molecule", ["dataset_id"], unique=False)
    op.create_index("ix_neb_dataset_molecule_entry_name", "neb_dataset_molecule", ["entry_name"], unique=False)
    op.create_index("ix_neb_dataset_molecule_molecule_id", "neb_dataset_molecule", ["molecule_id"], unique=False)
    op.create_table(
        "neb_dataset_record",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("entry_name", sa.String(), nullable=False),
        sa.Column("specification_name", sa.String(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id", "entry_name"],
            ["neb_dataset_entry.dataset_id", "neb_dataset_entry.name"],
            onupdate="cascade",
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "specification_name"],
            ["neb_dataset_specification.dataset_id", "neb_dataset_specification.name"],
            onupdate="cascade",
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["neb_dataset.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["neb_record.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "entry_name", "specification_name"),
        sa.UniqueConstraint("dataset_id", "entry_name", "specification_name", name="ux_neb_dataset_record_unique"),
    )
    op.create_index("ix_neb_dataset_record_record_id", "neb_dataset_record", ["record_id"], unique=False)
    op.create_table(
        "neb_initialchain",
        sa.Column("neb_id", sa.Integer(), nullable=False),
        sa.Column("molecule_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["molecule_id"], ["molecule.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(["neb_id"], ["neb_record.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("neb_id", "molecule_id", "position"),
    )
    op.create_table(
        "neb_optimizations",
        sa.Column("neb_id", sa.Integer(), nullable=False),
        sa.Column("optimization_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("ts", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["neb_id"], ["neb_record.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["optimization_id"],
            ["optimization_record.id"],
        ),
        sa.PrimaryKeyConstraint("neb_id", "optimization_id", "position", "ts"),
    )
    op.create_table(
        "neb_singlepoints",
        sa.Column("neb_id", sa.Integer(), nullable=False),
        sa.Column("singlepoint_id", sa.Integer(), nullable=False),
        sa.Column("chain_iteration", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["neb_id"], ["neb_record.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["singlepoint_id"],
            ["singlepoint_record.id"],
        ),
        sa.PrimaryKeyConstraint("neb_id", "singlepoint_id", "chain_iteration", "position"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    raise RuntimeError("Cannot downgrade")
    # ### end Alembic commands ###
