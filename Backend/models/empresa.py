from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)

from extensions import db


class Empresa(db.Model):
    __tablename__ = "empresas"

    id = db.Column(Integer, primary_key=True)
    propietario_id = db.Column(ForeignKey("usuarios.id"))
    nit = db.Column(String(30), nullable=False, unique=True)
    razon_social = db.Column(String(200), nullable=False)
    direccion = db.Column(Text)
    telefono = db.Column(String(30))
    correo = db.Column(String(150))
    activa = db.Column(Boolean, nullable=False, server_default=text("1"))
