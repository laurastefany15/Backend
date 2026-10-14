from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Time,
    text,
)

from extensions import db


class Horario(db.Model):
    __tablename__ = "horarios"
    __table_args__ = (CheckConstraint("minutos_descanso >= 0", name="ck_horario_descanso"),)

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"), nullable=False)
    nombre = db.Column(String(120), nullable=False)
    hora_entrada = db.Column(Time, nullable=False)
    hora_salida = db.Column(Time, nullable=False)
    minutos_descanso = db.Column(Integer, nullable=False, server_default=text("0"))
