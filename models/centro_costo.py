from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)

from extensions import db


class CentroCosto(db.Model):
    __tablename__ = "centros_costo"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"), nullable=False)
    codigo = db.Column(String(30), nullable=False)
    nombre = db.Column(String(120), nullable=False)
    activo = db.Column(Boolean, nullable=False, server_default=text("1"))
