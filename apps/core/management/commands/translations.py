"""Gestión de traducciones sin GNU gettext (ADR-009), usando Babel (Python puro).

    uv run python manage.py translations update    # extrae textos nuevos al .po
    uv run python manage.py translations compile   # genera el .mo que usa Django
    uv run python manage.py translations check     # falla si falta alguna traducción

Los textos se escriben en español en el código; locale/<idioma>/LC_MESSAGES/django.po
contiene su traducción. Se reconocen:
- Python: _("..."), gettext("..."), gettext_lazy("...")
- Plantillas: {% translate "..." %}, _("...") en argumentos y {% blocktranslate %}…
"""

import io
import re
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.extract import extract_python
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po, write_po
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

TARGET_LANGUAGES = [code for code, _name in settings.LANGUAGES if code != settings.LANGUAGE_CODE]
PY_KEYWORDS = {"_": None, "gettext": None, "gettext_lazy": None}

TRANSLATE_TAG = re.compile(r"""\{%\s*(?:translate|trans)\s+(["'])(?P<msg>.*?)\1""")
UNDERSCORE_ARG = re.compile(r"""\b_\((["'])(?P<msg>.*?)\1\)""")
BLOCK_TAG = re.compile(
    r"\{%\s*blocktrans(?:late)?(?P<opts>[^%]*)%\}(?P<body>.*?)\{%\s*endblocktrans(?:late)?\s*%\}",
    re.DOTALL,
)
BLOCK_VAR = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
TRIM = re.compile(r"\s*\n\s*")


def _block_msgid(opts: str, body: str) -> str:
    """Reproduce cómo construye Django el msgid de {% blocktranslate %}."""
    parts, pos = [], 0
    for match in BLOCK_VAR.finditer(body):
        parts.append(body[pos : match.start()].replace("%", "%%"))
        parts.append(f"%({match.group(1)})s")
        pos = match.end()
    parts.append(body[pos:].replace("%", "%%"))
    msg = "".join(parts)
    if "trimmed" in opts.split():
        msg = TRIM.sub(" ", msg.strip())
    return msg


def source_files():
    base = Path(settings.BASE_DIR)
    skip = {".venv", "node_modules", "staticfiles", ".git"}
    for path in sorted(base.rglob("*")):
        if any(part in skip for part in path.parts) or {"tests", "migrations"} & set(path.parts):
            continue
        if path.suffix in {".py", ".html", ".txt"} and path.is_file():
            yield base, path


def extract_messages() -> dict[str, set[str]]:
    """Devuelve {msgid: {ubicaciones}}."""
    found: dict[str, set[str]] = {}

    def add(msg, where):
        if msg:
            found.setdefault(msg, set()).add(where)

    for base, path in source_files():
        rel = path.relative_to(base).as_posix()
        if path.suffix == ".py":
            with path.open("rb") as fh:
                for lineno, _func, message, _comments in extract_python(fh, PY_KEYWORDS, [], {}):
                    if isinstance(message, str):
                        add(message, f"{rel}:{lineno}")
        else:
            text = path.read_text(encoding="utf-8")
            for regex in (TRANSLATE_TAG, UNDERSCORE_ARG):
                for match in regex.finditer(text):
                    add(match.group("msg"), f"{rel}:{text.count(chr(10), 0, match.start()) + 1}")
            for match in BLOCK_TAG.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                add(_block_msgid(match.group("opts"), match.group("body")), f"{rel}:{line}")
    return found


def po_path(lang: str) -> Path:
    return Path(settings.BASE_DIR) / "locale" / lang / "LC_MESSAGES" / "django.po"


def load_catalog(lang: str) -> Catalog:
    path = po_path(lang)
    if path.exists():
        with path.open("rb") as fh:
            return read_po(fh, locale=lang)
    return Catalog(locale=lang, project="Hogar", charset="utf-8")


class Command(BaseCommand):
    help = "Extrae, compila y comprueba las traducciones (sin GNU gettext)."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["update", "compile", "check"])

    def handle(self, *args, action, **options):
        getattr(self, f"do_{action}")()

    def do_update(self):
        messages = extract_messages()
        for lang in TARGET_LANGUAGES:
            old = load_catalog(lang)
            new = Catalog(locale=lang, project="Hogar", charset="utf-8")
            for msgid in sorted(messages):
                previous = old.get(msgid)
                locations = [tuple(loc.rsplit(":", 1)) for loc in sorted(messages[msgid])]
                new.add(
                    msgid,
                    previous.string if previous else "",
                    locations=[(f, int(n)) for f, n in locations],
                )
            path = po_path(lang)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wb") as fh:
                write_po(fh, new, width=100, sort_output=True)
            missing = sum(1 for m in new if m.id and not m.string)
            self.stdout.write(f"{lang}: {len(messages)} textos, {missing} sin traducir")

    def do_compile(self):
        for lang in TARGET_LANGUAGES:
            catalog = load_catalog(lang)
            with po_path(lang).with_suffix(".mo").open("wb") as fh:
                write_mo(fh, catalog)
            self.stdout.write(f"{lang}: compilado")

    def do_check(self):
        messages = extract_messages()
        problems = []
        for lang in TARGET_LANGUAGES:
            catalog = load_catalog(lang)
            for msgid in messages:
                entry = catalog.get(msgid)
                if entry is None or not entry.string:
                    problems.append(f"[{lang}] sin traducir: {msgid!r}")
            mo = po_path(lang).with_suffix(".mo")
            buffer = io.BytesIO()
            write_mo(buffer, catalog)
            if not mo.exists() or mo.read_bytes() != buffer.getvalue():
                problems.append(f"[{lang}] falta compilar: manage.py translations compile")
        if problems:
            raise CommandError("\n".join(problems))
        self.stdout.write("Traducciones completas.")
