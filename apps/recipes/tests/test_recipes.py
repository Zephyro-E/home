"""Recetas, ingredientes, imágenes y foto de perfil."""

import io
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.core import images
from apps.core.models import Visibility
from apps.recipes import ingredients as ing
from apps.recipes import services
from apps.recipes.models import Recipe, RecipeComment, RecipeRating
from apps.shopping.models import GroceryItem

pytestmark = pytest.mark.django_db
UNDO = {"HTTP_X_UNDO_COMMIT": "1"}


@pytest.fixture(autouse=True)
def _media(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"


def image_file(fmt="JPEG", size=(2400, 1200), name="foto.jpg", exif_gps=False):
    buf = io.BytesIO()
    img = Image.new("RGB", size, (200, 120, 40))
    kwargs = {}
    if exif_gps:
        exif = Image.Exif()
        exif[0x010F] = "MarcaFalsa"  # Make
        exif[0x8825] = {1: "N", 2: (40.0, 25.0, 0.0)}  # GPSInfo
        kwargs["exif"] = exif.tobytes()
    img.save(buf, format=fmt, **kwargs)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


@pytest.fixture
def data(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    return {
        "household": household,
        "ana": ana,
        "luis": luis,
        "eva": eva,
        "tortilla": services.create_recipe(
            household,
            ana,
            title="Tortilla de patatas",
            servings=4,
            tags="clásica, huevos",
            ingredients_text="4 huevos\n500 g de patatas\n1/2 cebolla\nsal",
            instructions="Pelar y cortar.\n\nFreír.\nCuajar.",
        ),
        "private": services.create_recipe(
            household, ana, title="Salsa secreta", visibility="private"
        ),
        "foreign": services.create_recipe(other, eva, title="Receta ajena"),
    }


# --- Ingredientes -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("200 g de harina", (Decimal("200"), "g", "harina")),
        ("2 huevos", (Decimal("2"), "", "huevos")),
        ("1/2 cebolla", (Decimal("0.500"), "", "cebolla")),
        ("1 1/2 tazas de leche", (Decimal("1.500"), "tazas", "leche")),
        ("½ limón", (Decimal("0.500"), "", "limón")),
        ("1,5 kg patatas", (Decimal("1.5"), "kg", "patatas")),
        ("- sal", (None, "", "sal")),
        ("3 dientes de ajo", (Decimal("3"), "dientes", "ajo")),
        ("2 g", (Decimal("2"), "", "g")),
    ],
)
def test_leer_ingredientes(line, expected):
    item = ing.parse_line(line)
    assert (item["quantity"], item["unit"], item["name"]) == expected


def test_lineas_vacias_y_formato():
    assert ing.parse_text("\n  \n2 huevos\n") == [
        {"quantity": Decimal("2"), "unit": "", "name": "huevos"}
    ]
    assert ing.format_quantity(Decimal("1.500")) == "1,5"
    assert ing.format_quantity(Decimal("2.000")) == "2"
    assert ing.to_line(Decimal("0.5"), "kg", "patatas") == "0,5 kg patatas"
    assert ing.to_line(None, "", "sal") == "sal"


def test_receta_y_raciones(data):
    r = data["tortilla"]
    assert [i.name for i in r.ingredients.all()] == ["huevos", "patatas", "cebolla", "sal"]
    assert r.steps == ["Pelar y cortar.", "Freír.", "Cuajar."]
    assert r.tag_list == ["clásica", "huevos"]
    lines = [line for _i, _q, line in services.scaled_ingredients(r, 2)]
    assert lines == ["2 huevos", "250 g patatas", "0,25 cebolla", "sal"]
    assert services.ingredients_text(r) == "4 huevos\n500 g patatas\n0,5 cebolla\nsal"


def test_raciones_validas(data):
    with pytest.raises(ValidationError):
        services.create_recipe(data["household"], data["ana"], title="X", servings=0)
    with pytest.raises(ValidationError):
        services.create_recipe(data["household"], data["ana"], title="  ")


def test_etiquetas_limpias(data):
    r = services.create_recipe(
        data["household"], data["ana"], title="X", tags=" rápida ,, rápida, horno "
    )
    assert r.tags == "rápida, horno"


def test_ingredientes_a_la_lista_de_la_compra(data):
    r = data["tortilla"]
    services.add_to_grocery(
        r, data["luis"], data["household"], 6, [i.pk for i in r.ingredients.all()][:3]
    )
    items = {g.name: g.quantity for g in GroceryItem.objects.all()}
    assert items == {"huevos": "6", "patatas": "750 g", "cebolla": "0,75"}
    # Volver a añadir no duplica: actualiza la cantidad.
    services.add_to_grocery(r, data["luis"], data["household"], 4, [r.ingredients.first().pk])
    assert GroceryItem.objects.get(name="huevos").quantity == "4"


def test_permisos(data):
    luis = data["luis"]
    with pytest.raises(PermissionDenied):
        services.update_recipe(data["private"], luis, title="x", servings=1)
    with pytest.raises(PermissionDenied):
        services.delete_recipe(data["tortilla"], luis, luis.memberships.get())
    with pytest.raises(PermissionDenied):
        services.make_shared(data["private"], luis)
    assert data["private"] not in services.recipes_for(luis, data["household"])


def test_busqueda_por_ingrediente(data):
    found = services.listing(data["luis"], data["household"], query="patata")
    assert [r.title for r in found] == ["Tortilla de patatas"]
    assert services.all_tags(data["luis"], data["household"]) == ["clásica", "huevos"]


# --- Imágenes -----------------------------------------------------------------------------


def test_imagen_se_reduce_y_pierde_el_exif():
    out = images.process_upload(image_file(exif_gps=True))
    img = Image.open(io.BytesIO(out.read()))
    assert img.format == "WEBP"
    assert max(img.size) == images.MAX_SIDE
    assert not img.getexif()
    assert "exif" not in img.info


def test_imagen_cuadrada_para_avatar():
    out = images.process_upload(image_file(size=(900, 600)), max_side=400, square=True)
    assert Image.open(io.BytesIO(out.read())).size == (400, 400)


@pytest.mark.parametrize(
    "upload",
    [
        SimpleUploadedFile("x.jpg", b"esto no es una imagen", content_type="image/jpeg"),
        SimpleUploadedFile("x.gif", b"GIF89a" + b"\x00" * 50, content_type="image/gif"),
    ],
)
def test_imagenes_invalidas(upload):
    with pytest.raises(ValidationError):
        images.process_upload(upload)


def test_gif_real_rechazado():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="GIF")
    with pytest.raises(ValidationError):
        images.process_upload(SimpleUploadedFile("x.gif", buf.getvalue()))


def test_imagen_demasiado_grande(monkeypatch):
    monkeypatch.setattr(images, "MAX_UPLOAD_BYTES", 100)
    with pytest.raises(ValidationError):
        images.process_upload(image_file())


def test_foto_de_receta_se_sustituye_y_se_borra(data):
    r = data["tortilla"]
    services.update_recipe(r, data["ana"], title=r.title, servings=4, image=image_file())
    first = r.image.name
    assert first.startswith(f"recipes/{data['household'].pk}/") and first.endswith(".webp")
    storage = r.image.storage
    services.update_recipe(
        r, data["ana"], title=r.title, servings=4, image=image_file(fmt="PNG", name="b.png")
    )
    assert not storage.exists(first) and storage.exists(r.image.name)
    second = r.image.name
    services.delete_recipe(r, data["ana"], data["ana"].memberships.get())
    assert not storage.exists(second)


# --- Vistas -------------------------------------------------------------------------------

PAGES = ["recipes:list", "recipes:create"]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    assert reverse("core:login") in client.get(reverse(name)).url


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


def test_listado_solo_lo_visible(login_as, data):
    html = login_as(data["luis"]).get(reverse("recipes:list")).content.decode()
    assert (
        "Tortilla de patatas" in html and "Salsa secreta" not in html and "Receta ajena" not in html
    )


@pytest.mark.parametrize("name", ["recipes:detail", "recipes:edit", "recipes:image"])
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_ajeno_da_404_al_verlo(login_as, data, name, who, target):
    assert login_as(data[who]).get(reverse(name, args=[data[target].pk])).status_code == 404


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("recipes:edit", {"title": "Hackeada", "course": "main", "servings": "2"}),
        ("recipes:share", {}),
        ("recipes:delete", {}),
        ("recipes:rate", {"stars": "5"}),
        ("recipes:comment_add", {"body": "hola"}),
        ("recipes:add_to_grocery", {"servings": "2"}),
    ],
)
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_ajeno_da_404_al_modificarlo(login_as, data, name, payload, who, target):
    recipe = data[target]
    response = login_as(data[who]).post(reverse(name, args=[recipe.pk]), payload, **UNDO)
    assert response.status_code == 404
    recipe.refresh_from_db()
    assert (
        recipe.title != "Hackeada"
        and recipe.visibility != ""
        and Recipe.objects.filter(pk=recipe.pk).exists()
    )
    assert not RecipeRating.objects.filter(recipe=recipe).exists()
    assert not RecipeComment.objects.filter(recipe=recipe).exists()


def test_crear_receta_con_foto(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("recipes:create"),
        {
            "title": "Gazpacho",
            "course": "starter",
            "visibility": "shared",
            "servings": "6",
            "ingredients_text": "1 kg de tomates\n1 pepino",
            "instructions": "Triturar.",
            "photo": image_file(),
        },
    )
    recipe = Recipe.objects.get(title="Gazpacho")
    assert response.status_code == 302 and recipe.image and recipe.owner == data["luis"]
    image = login_as(data["ana"]).get(reverse("recipes:image", args=[recipe.pk]))
    assert image.status_code == 200 and image["Content-Type"] == "image/webp"
    assert "private" in image["Cache-Control"]
    assert login_as(data["eva"]).get(reverse("recipes:image", args=[recipe.pk])).status_code == 404


def test_foto_invalida_en_el_formulario(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("recipes:create"),
        {
            "title": "X",
            "course": "main",
            "visibility": "shared",
            "servings": "2",
            "photo": SimpleUploadedFile("x.jpg", b"nada", content_type="image/jpeg"),
        },
    )
    assert response.status_code == 400 and not Recipe.objects.filter(title="X").exists()


def test_detalle_con_raciones_y_lista(login_as, data):
    r = data["tortilla"]
    client = login_as(data["luis"])
    html = client.get(reverse("recipes:detail", args=[r.pk]) + "?raciones=8").content.decode()
    assert "1000 g patatas" in html and "8 huevos" in html
    assert client.get(reverse("recipes:detail", args=[r.pk]) + "?raciones=abc").status_code == 200
    ids = [str(i.pk) for i in r.ingredients.all()]
    response = client.post(
        reverse("recipes:add_to_grocery", args=[r.pk]), {"servings": "2", "ingredient": ids}
    )
    assert response.status_code == 302 and "raciones=2" in response.url
    assert GroceryItem.objects.count() == 4


def test_editar_conserva_ingredientes(login_as, data):
    r = data["tortilla"]
    client = login_as(data["luis"])
    html = client.get(reverse("recipes:edit", args=[r.pk])).content.decode()
    assert "500 g patatas" in html
    client.post(
        reverse("recipes:edit", args=[r.pk]),
        {"title": "Tortilla", "course": "main", "servings": "2", "ingredients_text": "3 huevos"},
    )
    r.refresh_from_db()
    assert r.title == "Tortilla" and [i.name for i in r.ingredients.all()] == ["huevos"]


def test_borrar_y_valorar(login_as, data):
    r = data["tortilla"]
    assert (
        login_as(data["luis"])
        .post(reverse("recipes:rate", args=[r.pk]), {"stars": "5"}, HTTP_HX_REQUEST="true")
        .status_code
        == 200
    )
    assert (
        login_as(data["luis"]).post(reverse("recipes:delete", args=[r.pk]), **UNDO).status_code
        == 403
    )
    assert (
        login_as(data["ana"]).post(reverse("recipes:delete", args=[r.pk]), **UNDO).status_code
        == 204
    )


# --- Foto de perfil -----------------------------------------------------------------------


def test_foto_de_perfil(login_as, data):
    client = login_as(data["luis"])
    client.post(reverse("core:avatar_upload"), {"photo": image_file()})
    data["luis"].refresh_from_db()
    assert data["luis"].avatar.name.startswith("avatars/")
    url = reverse("core:avatar", args=[data["luis"].pk])
    assert client.get(url).status_code == 200
    assert login_as(data["ana"]).get(url).status_code == 200  # comparte hogar
    assert login_as(data["eva"]).get(url).status_code == 404  # otro hogar
    html = login_as(data["ana"]).get(reverse("core:household")).content.decode()
    assert url in html
    client = login_as(data["luis"])
    client.post(reverse("core:avatar_upload"), {"remove": "1"})
    data["luis"].refresh_from_db()
    assert not data["luis"].avatar


def test_foto_de_perfil_invalida(login_as, data):
    client = login_as(data["luis"])
    response = client.post(
        reverse("core:avatar_upload"),
        {"photo": SimpleUploadedFile("x.png", b"no", content_type="image/png")},
    )
    assert response.status_code == 302
    data["luis"].refresh_from_db()
    assert not data["luis"].avatar


def test_foto_de_perfil_anonimo(client, data):
    response = client.get(reverse("core:avatar", args=[data["luis"].pk]))
    assert response.status_code == 302


@override_settings(LANGUAGE_CODE="es")
def test_visibilidad_por_defecto(data):
    assert data["tortilla"].visibility == Visibility.SHARED
