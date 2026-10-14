from sqlalchemy import (
    ForeignKey,
    PrimaryKeyConstraint,
)

from extensions import db


class UsuarioRol(db.Model):
    __tablename__ = "usuarios_roles"
    __table_args__ = (PrimaryKeyConstraint("usuario_id", "rol_id"),)

    usuario_id = db.Column(ForeignKey("usuarios.id"), nullable=False)
    rol_id = db.Column(ForeignKey("roles.id"), nullable=False)
