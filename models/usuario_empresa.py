from sqlalchemy import ForeignKey, PrimaryKeyConstraint

from extensions import db


class UsuarioEmpresa(db.Model):
    __tablename__ = "usuarios_empresas"
    __table_args__ = (PrimaryKeyConstraint("usuario_id", "empresa_id"),)

    usuario_id = db.Column(ForeignKey("usuarios.id"), nullable=False)
    empresa_id = db.Column(ForeignKey("empresas.id"), nullable=False)
