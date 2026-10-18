from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)

from extensions import db


class DetalleNomina(db.Model):
    __tablename__ = "detalles_nomina"
    __table_args__ = (
        CheckConstraint("valor >= 0", name="ck_detalle_nomina_valor"),
        Index("idx_detalles_nomina", "nomina_id"),
    )

    id = db.Column(Integer, primary_key=True)
    nomina_id = db.Column(ForeignKey("nominas.id"), nullable=False)
    concepto_id = db.Column(ForeignKey("conceptos_nomina.id"), nullable=False)
    cantidad = db.Column(Numeric(12, 3))
    valor_unitario = db.Column(Numeric(15, 4))
    porcentaje_aplicado = db.Column(Numeric(8, 4))
    valor = db.Column(Numeric(15, 2), nullable=False)
    origen_tipo = db.Column(String(30))
    origen_id = db.Column(Integer)
    descripcion = db.Column(Text)
