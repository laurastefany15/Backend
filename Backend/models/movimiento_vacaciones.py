from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)

from extensions import db


class MovimientoVacaciones(db.Model):
    __tablename__ = "movimientos_vacaciones"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('CAUSACION', 'DISFRUTE', 'COMPENSACION', 'AJUSTE')",
            name="ck_movimiento_vacaciones_tipo",
        ),
        CheckConstraint("dias <> 0", name="ck_movimiento_vacaciones_dias"),
        Index(
            "uq_descuento_vacacion",
            "vacaciones_id",
            unique=True,
            sqlite_where=text("tipo = 'DISFRUTE' AND vacaciones_id IS NOT NULL"),
        ),
        Index("idx_mov_vacaciones_contrato", "contrato_id", "fecha"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    vacaciones_id = db.Column(ForeignKey("vacaciones.id"))
    fecha = db.Column(Date, nullable=False)
    tipo = db.Column(String(20), nullable=False)
    dias = db.Column(Numeric(10, 3), nullable=False)
    observacion = db.Column(Text)
