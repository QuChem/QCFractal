"""refactor torsiondrive

Revision ID: bb4804242cea
Revises: 31651dcef18d
Create Date: 2021-12-17 10:23:34.593275

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import table, column

from qcfractal.db_socket.column_types import PlainMsgpackExt

# revision identifiers, used by Alembic.
revision = "bb4804242cea"
down_revision = "31651dcef18d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    # Torsiondrive spec table
    op.create_table(
        "torsiondrive_specification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("program", sa.String(length=100), nullable=False),
        sa.Column("optimization_specification_id", sa.Integer(), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("program = LOWER(program)", name="ck_torsiondrive_specification_program_lower"),
        sa.ForeignKeyConstraint(
            ["optimization_specification_id"],
            ["optimization_specification.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "program", "optimization_specification_id", "keywords", name="ux_torsiondrive_specification_keys"
        ),
    )

    op.create_index("ix_torsiondrive_specification_keywords", "torsiondrive_specification", ["keywords"], unique=False)
    op.create_index(
        "ix_torsiondrive_specification_optimization_specification_id",
        "torsiondrive_specification",
        ["optimization_specification_id"],
        unique=False,
    )
    op.create_index("ix_torsiondrive_specification_program", "torsiondrive_specification", ["program"], unique=False)

    # Modify the optimization history table
    op.alter_column("optimization_history", "opt_id", new_column_name="optimization_id")
    op.alter_column("optimization_history", "torsion_id", new_column_name="torsiondrive_id")
    op.drop_constraint("optimization_history_torsion_id_fkey", "optimization_history", type_="foreignkey")
    op.drop_constraint("optimization_history_opt_id_fkey", "optimization_history", type_="foreignkey")
    op.create_foreign_key(
        "torsiondrive_optimizations_torsiondrive_id_fkey",
        "optimization_history",
        "torsiondrive_procedure",
        ["torsiondrive_id"],
        ["id"],
        ondelete="cascade",
    )
    op.create_foreign_key(
        "torsiondrive_optimizations_optimization_id_fkey",
        "optimization_history",
        "optimization_record",
        ["optimization_id"],
        ["id"],
    )

    op.drop_constraint("optimization_history_pkey", "optimization_history", type_="primary")
    op.create_primary_key(
        "torsiondrive_optimizations_pkey",
        "optimization_history",
        ["torsiondrive_id", "optimization_id", "key", "position"],
    )

    # Initial molecule association table
    op.alter_column("torsion_init_mol_association", "torsion_id", new_column_name="torsiondrive_id")
    op.drop_constraint(
        "torsion_init_mol_association_torsion_id_fkey", "torsion_init_mol_association", type_="foreignkey"
    )
    op.drop_constraint(
        "torsion_init_mol_association_molecule_id_fkey", "torsion_init_mol_association", type_="foreignkey"
    )
    op.create_foreign_key(
        "torsiondrive_initial_molecules_torsiondrive_id_fkey",
        "torsion_init_mol_association",
        "torsiondrive_procedure",
        ["torsiondrive_id"],
        ["id"],
        ondelete="cascade",
    )
    op.create_foreign_key(
        "torsiondrive_initial_molecules_molecule_id_fkey",
        "torsion_init_mol_association",
        "molecule",
        ["molecule_id"],
        ["id"],
    )
    op.drop_constraint("torsion_init_mol_association_pkey", "torsion_init_mol_association", type_="primary")
    op.create_primary_key(
        "torsiondrive_initial_molecules_pkey", "torsion_init_mol_association", ["torsiondrive_id", "molecule_id"]
    )

    # The torsiondrive record table itself
    op.add_column("torsiondrive_procedure", sa.Column("specification_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "torsiondrive_record_specification_id_fkey",
        "torsiondrive_procedure",
        "torsiondrive_specification",
        ["specification_id"],
        ["id"],
    )

    op.execute(sa.text("ALTER INDEX torsiondrive_procedure_pkey RENAME TO torsiondrive_record_pkey"))
    op.execute(
        sa.text(
            "ALTER TABLE torsiondrive_procedure RENAME CONSTRAINT torsiondrive_procedure_id_fkey TO torsiondrive_record_id_fkey"
        )
    )

    ###########################################################
    # NOW THE BIG MIGRATION
    ###########################################################
    # change the spec columns to jsonb
    op.execute("ALTER TABLE torsiondrive_procedure ALTER COLUMN qc_spec TYPE JSONB")
    op.execute("ALTER TABLE torsiondrive_procedure ALTER COLUMN optimization_spec TYPE JSONB")
    op.execute("ALTER TABLE torsiondrive_procedure ALTER COLUMN keywords TYPE JSONB")

    # Update the optimization spec with the td keywords additional keywords
    op.execute(
        sa.text(
            r"""UPDATE torsiondrive_procedure
                           SET optimization_spec = optimization_spec || jsonb_build_object('keywords', keywords->'additional_keywords')
                           WHERE keywords ? 'additional_keywords'"""
        )
    )

    # The empty, default keywords
    res = op.get_bind().execute(
        sa.text("SELECT id FROM keywords WHERE hash_index = 'bf21a9e8fbc5a3846fb05b4fa0859e0917b2202f'")
    )
    empty_kw = res.scalar()

    # Fiddle with the specifications
    # First, a hack. The MolSSI database has some old data with a non-existent hash still there. Replace
    # that with the appropriate keyword
    op.execute(
        sa.text(
            r"""UPDATE torsiondrive_procedure SET qc_spec = (qc_spec || '{"keywords": "2"}') WHERE qc_spec->>'keywords' = '5c954fa6b6a2de5f188ea234'"""
        )
    )

    # Remove empty and null keywords
    op.execute(
        sa.text(r"UPDATE torsiondrive_procedure SET qc_spec = (qc_spec - 'keywords') WHERE qc_spec->>'keywords' = ''")
    )
    op.execute(
        sa.text(
            r"UPDATE torsiondrive_procedure SET qc_spec = (qc_spec - 'keywords') WHERE qc_spec->>'keywords' = 'null'"
        )
    )

    # Insert the qcspec
    # Protocols for qc_spec were always ignored. So set them with the default
    op.execute(
        sa.text(
            f"""
               INSERT INTO qc_specification (program, driver, method, basis, keywords_id, protocols)
               SELECT DISTINCT td.qc_spec->>'program',
                               'deferred'::singlepointdriver,
                               td.qc_spec->>'method',
                               COALESCE(td.qc_spec->>'basis', ''),
                               COALESCE((td.qc_spec->>'keywords')::int, {empty_kw}),
                               '{{}}'::jsonb
               FROM torsiondrive_procedure td
               ON CONFLICT DO NOTHING
               """
        )
    )

    # remove explicitly specified default protocols
    op.execute(
        sa.text(
            r"""UPDATE torsiondrive_procedure SET optimization_spec = (optimization_spec || '{"protocols": "{}"}') WHERE optimization_spec->'protocols' = '{"trajectory": "all"}'"""
        )
    )

    # Now the optimization_spec
    op.execute(
        sa.text(
            f"""
               INSERT INTO optimization_specification (program, keywords, protocols, qc_specification_id)
               SELECT DISTINCT td.optimization_spec->>'program',
                               COALESCE(td.optimization_spec->'keywords', '{{}}'),
                               COALESCE(td.optimization_spec->'protocols', '{{}}'),
                               (
                               SELECT id from qc_specification sp
                               WHERE sp.program = td.qc_spec->>'program'
                               AND sp.driver = 'deferred'::singlepointdriver
                               AND sp.method = td.qc_spec->>'method'
                               AND sp.basis = COALESCE(td.qc_spec->>'basis', '')
                               AND sp.keywords_id = COALESCE((td.qc_spec->>'keywords')::int, {empty_kw})
                               AND sp.protocols = '{{}}'
                               )
               FROM torsiondrive_procedure td
               ON CONFLICT DO NOTHING
               """
        )
    )

    # And the torsiondrive spec
    op.execute(
        sa.text(
            f"""
               INSERT INTO torsiondrive_specification (program, keywords, optimization_specification_id)
               SELECT DISTINCT 'torsiondrive',
                               td.keywords,
                               (
                                    SELECT id from optimization_specification os
                                    WHERE os.program = td.optimization_spec->>'program'
                                    AND os.keywords = COALESCE(td.optimization_spec->'keywords', '{{}}')
                                    AND os.protocols = COALESCE(td.optimization_spec->'protocols', '{{}}')
                                    AND os.qc_specification_id =
                                       (
                                           SELECT id from qc_specification sp
                                           WHERE sp.program = td.qc_spec->>'program'
                                           AND sp.driver = 'deferred'::singlepointdriver
                                           AND sp.method = td.qc_spec->>'method'
                                           AND sp.basis = COALESCE(td.qc_spec->>'basis', '')
                                           AND sp.keywords_id = COALESCE((td.qc_spec->>'keywords')::int, {empty_kw})
                                           AND sp.protocols = '{{}}'
                                       )
                                )
               FROM torsiondrive_procedure td
               """
        )
    )

    # Now add this to the torsiondrive spec column
    op.execute(
        sa.text(
            f"""
               UPDATE torsiondrive_procedure td
               SET specification_id = (
                   SELECT id FROM torsiondrive_specification ts
                   WHERE ts.program = 'torsiondrive'
                   AND ts.keywords = td.keywords
                   AND ts.optimization_specification_id = (
                             SELECT id from optimization_specification os
                             WHERE os.program = td.optimization_spec->>'program'
                             AND os.keywords = COALESCE(td.optimization_spec->'keywords', '{{}}')
                             AND os.protocols = COALESCE(td.optimization_spec->'protocols', '{{}}')
                             AND os.qc_specification_id = (
                                    SELECT id from qc_specification sp
                                    WHERE sp.program = td.qc_spec->>'program'
                                    AND sp.driver = 'deferred'::singlepointdriver
                                    AND sp.method = td.qc_spec->>'method'
                                    AND sp.basis = COALESCE(td.qc_spec->>'basis', '')
                                    AND sp.keywords_id = COALESCE((td.qc_spec->>'keywords')::int, {empty_kw})
                                    AND sp.protocols = '{{}}'
                            )
                        )
                   )
               """
        )
    )

    # Now migrate the service queue
    # Temporary ORM
    service_table = table(
        "service_queue",
        column("id", sa.Integer),
        column("service_state", PlainMsgpackExt),
    )

    bind = op.get_bind()
    session = Session(bind=bind)

    services = session.query(service_table).all()

    for service in services:

        if "torsiondrive_state" not in service.service_state:
            continue

        # We have a torsiondrive
        # Remove the optimization template
        service.service_state.pop("optimization_template")
        session.execute(service_table.update().values({"service_state": service.service_state}))

    # drop the final energies and minimum position columns
    op.drop_column("torsiondrive_procedure", "final_energy_dict")
    op.drop_column("torsiondrive_procedure", "minimum_positions")

    # Make columns not nullable now that they are populated
    op.alter_column("torsiondrive_procedure", "specification_id", nullable=False)

    op.drop_column("torsiondrive_procedure", "keywords")
    op.drop_column("torsiondrive_procedure", "optimization_spec")
    op.drop_column("torsiondrive_procedure", "qc_spec")
    op.rename_table("optimization_history", "torsiondrive_optimizations")
    op.rename_table("torsiondrive_procedure", "torsiondrive_record")
    op.rename_table("torsion_init_mol_association", "torsiondrive_initial_molecules")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    raise RuntimeError("Cannot downgrade")
