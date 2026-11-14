from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core import backup


class Command(BaseCommand):
    help = (
        "Restaura una copia de data/backups/. Para la aplicación antes de usarlo. "
        "Se guarda automáticamente una copia del estado actual por si hay que deshacerlo."
    )

    def add_arguments(self, parser):
        parser.add_argument("name", help="Nombre de la carpeta de la copia (ver: backup --list).")
        parser.add_argument("--yes", action="store_true", help="No pedir confirmación.")

    def handle(self, *args, name, yes=False, **options):
        folder = Path(name)
        if not folder.is_absolute():
            folder = backup.backups_dir() / name
        if not folder.is_dir():
            raise CommandError(f"No existe la copia {folder}")
        if not yes:
            answer = input(
                f"Se reemplazarán TODOS los datos actuales por la copia «{folder.name}». "
                "¿Continuar? [s/N] "
            )
            if answer.strip().lower() not in {"s", "si", "sí", "y", "yes"}:
                self.stdout.write("Cancelado.")
                return
        try:
            safety = backup.restore_backup(folder)
        except (ValueError, FileNotFoundError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Restaurada la copia {folder.name}."))
        self.stdout.write(f"El estado anterior se guardó en {safety.name}.")
