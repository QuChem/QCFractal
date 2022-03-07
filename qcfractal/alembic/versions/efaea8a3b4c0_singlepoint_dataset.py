"""singlepoint dataset

Revision ID: efaea8a3b4c0
Revises: bf4b379a6ce4
Create Date: 2022-02-21 10:19:54.041035

"""
import os
import sys
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import table, column

sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))
from migration_helpers.v0_50_helpers import get_empty_keywords_id, add_opt_spec, add_qc_spec

# revision identifiers, used by Alembic.
revision = "efaea8a3b4c0"
down_revision = "bf4b379a6ce4"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "singlepoint_dataset_specification",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("specification_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["specification_id"],
            ["qc_specification.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "name"),
    )
    op.create_index(
        "ix_singlepoint_dataset_specification_dataset_id",
        "singlepoint_dataset_specification",
        ["dataset_id"],
        unique=False,
    )
    op.create_index(
        "ix_singlepoint_dataset_specification_name", "singlepoint_dataset_specification", ["name"], unique=False
    )
    op.create_index(
        "ix_singlepoint_dataset_specification_specification_id",
        "singlepoint_dataset_specification",
        ["specification_id"],
        unique=False,
    )

    op.create_table(
        "singlepoint_dataset_record",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("entry_name", sa.String(), nullable=False),
        sa.Column("specification_name", sa.String(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id", "entry_name"],
            ["dataset_entry.dataset_id", "dataset_entry.name"],
            onupdate="cascade",
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "specification_name"],
            ["singlepoint_dataset_specification.dataset_id", "singlepoint_dataset_specification.name"],
            onupdate="cascade",
            ondelete="cascade",
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["singlepoint_record.id"],
        ),
        sa.PrimaryKeyConstraint("dataset_id", "entry_name", "specification_name"),
        sa.UniqueConstraint(
            "dataset_id", "entry_name", "specification_name", name="ux_singlepoint_dataset_record_unique"
        ),
    )
    op.create_index(
        "ix_singlepoint_dataset_record_record_id", "singlepoint_dataset_record", ["record_id"], unique=False
    )

    # Rename dataset table pkey
    op.execute(sa.text("ALTER INDEX dataset_pkey RENAME TO singlepoint_dataset_pkey"))

    op.add_column(
        "dataset_entry", sa.Column("additional_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("dataset_entry", sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key(
        "singlepoint_dataset_entry_dataset_id_fkey",
        "dataset_entry",
        "dataset",
        ["dataset_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index("ix_singlepoint_dataset_entry_dataset_id", "dataset_entry", ["dataset_id"], unique=False)

    op.create_index("ix_singlepoint_dataset_entry_molecule_id", "dataset_entry", ["molecule_id"], unique=False)

    op.create_index("ix_singlepoint_dataset_entry_name", "dataset_entry", ["name"], unique=False)

    op.create_foreign_key(
        "singlepoint_dataset_entry_molecule_id_fkey", "dataset_entry", "molecule", ["molecule_id"], ["id"]
    )
    op.drop_constraint("dataset_entry_molecule_id_fkey", "dataset_entry", type_="foreignkey")
    op.drop_constraint("dataset_entry_dataset_id_fkey", "dataset_entry", type_="foreignkey")

    # dataset entry pkey and fkey
    op.drop_constraint("dataset_id_fkey", "dataset", type_="foreignkey")
    op.create_foreign_key("singlepoint_dataset_id_fkey", "dataset", "collection", ["id"], ["id"], ondelete="CASCADE")
    op.execute(sa.text("ALTER INDEX dataset_entry_pkey RENAME TO singlepoint_dataset_entry_pkey"))

    ##############################
    # DATA MIGRATION
    ##############################
    conn = op.get_bind()

    op.execute(sa.text("UPDATE collection SET collection_type = 'singlepoint' where collection = 'dataset'"))
    op.execute(sa.text("UPDATE collection SET collection = 'singlepoint' where collection = 'dataset'"))

    # Temporary ORM
    dataset_table = table(
        "dataset",
        column("id", sa.Integer),
        column("history", sa.JSON),
        column("history_keys", sa.JSON),
        column("alias_keywords", sa.JSON),
    )

    session = Session(conn)
    datasets = session.query(dataset_table).all()

    empty_kw = get_empty_keywords_id(conn)

    for ds in datasets:
        spec_idx = 1
        for h in ds["history"]:
            spec = dict(zip(ds["history_keys"], h))

            # keywords should be in alias_keywords, except for dftd3 directly run through the
            # composition planner......
            try:
                kw = ds["alias_keywords"][spec["program"]][spec["keywords"]]
            except KeyError:
                if spec["program"] == "dftd3":
                    kw = empty_kw
                else:
                    raise RuntimeError(f"Missing entry from alias_keywords: {spec['program']}, {spec['keywords']}")

            if kw is None:
                kw = empty_kw
            if spec["basis"] is None:
                spec["basis"] = ""

            # What specifications match? Protocols wasn't taken into account
            res = conn.execute(
                sa.text(
                    """
                    SELECT q.id FROM qc_specification q
                    WHERE q.program = :program
                    AND q.driver = :driver
                    AND q.method = :method
                    AND q.basis = :basis
                    AND q.keywords_id = :keywords_id
                    """
                ),
                col_id=ds["id"],
                program=spec["program"],
                driver=spec["driver"],
                method=spec["method"],
                basis="" if spec["basis"] is None else spec["basis"],
                keywords_id=kw,
            )

            spec_ids = res.scalars().all()

            # If not already existing, add it
            if len(spec_ids) == 0:
                sid = add_qc_spec(
                    conn,
                    spec["program"],
                    spec["driver"],
                    spec["method"],
                    spec["basis"],
                    kw,
                    spec.get("protocols", {}),
                )

                spec_ids = [sid]

            # Add these to the spec table
            for sid in spec_ids:
                spec_name = f"spec_{spec_idx}"
                spec_idx += 1

                conn.execute(
                    sa.text(
                        """INSERT INTO singlepoint_dataset_specification (dataset_id, name, description, specification_id)
                                      VALUES (:col_id, :spec_name, :spec_desc, :qc_spec_id)"""
                    ),
                    col_id=ds["id"],
                    spec_name=spec_name,
                    spec_desc="",
                    qc_spec_id=sid,
                )

                # Now what records match these specs
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO singlepoint_dataset_record (dataset_id, entry_name, specification_name, record_id)
                        SELECT e.dataset_id, e.name, s.name, r.id
                        FROM dataset_entry e, singlepoint_dataset_specification s, singlepoint_record r 
                        WHERE e.dataset_id = :col_id
                        AND s.dataset_id = :col_id
                        AND s.specification_id = r.specification_id
                        AND r.specification_id = :qc_spec_id
                        AND e.molecule_id = r.molecule_id
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    col_id=ds["id"],
                    qc_spec_id=sid,
                )

    # Drop old dataset columns
    op.drop_column("dataset", "default_benchmark")
    op.drop_column("dataset", "default_program")
    op.drop_column("dataset", "default_driver")
    op.drop_column("dataset", "default_keywords")
    op.drop_column("dataset", "default_units")
    op.drop_column("dataset", "history")
    op.drop_column("dataset", "history_keys")
    op.drop_column("dataset", "alias_keywords")

    # Finally rename the tables
    op.rename_table("dataset", "singlepoint_dataset")
    op.rename_table("dataset_entry", "singlepoint_dataset_entry")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    raise RuntimeError("Cannot downgrade")