from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    text,
)

from extensions import db


class Auditoria(db.Model):
    __tablename__ = "auditoria"

    id = db.Column(Integer, primary_key=True)
    usuario_id = db.Column(ForeignKey("usuarios.id"))
    tabla = db.Column(String(100), nullable=False)
    registro_id = db.Column(Integer)
    accion = db.Column(String(20), nullable=False)
    antes = db.Column(JSON)
    despues = db.Column(JSON)
    creado_en = db.Column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
