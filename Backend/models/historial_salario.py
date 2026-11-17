from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)

from extensions import db


class HistorialSalario(db.Model):
    __tablename__ = "historial_salarios"
    __table_args__ = (
        CheckConstraint("salario_mensual >= 0", name="ck_historial_salario"),
        UniqueConstraint("contrato_id", "vigente_desde"),
        Index("idx_salarios_contrato_fecha", "contrato_id", "vigente_desde"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    vigente_desde = db.Column(Date, nullable=False)
    salario_mensual = db.Column(Numeric(15, 2), nullable=False)
    observacion = db.Column(Text)
