from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)

from extensions import db


class DocumentoIncapacidad(db.Model):
    __tablename__ = "documentos_incapacidad"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('CERTIFICADO_EPS', 'HISTORIA_CLINICA', 'TRANSCRIPCION', 'OTRO')",
            name="ck_documento_incapacidad_tipo",
        ),
        CheckConstraint("tamano_bytes > 0", name="ck_documento_incapacidad_tamano"),
        Index("idx_documentos_incapacidad", "incapacidad_id"),
    )

    id = db.Column(Integer, primary_key=True)
    incapacidad_id = db.Column(ForeignKey("incapacidades.id"), nullable=False)
    tipo = db.Column(String(30), nullable=False, server_default=text("'OTRO'"))
    nombre_original = db.Column(String(255), nullable=False)
    nombre_archivo = db.Column(String(80), nullable=False, unique=True)
    content_type = db.Column(String(100), nullable=False)
    tamano_bytes = db.Column(Integer, nullable=False)
    subido_por = db.Column(ForeignKey("usuarios.id"))
    creado_en = db.Column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
