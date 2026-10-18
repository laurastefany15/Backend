from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)

from extensions import db


class PagoNomina(db.Model):
    __tablename__ = "pagos_nomina"
    __table_args__ = (
        CheckConstraint("valor > 0", name="ck_pago_nomina_valor"),
        CheckConstraint(
            "medio IN ('TRANSFERENCIA', 'EFECTIVO', 'CHEQUE', 'OTRO')",
            name="ck_pago_nomina_medio",
        ),
    )

    id = db.Column(Integer, primary_key=True)
    nomina_id = db.Column(ForeignKey("nominas.id"), nullable=False)
    fecha_pago = db.Column(Date, nullable=False)
    valor = db.Column(Numeric(15, 2), nullable=False)
    medio = db.Column(String(20), nullable=False)
    referencia = db.Column(String(100))
    observaciones = db.Column(Text)
