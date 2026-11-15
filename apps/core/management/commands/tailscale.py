"""Acceso desde fuera de casa con Tailscale (ADR-022).

    uv run python manage.py tailscale configurar   # ajusta .env y activa HTTPS
    uv run python manage.py tailscale estado       # muestra la dirección y si está activo
    uv run python manage.py tailscale quitar       # deja de publicar la app en Tailscale

Tailscale ("tailscale serve") recibe las conexiones HTTPS de la red privada y las pasa a
la app en http://127.0.0.1:8000. La app solo necesita saber su dirección pública dentro de
la red (para la protección CSRF) y que debe marcar las cookies como seguras.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PORT = 8000
WINDOWS_PATHS = [
    Path(r"C:\Program Files\Tailscale\tailscale.exe"),
    Path(r"C:\Program Files (x86)\Tailscale\tailscale.exe"),
]


def find_tailscale() -> str:
    found = shutil.which("tailscale")
    if found:
        return found
    for path in WINDOWS_PATHS:
        if path.exists():
            return str(path)
    raise CommandError(
        "No encuentro Tailscale. Instálalo desde https://tailscale.com/download "
        "y entra con tu cuenta antes de ejecutar este script."
    )


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)


def machine_name(tailscale: str) -> str:
    """Nombre completo del PC en la red privada, p. ej. "mi-pc.tail1234.ts.net"."""
    result = run([tailscale, "status", "--json"])
    if result.returncode != 0:
        raise CommandError(
            "Tailscale no responde. Ábrelo y comprueba que has iniciado sesión.\n"
            + (result.stderr or result.stdout).strip()
        )
    try:
        status = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CommandError("No he podido leer el estado de Tailscale.") from error
    if status.get("BackendState") != "Running":
        raise CommandError(
            "Tailscale no está conectado. Ábrelo, inicia sesión y vuelve a intentarlo."
        )
    name = (status.get("Self") or {}).get("DNSName", "").rstrip(".")
    if not name:
        raise CommandError(
            "Tailscale no da un nombre para este PC. Activa MagicDNS en la consola de "
            "Tailscale (https://login.tailscale.com/admin/dns)."
        )
    return name


def update_env(path: Path, values: dict[str, str]) -> None:
    """Escribe o sustituye variables en el archivo .env sin tocar el resto."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    out = []
    for line in lines:
        match = re.match(r"\s*([A-Z0-9_]+)\s*=", line)
        if match and match.group(1) in pending:
            key = match.group(1)
            out.append(f"{key}={pending.pop(key)}")
        else:
            out.append(line)
    if pending:
        if out and out[-1].strip():
            out.append("")
        out.append("# Acceso desde fuera de casa con Tailscale (manage.py tailscale configurar)")
        out.extend(f"{key}={value}" for key, value in pending.items())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


class Command(BaseCommand):
    help = "Configura el acceso desde fuera de casa con Tailscale."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["configurar", "estado", "quitar"])
        parser.add_argument(
            "--env-file", default=None, help="Ruta del archivo .env (por defecto, el del proyecto)."
        )

    def handle(self, *args, accion, env_file=None, **options):
        tailscale = find_tailscale()
        env_path = Path(env_file) if env_file else Path(settings.BASE_DIR) / ".env"

        if accion == "quitar":
            result = run([tailscale, "serve", "reset"])
            if result.returncode != 0:
                raise CommandError((result.stderr or result.stdout).strip())
            self.stdout.write("La app ya no se publica en Tailscale.")
            return

        name = machine_name(tailscale)
        url = f"https://{name}"

        if accion == "estado":
            result = run([tailscale, "serve", "status"])
            self.stdout.write(f"Dirección de la app en tu red Tailscale: {url}")
            self.stdout.write((result.stdout or result.stderr).strip() or "(sin publicar)")
            return

        update_env(env_path, {"HOGAR_CSRF_TRUSTED_ORIGINS": url, "HOGAR_HTTPS": "1"})
        result = run([tailscale, "serve", "--bg", f"http://127.0.0.1:{PORT}"])
        if result.returncode != 0:
            text = (result.stderr or result.stdout).strip()
            raise CommandError(
                "Tailscale no ha podido activar HTTPS. Si el mensaje pide activar los "
                "certificados HTTPS, hazlo en https://login.tailscale.com/admin/dns "
                f"y vuelve a ejecutar este script.\n\n{text}"
            )
        self.stdout.write(self.style.SUCCESS("¡Listo! La app estará disponible en:"))
        self.stdout.write(f"\n    {url}\n")
        self.stdout.write(
            "Ábrela desde cualquier dispositivo conectado a tu red Tailscale.\n"
            "Recuerda reiniciar scripts\\servir.bat para que aplique los cambios."
        )
