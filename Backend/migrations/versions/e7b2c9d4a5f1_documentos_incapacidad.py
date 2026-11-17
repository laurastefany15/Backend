"""Store disability documents as uploaded files instead of URLs.

Revision ID: e7b2c9d4a5f1
Revises: c4d8f1a27b63
Create Date: 2026-10-26 15:20:00
"""
import sqlalchemy as sa
from alembic import op


revision = "e7b2c9d4a5f1"
down_revision = "c4d8f1a27b63"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_incapacidades")
    op.create_table(
        "documentos_incapacidad",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incapacidad_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=30), server_default=sa.text("'OTRO'"), nullable=False),
        sa.Column("nombre_original", sa.String(length=255), nullable=False),
        sa.Column("nombre_archivo", sa.String(length=80), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("subido_por", sa.Integer(), nullable=True),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo IN ('CERTIFICADO_EPS', 'HISTORIA_CLINICA', 'TRANSCRIPCION', 'OTRO')",
            name="ck_documento_incapacidad_tipo",
        ),
        sa.CheckConstraint("tamano_bytes > 0", name="ck_documento_incapacidad_tamano"),
        sa.ForeignKeyConstraint(["incapacidad_id"], ["incapacidades.id"]),
        sa.ForeignKeyConstraint(["subido_por"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre_archivo"),
    )
    with op.batch_alter_table("documentos_incapacidad") as batch_op:
        batch_op.create_index("idx_documentos_incapacidad", ["incapacidad_id"], unique=False)
    with op.batch_alter_table("incapacidades") as batch_op:
        batch_op.drop_column("documento_soporte_url")


def downgrade():
    with op.batch_alter_table("incapacidades") as batch_op:
        batch_op.add_column(sa.Column("documento_soporte_url", sa.Text(), nullable=True))
    with op.batch_alter_table("documentos_incapacidad") as batch_op:
        batch_op.drop_index("idx_documentos_incapacidad")
    op.drop_table("documentos_incapacidad")
