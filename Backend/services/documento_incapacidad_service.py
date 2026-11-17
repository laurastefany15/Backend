import os
import uuid

from flask import current_app
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import DocumentoIncapacidad
from services.incapacidad_service import (
    IncapacidadNotFoundError,
    IncapacidadValidationError,
    _empresa_id_for_user,
    _find_incapacidad,
)


TIPOS_DOCUMENTO = {"CERTIFICADO_EPS", "HISTORIA_CLINICA", "TRANSCRIPCION", "OTRO"}
FORMATOS = {
    "pdf": ("application/pdf", (b"%PDF-",)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}
DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def _upload_root():
    return current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.instance_path, "uploads"
    )


def _incapacidad_dir(incapacidad_id):
    return os.path.join(_upload_root(), "incapacidades", str(incapacidad_id))


def _document_path(documento):
    return os.path.join(_incapacidad_dir(documento.incapacidad_id), documento.nombre_archivo)


def _max_bytes():
    return current_app.config.get("MAX_DOCUMENT_BYTES", DEFAULT_MAX_BYTES)


def parse_tipo_documento(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return "OTRO"
    if not isinstance(value, str) or value.strip() not in TIPOS_DOCUMENTO:
        options = ", ".join(sorted(TIPOS_DOCUMENTO))
        raise IncapacidadValidationError(f"tipo de documento debe ser uno de: {options}.")
    return value.strip()


def _read_upload(upload):
    original = os.path.basename((upload.filename or "").replace("\\", "/")).strip()
    if not original:
        raise IncapacidadValidationError("Cada archivo debe tener un nombre.")
    if len(original) > 255:
        raise IncapacidadValidationError("El nombre del archivo no puede superar 255 caracteres.")

    extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if extension not in FORMATOS:
        raise IncapacidadValidationError(
            f"{original}: solo se admiten archivos PDF, PNG o JPG."
        )

    limit = _max_bytes()
    content = upload.stream.read(limit + 1)
    if not content:
        raise IncapacidadValidationError(f"{original}: el archivo está vacío.")
    if len(content) > limit:
        raise IncapacidadValidationError(
            f"{original}: el archivo supera el máximo de {limit // (1024 * 1024)} MB."
        )

    content_type, signatures = FORMATOS[extension]
    if not any(content.startswith(signature) for signature in signatures):
        raise IncapacidadValidationError(
            f"{original}: el contenido no corresponde a un archivo {extension.upper()}."
        )
    return original, extension, content_type, content


def stage_documents(incapacidad_id, uploads, tipo, current_user):
    """Valida y escribe los archivos; devuelve (documentos, rutas) sin confirmar la sesión."""
    if not uploads:
        raise IncapacidadValidationError("Debe adjuntar al menos un archivo.")

    prepared = [_read_upload(upload) for upload in uploads]
    directory = _incapacidad_dir(incapacidad_id)
    os.makedirs(directory, exist_ok=True)

    documentos = []
    paths = []
    try:
        for original, extension, content_type, content in prepared:
            stored_name = f"{uuid.uuid4().hex}.{extension}"
            path = os.path.join(directory, stored_name)
            with open(path, "xb") as file:
                file.write(content)
            paths.append(path)
            documento = DocumentoIncapacidad(
                incapacidad_id=incapacidad_id,
                tipo=tipo,
                nombre_original=original,
                nombre_archivo=stored_name,
                content_type=content_type,
                tamano_bytes=len(content),
                subido_por=current_user.id,
            )
            db.session.add(documento)
            documentos.append(documento)
    except Exception:
        discard_files(paths)
        raise
    return documentos, paths


def discard_files(paths):
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def serialize_documento(documento):
    return {
        "id": documento.id,
        "incapacidad_id": documento.incapacidad_id,
        "tipo": documento.tipo,
        "nombre_original": documento.nombre_original,
        "content_type": documento.content_type,
        "tamano_bytes": documento.tamano_bytes,
        "subido_por": documento.subido_por,
        "creado_en": documento.creado_en.isoformat() if documento.creado_en else None,
        "descarga": (
            f"/incapacidades/{documento.incapacidad_id}/documentos/{documento.id}/archivo"
        ),
    }


def documents_for(incapacidad_id):
    return (
        DocumentoIncapacidad.query.filter_by(incapacidad_id=incapacidad_id)
        .order_by(DocumentoIncapacidad.id)
        .all()
    )


def _find_documento(empresa_id, incapacidad_id, documento_id):
    _find_incapacidad(empresa_id, incapacidad_id)
    documento = DocumentoIncapacidad.query.filter_by(
        id=documento_id,
        incapacidad_id=incapacidad_id,
    ).first()
    if documento is None:
        raise IncapacidadNotFoundError("Documento no encontrado.")
    return documento


def list_documents(current_user, incapacidad_id):
    empresa_id = _empresa_id_for_user(current_user)
    _find_incapacidad(empresa_id, incapacidad_id)
    return [serialize_documento(documento) for documento in documents_for(incapacidad_id)]


def upload_documents(current_user, incapacidad_id, uploads, tipo=None):
    empresa_id = _empresa_id_for_user(current_user)
    _find_incapacidad(empresa_id, incapacidad_id)
    documentos, paths = stage_documents(
        incapacidad_id,
        uploads,
        parse_tipo_documento(tipo),
        current_user,
    )
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        discard_files(paths)
        raise IncapacidadValidationError("No se pudieron registrar los documentos.") from error
    return [serialize_documento(documento) for documento in documentos]


def get_document(current_user, incapacidad_id, documento_id):
    empresa_id = _empresa_id_for_user(current_user)
    return serialize_documento(_find_documento(empresa_id, incapacidad_id, documento_id))


def document_file(current_user, incapacidad_id, documento_id):
    empresa_id = _empresa_id_for_user(current_user)
    documento = _find_documento(empresa_id, incapacidad_id, documento_id)
    path = _document_path(documento)
    if not os.path.isfile(path):
        raise IncapacidadNotFoundError("El archivo del documento no está en el servidor.")
    return path, documento


def delete_document(current_user, incapacidad_id, documento_id):
    empresa_id = _empresa_id_for_user(current_user)
    documento = _find_documento(empresa_id, incapacidad_id, documento_id)
    payload = serialize_documento(documento)
    path = _document_path(documento)
    db.session.delete(documento)
    db.session.commit()
    discard_files([path])
    return payload
