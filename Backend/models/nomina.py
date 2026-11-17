from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)

from extensions import db


class Nomina(db.Model):
    __tablename__ = "nominas"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('BORRADOR', 'APROBADA', 'PAGADA', 'ANULADA')",
            name="ck_nomina_estado",
        ),
        CheckConstraint("salario_referencia >= 0", name="ck_nomina_salario"),
        CheckConstraint("total_devengado >= 0", name="ck_nomina_devengado"),
        CheckConstraint("total_deducciones >= 0", name="ck_nomina_deducciones"),
        UniqueConstraint("contrato_id", "periodo_id"),
        Index("idx_nominas_periodo", "periodo_id"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    periodo_id = db.Column(ForeignKey("periodos_nomina.id"), nullable=False)
    salario_referencia = db.Column(Numeric(15, 2), nullable=False, server_default=text("0"))
    total_devengado = db.Column(Numeric(15, 2), nullable=False, server_default=text("0"))
    total_deducciones = db.Column(Numeric(15, 2), nullable=False, server_default=text("0"))
    neto_pagar = db.Column(
        Numeric(15, 2),
        Computed("total_devengado - total_deducciones", persisted=True),
    )
    estado = db.Column(String(15), nullable=False, server_default=text("'BORRADOR'"))
    fecha_liquidacion = db.Column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    aprobada_por = db.Column(ForeignKey("usuarios.id"))
    observaciones = db.Column(Text)
