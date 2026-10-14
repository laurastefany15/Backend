from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
    String,
    text,
)

from extensions import db


class ConceptoNomina(db.Model):
    __tablename__ = "conceptos_nomina"
    __table_args__ = (
        CheckConstraint("tipo IN ('DEVENGADO', 'DEDUCCION')", name="ck_concepto_tipo"),
    )

    id = db.Column(Integer, primary_key=True)
    codigo = db.Column(String(35), nullable=False, unique=True)
    nombre = db.Column(String(150), nullable=False)
    tipo = db.Column(String(12), nullable=False)
    constituye_salario = db.Column(Boolean, nullable=False, server_default=text("0"))
    integra_base_seguridad_social = db.Column(Boolean, nullable=False, server_default=text("0"))
    activo = db.Column(Boolean, nullable=False, server_default=text("1"))
