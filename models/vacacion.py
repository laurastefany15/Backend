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


class Vacacion(db.Model):
    __tablename__ = "vacaciones"
    __table_args__ = (
        CheckConstraint("dias_habiles > 0", name="ck_vacaciones_dias"),
        CheckConstraint(
            "estado IN ('SOLICITADA', 'APROBADA', 'DISFRUTADA', 'CANCELADA')",
            name="ck_vacaciones_estado",
        ),
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_vacaciones_fechas"),
        Index("idx_vacaciones_contrato", "contrato_id", "fecha_inicio", "fecha_fin"),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    fecha_inicio = db.Column(Date, nullable=False)
    fecha_fin = db.Column(Date, nullable=False)
    fecha_reintegro = db.Column(Date)
    dias_habiles = db.Column(Numeric(8, 3), nullable=False)
    estado = db.Column(String(20), nullable=False, server_default=text("'SOLICITADA'"))
    aprobada_por = db.Column(ForeignKey("usuarios.id"))
    observaciones = db.Column(Text)
