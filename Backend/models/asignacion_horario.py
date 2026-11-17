from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
)

from extensions import db


class AsignacionHorario(db.Model):
    __tablename__ = "asignaciones_horario"
    __table_args__ = (
        CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta >= vigente_desde",
            name="ck_asignacion_horario_vigencia",
        ),
    )

    id = db.Column(Integer, primary_key=True)
    contrato_id = db.Column(ForeignKey("contratos.id"), nullable=False)
    horario_id = db.Column(ForeignKey("horarios.id"), nullable=False)
    vigente_desde = db.Column(Date, nullable=False)
    vigente_hasta = db.Column(Date)
