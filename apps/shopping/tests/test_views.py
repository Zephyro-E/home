"""Vistas de compras: funcionamiento y autorización (otro miembro, otro hogar, anónimo)."""

import pytest
from django.urls import reverse

from apps.core.models import Visibility
from apps.shopping import services
from apps.shopping.models import GroceryItem, WishComment, WishItem, WishVote

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}
UNDO = {"HTTP_X_UNDO_COMMIT": "1"}


@pytest.fixture
def data(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    return {
        "household": household,
        "ana": ana,
        "luis": luis,
        "eva": eva,
        "grocery": services.add_grocery(household, ana, "Leche"),
        "shared": services.create_wish(household, ana, name="Sofá", visibility=Visibility.SHARED),
        "private": services.create_wish(
            household, ana, name="Reloj", visibility=Visibility.PRIVATE
        ),
        "foreign": services.create_wish(other, eva, name="Tele", visibility=Visibility.SHARED),
    }


# --- Acceso -------------------------------------------------------------------------------

PAGES = ["shopping:list", "shopping:wishes", "shopping:wish_create"]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert reverse("core:login") in response.url


def test_anonimo_no_puede_borrar(client, data):
    client.post(reverse("shopping:grocery_delete"), {"id": data["grocery"].pk})
    assert GroceryItem.objects.filter(pk=data["grocery"].pk).exists()


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


def test_sin_hogar_redirige(login_as, make_user):
    response = login_as(make_user()).get(reverse("shopping:list"))
    assert response.status_code == 302
    assert response.url == reverse("core:no_household")


WISH_GET = ["shopping:wish_detail", "shopping:wish_edit"]
WISH_POST = [
    ("shopping:wish_status", {"status": "bought"}),
    ("shopping:wish_share", {}),
    ("shopping:wish_vote", {"value": "1"}),
    ("shopping:wish_comment", {"body": "hola"}),
    ("shopping:wish_delete", {}),
]


@pytest.mark.parametrize("name", WISH_GET)
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_deseo_ajeno_da_404_al_verlo(login_as, data, name, who, target):
    response = login_as(data[who]).get(reverse(name, args=[data[target].pk]))
    assert response.status_code == 404


@pytest.mark.parametrize(("name", "payload"), WISH_POST)
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_deseo_ajeno_da_404_al_modificarlo(login_as, data, name, payload, who, target):
    item = data[target]
    before = (item.name, item.status, item.visibility)
    response = login_as(data[who]).post(reverse(name, args=[item.pk]), payload)
    assert response.status_code == 404
    item.refresh_from_db()
    assert (item.name, item.status, item.visibility) == before
    assert not WishVote.objects.filter(item=item).exists()
    assert not WishComment.objects.filter(item=item).exists()


def test_producto_de_otro_hogar_da_404(login_as, data):
    client = login_as(data["eva"])
    pk = data["grocery"].pk
    assert (
        client.post(reverse("shopping:grocery_toggle", args=[pk]), {"checked": "1"}).status_code
        == 404
    )
    client.post(reverse("shopping:grocery_delete"), {"id": pk}, **UNDO)
    assert GroceryItem.objects.filter(pk=pk, is_checked=False).exists()


def test_privado_ajeno_no_aparece_en_listados(login_as, data):
    client = login_as(data["luis"])
    shared = client.get(reverse("shopping:wishes")).content.decode()
    mine = client.get(reverse("shopping:wishes") + "?ver=mios").content.decode()
    assert "Sofá" in shared
    assert "Reloj" not in shared and "Reloj" not in mine
    assert "Tele" not in shared


def test_miembro_no_admin_no_borra_lo_compartido_ajeno(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("shopping:wish_delete", args=[data["shared"].pk]), **UNDO
    )
    assert response.status_code == 403
    assert WishItem.objects.filter(pk=data["shared"].pk).exists()


def test_no_se_borra_el_comentario_de_otro(login_as, data):
    comment = services.add_comment(data["shared"], data["ana"], "mío")
    response = login_as(data["luis"]).post(
        reverse("shopping:comment_delete", args=[comment.pk]), **UNDO
    )
    assert response.status_code == 403
    assert WishComment.objects.filter(pk=comment.pk).exists()


def test_comentario_de_otro_hogar_da_404(login_as, data):
    comment = services.add_comment(data["shared"], data["ana"], "mío")
    response = login_as(data["eva"]).post(reverse("shopping:comment_delete", args=[comment.pk]))
    assert response.status_code == 404


# --- Lista de la compra -------------------------------------------------------------------


def test_anadir_con_htmx_devuelve_la_lista(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("shopping:grocery_add"), {"name": "Pan", "quantity": "2"}, **HTMX
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="grocery-list"' in html and "Pan" in html and "Leche" in html
    assert "<html" not in html


def test_anadir_sin_javascript_redirige(login_as, data):
    response = login_as(data["luis"]).post(reverse("shopping:grocery_add"), {"name": "Pan"})
    assert response.status_code == 302
    assert GroceryItem.objects.filter(name="Pan").exists()


def test_marcar_producto(login_as, data):
    pk = data["grocery"].pk
    login_as(data["luis"]).post(
        reverse("shopping:grocery_toggle", args=[pk]), {"checked": "1"}, **HTMX
    )
    item = GroceryItem.objects.get(pk=pk)
    assert item.is_checked and item.checked_by == data["luis"]


def test_borrado_definitivo_tras_deshacer(login_as, data):
    otro = services.add_grocery(data["household"], data["ana"], "Pan")
    response = login_as(data["luis"]).post(
        reverse("shopping:grocery_delete"), {"id": [data["grocery"].pk, otro.pk, "x"]}, **UNDO
    )
    assert response.status_code == 204
    assert not GroceryItem.objects.exists()


def test_borrar_exige_post(login_as, data):
    response = login_as(data["ana"]).get(reverse("shopping:grocery_delete"))
    assert response.status_code == 405


# --- Deseos -------------------------------------------------------------------------------


def test_crear_deseo_con_precio(login_as, data):
    response = login_as(data["luis"]).post(
        reverse("shopping:wish_create"),
        {
            "name": "Bici",
            "visibility": "private",
            "price": "249,90",
            "priority": "high",
            "url": "tienda.test/bici",
        },
    )
    item = WishItem.objects.get(name="Bici")
    assert response.status_code == 302
    assert response.url == reverse("shopping:wish_detail", args=[item.pk])
    assert item.owner == data["luis"]
    assert item.estimated_price_cents == 24990
    assert item.visibility == Visibility.PRIVATE
    assert item.url == "https://tienda.test/bici"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "visibility": "shared", "priority": "medium"},
        {"name": "X", "visibility": "shared", "priority": "medium", "price": "doce"},
        {"name": "X", "visibility": "shared", "priority": "medium", "url": "javascript:alert(1)"},
        {"name": "X", "visibility": "shared", "priority": "medium", "image_url": "ftp://a.test/x"},
    ],
)
def test_crear_deseo_invalido(login_as, data, payload):
    response = login_as(data["luis"]).post(reverse("shopping:wish_create"), payload)
    assert response.status_code == 400
    assert not WishItem.objects.filter(owner=data["luis"]).exists()


def test_editar_deseo_compartido_otro_miembro(login_as, data):
    item = data["shared"]
    response = login_as(data["luis"]).post(
        reverse("shopping:wish_edit", args=[item.pk]),
        {"name": "Sofá nuevo", "priority": "low", "price": "300", "visibility": "private"},
    )
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.name == "Sofá nuevo"
    assert item.estimated_price_cents == 30000
    assert item.visibility == Visibility.SHARED  # no se cambia desde el formulario


def test_editar_muestra_el_precio(login_as, data):
    item = data["shared"]
    item.estimated_price_cents = 1250
    item.save()
    html = login_as(data["ana"]).get(reverse("shopping:wish_edit", args=[item.pk])).content.decode()
    assert 'value="12,50"' in html


def test_detalle_compartido(login_as, data):
    services.vote(data["shared"], data["ana"], 1)
    services.add_comment(data["shared"], data["ana"], "Me encanta")
    html = (
        login_as(data["luis"])
        .get(reverse("shopping:wish_detail", args=[data["shared"].pk]))
        .content.decode()
    )
    assert "Sofá" in html and "Me encanta" in html
    assert reverse("shopping:wish_status", args=[data["shared"].pk]) in html
    # Luis no es admin ni dueño: no ve el botón de borrar.
    assert reverse("shopping:wish_delete", args=[data["shared"].pk]) not in html


def test_cambiar_estado(login_as, data):
    item = data["shared"]
    login_as(data["luis"]).post(
        reverse("shopping:wish_status", args=[item.pk]), {"status": "approved"}
    )
    item.refresh_from_db()
    assert item.status == WishItem.Status.APPROVED


def test_compartir_propio(login_as, data):
    item = data["private"]
    login_as(data["ana"]).post(reverse("shopping:wish_share", args=[item.pk]))
    item.refresh_from_db()
    assert item.visibility == Visibility.SHARED


def test_votar_con_htmx(login_as, data):
    item = data["shared"]
    response = login_as(data["luis"]).post(
        reverse("shopping:wish_vote", args=[item.pk]), {"value": "1", "detail": "1"}, **HTMX
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert f'id="votes-{item.pk}"' in html and "Luis" in html
    assert WishVote.objects.get(item=item, user=data["luis"]).value == 1


def test_votar_lo_personal_da_400(login_as, data):
    response = login_as(data["ana"]).post(
        reverse("shopping:wish_vote", args=[data["private"].pk]), {"value": "1"}
    )
    assert response.status_code == 400


def test_comentar_y_borrar_comentario(login_as, data):
    client = login_as(data["luis"])
    item = data["shared"]
    client.post(reverse("shopping:wish_comment", args=[item.pk]), {"body": "  ¿Cabe?  "})
    comment = WishComment.objects.get(item=item)
    assert comment.body == "¿Cabe?" and comment.author == data["luis"]
    response = client.post(reverse("shopping:comment_delete", args=[comment.pk]), **UNDO)
    assert response.status_code == 204
    assert not WishComment.objects.exists()


def test_duenno_borra_su_deseo(login_as, data):
    response = login_as(data["ana"]).post(
        reverse("shopping:wish_delete", args=[data["private"].pk]), **UNDO
    )
    assert response.status_code == 204
    assert not WishItem.objects.filter(pk=data["private"].pk).exists()


def test_filtro_por_estado(login_as, data):
    services.change_status(data["shared"], data["ana"], WishItem.Status.BOUGHT)
    client = login_as(data["luis"])
    assert "Sofá" not in client.get(reverse("shopping:wishes")).content.decode()
    bought = client.get(reverse("shopping:wishes") + "?estado=comprados").content.decode()
    assert "Sofá" in bought


def test_inicio_muestra_widgets(login_as, data):
    html = login_as(data["luis"]).get(reverse("core:home")).content.decode()
    assert reverse("shopping:list") in html
    assert "Leche" in html
    assert "Por votar" in html
