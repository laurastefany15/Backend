"""Remove sedes; each company has one implicit location.

Revision ID: a91c6e2b4f10
Revises: 4f3b2a9c1d7e
Create Date: 2026-10-19 16:20:00
"""
import sqlalchemy as sa
from alembic import op


revision = "a91c6e2b4f10"
down_revision = "4f3b2a9c1d7e"
branch_labels = None
depends_on = None


def _drop_contract_views():
    op.execute("DROP VIEW IF EXISTS vw_saldo_vacaciones")
    op.execute("DROP VIEW IF EXISTS vw_resumen_nomina")


def _create_contract_views():
    op.execute(
        """
        CREATE VIEW vw_saldo_vacaciones AS
        SELECT c.id AS contrato_id, c.empleado_id,
               COALESCE(SUM(m.dias), 0) AS dias_saldo
        FROM contratos c
        LEFT JOIN movimientos_vacaciones m ON m.contrato_id = c.id
        GROUP BY c.id, c.empleado_id
        """
    )
    op.execute(
        """
        CREATE VIEW vw_resumen_nomina AS
        SELECT n.id AS nomina_id, e.empresa_id, e.numero_documento, e.nombres, e.apellidos,
               p.fecha_inicio, p.fecha_fin, n.total_devengado, n.total_deducciones,
               n.neto_pagar, n.estado
        FROM nominas n
        JOIN contratos c ON c.id = n.contrato_id
        JOIN empleados e ON e.id = c.empleado_id
        JOIN periodos_nomina p ON p.id = n.periodo_id
        """
    )


def upgrade():
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_contratos")
    _drop_contract_views()
    with op.batch_alter_table("contratos") as batch_op:
        batch_op.drop_column("sede_id")
    _create_contract_views()
    op.drop_table("sedes")


def downgrade():
    _drop_contract_views()
    op.create_table(
        "sedes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "nombre"),
    )
    with op.batch_alter_table("contratos") as batch_op:
        batch_op.add_column(sa.Column("sede_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_contratos_sede_id",
            "sedes",
            ["sede_id"],
            ["id"],
        )
    _create_contract_views()
