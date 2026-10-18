from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)

from extensions import db


class Empleado(db.Model):
    __tablename__ = "empleados"
    __table_args__ = (
        CheckConstraint("estado IN ('ACTIVO', 'INACTIVO')", name="ck_empleado_estado"),
        UniqueConstraint("empresa_id", "tipo_documento", "numero_documento"),
    )

    id = db.Column(Integer, primary_key=True)
    empresa_id = db.Column(ForeignKey("empresas.id"), nullable=False)
    tipo_documento = db.Column(String(10), nullable=False)
    numero_documento = db.Column(String(30), nullable=False)
    nombres = db.Column(String(100), nullable=False)
    apellidos = db.Column(String(100), nullable=False)
    fecha_nacimiento = db.Column(Date)
    telefono = db.Column(String(30))
    correo = db.Column(String(150))
    direccion = db.Column(Text)
    contacto_emergencia = db.Column(String(150))
    telefono_emergencia = db.Column(String(30))
    banco = db.Column(String(120))
    tipo_cuenta = db.Column(String(25))
    numero_cuenta = db.Column(String(60))
    eps = db.Column(String(120))
    fondo_pension = db.Column(String(120))
    fondo_cesantias = db.Column(String(120))
    arl = db.Column(String(120))
    caja_compensacion = db.Column(String(120))
    estado = db.Column(String(15), nullable=False, server_default=text("'ACTIVO'"))
    creado_en = db.Column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
