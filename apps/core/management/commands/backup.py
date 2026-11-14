from django.core.management.base import BaseCommand

from apps.core import backup


class Command(BaseCommand):
    help = "Crea una copia de seguridad en data/backups/ (base de datos + archivos subidos)."

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", help="Muestra las copias existentes.")

    def handle(self, *args, list=False, **options):
        if list:
            for path in backup.list_backups():
                self.stdout.write(path.name)
            return
        folder = backup.create_backup()
        self.stdout.write(self.style.SUCCESS(f"Copia creada: {folder}"))
