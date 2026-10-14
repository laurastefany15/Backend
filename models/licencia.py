from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)

from extensions import db


class Licencia(db.Model):
    __tablename__ = "licencias"
    __table_args__ = (
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_licencia_fechas"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    tipo = db.Column(String(30), nullable=False)
    remunerada = db.Column(Boolean, nullable=False, server_default=text("0"))
    fecha_inicio = db.Column(Date, nullable=False)
    fecha_fin = db.Column(Date, nullable=False)
    estado = db.Column(String(20), nullable=False, server_default=text("'SOLICITADA'"))
    observaciones = db.Column(Text)
