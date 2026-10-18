from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from extensions import db


class Sede(db.Model):
    __tablename__ = "sedes"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"), nullable=False)
    nombre = db.Column(String(120), nullable=False)
    direccion = db.Column(Text)
