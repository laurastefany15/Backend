"""Roles de plataforma y acceso de un usuario a varias empresas.

Revision ID: b6e1a8c34d20
Revises: e7b2c9d4a5f1
Create Date: 2026-11-11 15:10:00
"""
import sqlalchemy as sa
from alembic import op


revision = "b6e1a8c34d20"
down_revision = "e7b2c9d4a5f1"
branch_labels = None
depends_on = None


def _sqlite_fk(enabled):
    with op.get_context().autocommit_block():
        op.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def upgrade():
    op.execute(
        """
        INSERT INTO roles (codigo, descripcion)
        SELECT 'SUPERUSER', 'Administrador del software'
        WHERE NOT EXISTS (SELECT 1 FROM roles WHERE codigo = 'SUPERUSER')
        """
    )
    op.execute(
        """
        INSERT INTO roles (codigo, descripcion)
        SELECT 'USUARIO', 'Usuario de una o varias empresas'
        WHERE NOT EXISTS (SELECT 1 FROM roles WHERE codigo = 'USUARIO')
        """
    )
    op.create_table(
        "usuarios_empresas",
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("usuario_id", "empresa_id"),
    )
    op.execute(
        """
        INSERT INTO usuarios_empresas (usuario_id, empresa_id)
        SELECT id, empresa_id FROM usuarios WHERE empresa_id IS NOT NULL
        """
    )
    op.add_column("empresas", sa.Column("propietario_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE empresas
        SET propietario_id = (
            SELECT u.id
            FROM usuarios u
            JOIN usuarios_roles ur ON ur.usuario_id = u.id
            JOIN roles r ON r.id = ur.rol_id AND r.codigo = 'ADMIN'
            WHERE u.empresa_id = empresas.id
            ORDER BY u.id
            LIMIT 1
        )
        """
    )
    op.execute(
        """
        UPDATE empresas
        SET propietario_id = (
            SELECT u.id
            FROM usuarios u
            WHERE u.empresa_id = empresas.id
            ORDER BY u.id
            LIMIT 1
        )
        WHERE propietario_id IS NULL
        """
    )
    op.add_column("usuarios", sa.Column("creado_por_id", sa.Integer(), nullable=True))
    _sqlite_fk(False)
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_column("empresa_id")
    _sqlite_fk(True)


def downgrade():
    _sqlite_fk(False)
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(sa.Column("empresa_id", sa.Integer(), nullable=True))
    _sqlite_fk(True)
    op.execute(
        """
        UPDATE usuarios
        SET empresa_id = (
            SELECT empresa_id
            FROM usuarios_empresas
            WHERE usuarios_empresas.usuario_id = usuarios.id
            ORDER BY empresa_id
            LIMIT 1
        )
        """
    )
    op.execute("ALTER TABLE usuarios DROP COLUMN creado_por_id")
    op.execute("ALTER TABLE empresas DROP COLUMN propietario_id")
    op.drop_table("usuarios_empresas")
    op.execute(
        """
        DELETE FROM usuarios_roles
        WHERE rol_id IN (
            SELECT id FROM roles WHERE codigo IN ('SUPERUSER', 'USUARIO')
        )
        """
    )
    op.execute("DELETE FROM roles WHERE codigo IN ('SUPERUSER', 'USUARIO')")
