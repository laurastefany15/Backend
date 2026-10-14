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


class HoraExtra(db.Model):
    __tablename__ = "horas_extras"
    __table_args__ = (
        CheckConstraint("cantidad_horas > 0", name="ck_hora_extra_cantidad"),
        CheckConstraint(
            "modo_pago_aplicado IS NULL OR modo_pago_aplicado IN ('ADICIONAL', 'COMPLETO')",
            name="ck_hora_extra_modo_pago",
        ),
        CheckConstraint(
            "estado IN ('PENDIENTE', 'APROBADA', 'RECHAZADA', 'LIQUIDADA')",
            name="ck_hora_extra_estado",
        ),
        Index("idx_extras_contrato_fecha", "contrato_id", "fecha", "estado"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    asistencia_id = db.Column(ForeignKey("asistencias.id"))
    tipo_codigo = db.Column(ForeignKey("tipos_recargo.codigo"), nullable=False)
    fecha = db.Column(Date, nullable=False)
    cantidad_horas = db.Column(Numeric(8, 3), nullable=False)
    valor_hora_base = db.Column(Numeric(15, 4))
    porcentaje_aplicado = db.Column(Numeric(8, 4))
    modo_pago_aplicado = db.Column(String(12))
    valor_calculado = db.Column(Numeric(15, 2))
    estado = db.Column(String(15), nullable=False, server_default=text("'PENDIENTE'"))
    aprobado_por = db.Column(ForeignKey("usuarios.id"))
    observaciones = db.Column(Text)
