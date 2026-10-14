from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)

from extensions import db


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"))
    correo = db.Column(String(150), nullable=False, unique=True)
    hash_password = db.Column(Text, nullable=False)
    activo = db.Column(Boolean, nullable=False, server_default=text("1"))
    creado_en = db.Column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
