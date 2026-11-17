from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text

from extensions import db


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(Integer, primary_key=True)
    creado_por_id = db.Column(ForeignKey("usuarios.id"))
    correo = db.Column(String(150), nullable=False, unique=True)
    hash_password = db.Column(Text, nullable=False)
    correo_verificado = db.Column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    token_verificacion_hash = db.Column(String(64), unique=True, index=True)
    token_verificacion_expira_en = db.Column(DateTime(timezone=True))
    activo = db.Column(Boolean, nullable=False, server_default=text("1"))
    creado_en = db.Column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
