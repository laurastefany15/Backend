from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)

from extensions import db


class Contrato(db.Model):
    __tablename__ = "contratos"
    __table_args__ = (
        CheckConstraint(
            "tipo_contrato IN ('INDEFINIDO', 'FIJO', 'OBRA_LABOR', 'APRENDIZAJE', 'OTRO')",
            name="ck_contrato_tipo",
        ),
        CheckConstraint("salario_mensual >= 0", name="ck_contrato_salario"),
        CheckConstraint("horas_semanales > 0", name="ck_contrato_horas"),
        CheckConstraint("dia_descanso BETWEEN 1 AND 7", name="ck_contrato_dia_descanso"),
        CheckConstraint("estado IN ('ACTIVO', 'TERMINADO')", name="ck_contrato_estado"),
        CheckConstraint(
            "fecha_fin IS NULL OR fecha_fin >= fecha_inicio", name="ck_contrato_fechas"
        ),
        Index("idx_contratos_empleado", "empleado_id"),
    )

    id = db.Column(Integer, primary_key=True)
    empleado_id = db.Column(ForeignKey("empleados.id"), nullable=False)
    tipo_contrato = db.Column(String(30), nullable=False)
    cargo = db.Column(String(140), nullable=False)
    fecha_inicio = db.Column(Date, nullable=False)
    fecha_fin = db.Column(Date)
    salario_mensual = db.Column(Numeric(15, 2), nullable=False)
    horas_semanales = db.Column(Numeric(6, 2), nullable=False)
    dia_descanso = db.Column(Integer, nullable=False, server_default=text("7"))
    tiene_auxilio_transporte = db.Column(Boolean, nullable=False, server_default=text("1"))
    estado = db.Column(String(15), nullable=False, server_default=text("'ACTIVO'"))
