"""Subida segura de imágenes (ADR-021).

- Formatos admitidos: JPEG, PNG y WEBP, hasta MAX_UPLOAD_BYTES.
- Se abre con Pillow (si no es una imagen real, se rechaza), se gira según la
  orientación EXIF y se reduce a MAX_SIDE píxeles por el lado mayor.
- Se vuelve a guardar como WEBP sin metadatos: se eliminan EXIF, GPS y demás datos ocultos.
- Las imágenes viven en MEDIA_ROOT (dentro de data/) con nombres aleatorios y nunca se
  sirven directamente: cada módulo las entrega con una vista que comprueba permisos.
"""

import io
import uuid
import warnings

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000  # protección frente a imágenes "bomba"
MAX_SIDE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO: JPEG de algunas cámaras


def process_upload(upload, max_side: int = MAX_SIDE, square: bool = False) -> ContentFile:
    """Valida y limpia una imagen subida. Devuelve un ContentFile WEBP listo para guardar."""
    if upload is None:
        raise ValidationError(_("Elige una imagen."))
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(_("La imagen es demasiado grande (máximo 10 MB)."))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(upload)
            if image.format not in ALLOWED_FORMATS:
                raise ValidationError(_("Formato no admitido. Usa JPG, PNG o WEBP."))
            if image.width * image.height > MAX_PIXELS:
                raise ValidationError(_("La imagen tiene demasiados píxeles."))
            image.load()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Warning) as error:
        raise ValidationError(_("El archivo no es una imagen válida.")) from error

    image = ImageOps.exif_transpose(image)  # aplica el giro antes de borrar el EXIF
    if square:
        side = min(image.size)
        image = ImageOps.fit(image, (side, side))
    image.thumbnail((max_side, max_side))
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    out = io.BytesIO()
    image.save(out, format="WEBP", quality=82, method=4)  # sin exif= → sin metadatos
    return ContentFile(out.getvalue(), name=f"{uuid.uuid4().hex}.webp")


def replace_image(instance, field_name: str, upload, **options) -> None:
    """Sustituye la imagen de un campo, borrando el archivo anterior."""
    new = process_upload(upload, **options)
    old = getattr(instance, field_name)
    old_name = old.name if old else None
    getattr(instance, field_name).save(new.name, new, save=False)
    instance.save(update_fields=[field_name])
    if old_name:
        old.storage.delete(old_name)


def remove_image(instance, field_name: str) -> None:
    field = getattr(instance, field_name)
    if field:
        field.delete(save=False)
        instance.save(update_fields=[field_name])


def serve(field) -> HttpResponse:
    """Entrega una imagen ya autorizada por la vista que llama.

    Se lee entera (ya está reducida a unos cientos de KB) para cerrar el archivo al
    momento: en Windows, un archivo abierto no se puede borrar ni sustituir.
    """
    if not field:
        raise Http404
    try:
        with field.storage.open(field.name, "rb") as handle:
            content = handle.read()
    except FileNotFoundError as error:
        raise Http404 from error
    response = HttpResponse(content, content_type="image/webp")
    response["Cache-Control"] = "private, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response
