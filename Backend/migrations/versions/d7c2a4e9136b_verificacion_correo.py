"""Agregar verificación de correo a usuarios."""
import sqlalchemy as sa
from alembic import op


revision = "d7c2a4e9136b"
down_revision = "b6e1a8c34d20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column(
            "correo_verificado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column("token_verificacion_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "usuarios",
        sa.Column(
            "token_verificacion_expira_en", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_index(
        "ix_usuarios_token_verificacion_hash",
        "usuarios",
        ["token_verificacion_hash"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_usuarios_token_verificacion_hash", table_name="usuarios")
    op.drop_column("usuarios", "token_verificacion_expira_en")
    op.drop_column("usuarios", "token_verificacion_hash")
    op.drop_column("usuarios", "correo_verificado")
