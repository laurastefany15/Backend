from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)

from extensions import db


class Asistencia(db.Model):
    __tablename__ = "asistencias"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('REGISTRADA', 'VALIDADA', 'ANULADA')", name="ck_asistencia_estado"
        ),
        CheckConstraint("salida IS NULL OR salida > entrada", name="ck_asistencia_salida"),
        CheckConstraint("minutos_descanso >= 0", name="ck_asistencia_descanso"),
        Index("idx_asistencia_contrato", "contrato_id", "entrada"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    entrada = db.Column(DateTime(timezone=True), nullable=False)
    salida = db.Column(DateTime(timezone=True))
    minutos_descanso = db.Column(Integer, nullable=False, server_default=text("0"))
    estado = db.Column(String(15), nullable=False, server_default=text("'REGISTRADA'"))
    observacion = db.Column(Text)
