from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)

from extensions import db


class PeriodoNomina(db.Model):
    __tablename__ = "periodos_nomina"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('SEMANAL', 'QUINCENAL', 'MENSUAL')", name="ck_periodo_tipo"
        ),
        CheckConstraint(
            "estado IN ('ABIERTO', 'EN_REVISION', 'CERRADO')", name="ck_periodo_estado"
        ),
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_periodo_fechas"),
        UniqueConstraint("empresa_id", "tipo", "fecha_inicio", "fecha_fin"),
    )

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"), nullable=False)
    tipo = db.Column(String(15), nullable=False)
    fecha_inicio = db.Column(Date, nullable=False)
    fecha_fin = db.Column(Date, nullable=False)
    fecha_pago = db.Column(Date, nullable=False)
    estado = db.Column(String(15), nullable=False, server_default=text("'ABIERTO'"))
