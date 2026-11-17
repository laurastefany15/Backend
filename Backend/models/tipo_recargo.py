from sqlalchemy import (
    Boolean,
    CheckConstraint,
    String,
    Text,
    text,
)

from extensions import db


class TipoRecargo(db.Model):
    __tablename__ = "tipos_recargo"
    __table_args__ = (
        CheckConstraint("modo_pago IN ('ADICIONAL', 'COMPLETO')", name="ck_tipo_recargo_modo"),
    )

    codigo = db.Column(String(20), primary_key=True)
    nombre = db.Column(String(120), nullable=False)
    descripcion = db.Column(Text)
    modo_pago = db.Column(String(12), nullable=False)
    activo = db.Column(Boolean, nullable=False, server_default=text("1"))
