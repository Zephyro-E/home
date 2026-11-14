"""Copias de seguridad y restauración (ver docs/arquitectura.md).

Cada copia es una carpeta data/backups/AAAAMMDD-HHMMSS/ con:
- hogar.sqlite3: copia en caliente de la base de datos (API de backup de SQLite).
- media.zip: imágenes y archivos subidos (si hay).
"""

import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection

DB_FILENAME = "hogar.sqlite3"
MEDIA_FILENAME = "media.zip"


def backups_dir() -> Path:
    path = Path(settings.DATA_DIR) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def keep_count() -> int:
    return int(os.environ.get("HOGAR_BACKUP_KEEP", "30"))


def _ensure_no_transaction() -> None:
    # Con una transacción abierta, SQLite se quedaría esperando indefinidamente.
    if connection.in_atomic_block:
        raise RuntimeError("Las copias no pueden hacerse dentro de una transacción.")


def _copy_database_to(dest: Path) -> None:
    _ensure_no_transaction()
    connection.ensure_connection()
    target = sqlite3.connect(dest)
    try:
        connection.connection.backup(target)
    finally:
        target.close()


def _zip_media(dest: Path) -> bool:
    media = Path(settings.MEDIA_ROOT)
    files = [p for p in media.rglob("*") if p.is_file()] if media.exists() else []
    if not files:
        return False
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(media).as_posix())
    return True


def list_backups() -> list[Path]:
    return sorted(
        (p for p in backups_dir().iterdir() if p.is_dir() and (p / DB_FILENAME).exists()),
        reverse=True,
    )


def rotate(keep: int | None = None) -> list[Path]:
    """Borra las copias más antiguas, conservando las `keep` más recientes."""
    keep = keep_count() if keep is None else keep
    removed = list_backups()[keep:]
    for path in removed:
        shutil.rmtree(path)
    return removed


def create_backup(label: str = "") -> Path:
    name = datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{label}" if label else "")
    folder = backups_dir() / name
    suffix = 1
    while folder.exists():
        suffix += 1
        folder = backups_dir() / f"{name}-{suffix}"
    folder.mkdir()
    _copy_database_to(folder / DB_FILENAME)
    _zip_media(folder / MEDIA_FILENAME)
    rotate()
    return folder


def check_database_file(path: Path) -> None:
    """Comprueba que el archivo es una base de datos SQLite íntegra de Hogar."""
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        ok = db.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        db.close()
    if ok != "ok":
        raise ValueError(f"La copia está dañada: {ok}")
    if "core_user" not in tables:
        raise ValueError("El archivo no parece una copia de Hogar.")


def restore_backup(folder: Path) -> Path:
    """Restaura una copia. Antes guarda una copia de seguridad del estado actual.

    Devuelve la carpeta de esa copia previa (por si hay que deshacer la restauración).
    La aplicación debe estar parada mientras se restaura.
    """
    db_file = folder / DB_FILENAME
    if not db_file.exists():
        raise FileNotFoundError(f"No existe {db_file}")
    check_database_file(db_file)

    _ensure_no_transaction()
    safety = create_backup(label="antes-de-restaurar")

    connection.ensure_connection()
    source = sqlite3.connect(db_file)
    try:
        source.backup(connection.connection)
    finally:
        source.close()

    media_zip = folder / MEDIA_FILENAME
    media = Path(settings.MEDIA_ROOT)
    if media.exists():
        shutil.rmtree(media)
    if media_zip.exists():
        media.mkdir(parents=True)
        with zipfile.ZipFile(media_zip) as zf:
            for member in zf.namelist():
                target = (media / member).resolve()
                if not target.is_relative_to(media.resolve()):
                    raise ValueError(f"Ruta no permitida en la copia: {member}")
            zf.extractall(media)
    return safety
