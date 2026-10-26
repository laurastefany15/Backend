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


class Incapacidad(db.Model):
    __tablename__ = "incapacidades"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('ENFERMEDAD_GENERAL', 'ACCIDENTE_LABORAL', 'ENFERMEDAD_LABORAL', "
            "'MATERNIDAD', 'PATERNIDAD', 'OTRA')",
            name="ck_incapacidad_tipo",
        ),
        CheckConstraint(
            "estado IN ('REGISTRADA', 'VALIDADA', 'EN_COBRO', 'PAGADA', 'RECHAZADA')",
            name="ck_incapacidad_estado",
        ),
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_incapacidad_fechas"),
        Index("idx_incapacidades_contrato", "contrato_id", "fecha_inicio", "fecha_fin"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    tipo = db.Column(String(30), nullable=False)
    fecha_inicio = db.Column(Date, nullable=False)
    fecha_fin = db.Column(Date, nullable=False)
    entidad_responsable = db.Column(String(150))
    numero_certificado = db.Column(String(100))
    porcentaje_reconocimiento = db.Column(Numeric(8, 4))
    valor_estimado = db.Column(Numeric(15, 2))
    valor_reconocido = db.Column(Numeric(15, 2))
    estado = db.Column(String(20), nullable=False, server_default=text("'REGISTRADA'"))
    observaciones = db.Column(Text)
