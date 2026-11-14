import sqlite3
import zipfile
from io import StringIO

import pytest
from django.core.management import call_command

from apps.core import backup
from apps.core.models import User


@pytest.fixture(autouse=True)
def data_dir(tmp_path, settings):
    settings.DATA_DIR = tmp_path / "data"
    settings.MEDIA_ROOT = tmp_path / "data" / "media"
    return settings.DATA_DIR


def users_in(db_file):
    db = sqlite3.connect(db_file)
    try:
        return {row[0] for row in db.execute("SELECT email FROM core_user")}
    finally:
        db.close()


# Las copias se hacen fuera de transacciones (como en la realidad): transaction=True.
@pytest.mark.django_db(transaction=True)
def test_copia_contiene_la_base_de_datos_y_los_archivos(make_user, settings):
    make_user(email="ana@casa.test")
    (settings.MEDIA_ROOT / "avatars").mkdir(parents=True)
    (settings.MEDIA_ROOT / "avatars" / "ana.txt").write_text("hola")

    folder = backup.create_backup()

    assert users_in(folder / backup.DB_FILENAME) == {"ana@casa.test"}
    with zipfile.ZipFile(folder / backup.MEDIA_FILENAME) as zf:
        assert zf.namelist() == ["avatars/ana.txt"]
    backup.check_database_file(folder / backup.DB_FILENAME)


@pytest.mark.django_db(transaction=True)
def test_rotacion_conserva_las_mas_recientes(make_user):
    make_user()
    for _ in range(4):
        backup.create_backup()
    assert len(backup.list_backups()) == 4
    backup.rotate(keep=2)
    assert len(backup.list_backups()) == 2


@pytest.mark.django_db(transaction=True)
def test_restaurar_recupera_los_datos(make_user, settings):
    make_user(email="ana@casa.test")
    folder = backup.create_backup()

    make_user(email="luis@casa.test")  # cambio posterior a la copia
    settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    (settings.MEDIA_ROOT / "nuevo.txt").write_text("x")

    call_command("restore", folder.name, "--yes", stdout=StringIO())

    assert set(User.objects.values_list("email", flat=True)) == {"ana@casa.test"}
    assert not (settings.MEDIA_ROOT / "nuevo.txt").exists()
    # Se guardó el estado anterior por si hay que deshacer.
    safety = [p for p in backup.list_backups() if "antes-de-restaurar" in p.name]
    assert len(safety) == 1
    assert users_in(safety[0] / backup.DB_FILENAME) == {"ana@casa.test", "luis@casa.test"}


def test_rechaza_archivos_que_no_son_copias(tmp_path):
    bad = tmp_path / "hogar.sqlite3"
    sqlite3.connect(bad).execute("CREATE TABLE otra (id int)").connection.close()
    with pytest.raises(ValueError):
        backup.check_database_file(bad)


@pytest.mark.django_db
def test_dentro_de_una_transaccion_falla_en_vez_de_bloquearse():
    with pytest.raises(RuntimeError):
        backup.create_backup()
