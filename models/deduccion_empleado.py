from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)

from extensions import db


class DeduccionEmpleado(db.Model):
    __tablename__ = "deducciones_empleado"
    __table_args__ = (
        CheckConstraint("valor_cuota > 0", name="ck_deduccion_cuota"),
        CheckConstraint(
            "periodicidad IN ('UNICA', 'POR_PERIODO')", name="ck_deduccion_periodicidad"
        ),
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta >= vigente_desde",
            name="ck_deduccion_vigencia",
        ),
        CheckConstraint("monto_original IS NULL OR monto_original >= 0", name="ck_deduccion_monto"),
        CheckConstraint(
            "saldo_pendiente IS NULL OR saldo_pendiente >= 0", name="ck_deduccion_saldo"
        ),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    concepto_id = db.Column(ForeignKey("conceptos_nomina.id"), nullable=False)
    descripcion = db.Column(Text)
    monto_original = db.Column(Numeric(15, 2))
    saldo_pendiente = db.Column(Numeric(15, 2))
    valor_cuota = db.Column(Numeric(15, 2), nullable=False)
    vigente_desde = db.Column(Date, nullable=False)
    vigente_hasta = db.Column(Date)
    periodicidad = db.Column(
        String(20), nullable=False, server_default=text("'POR_PERIODO'")
    )
    activa = db.Column(Boolean, nullable=False, server_default=text("1"))
