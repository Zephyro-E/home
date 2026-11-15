"""Sitios: reglas, vistas y autorización."""

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Visibility
from apps.places import services
from apps.places.models import Place, PlaceComment, PlaceRating

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
        "bar": services.create_place(
            household, ana, name="La Bodeguita", category="bar", location="Centro"
        ),
        "hike": services.create_place(household, ana, name="Ruta del Cares", category="nature"),
        "private": services.create_place(household, ana, name="Spa sorpresa", visibility="private"),
        "foreign": services.create_place(other, eva, name="Sitio ajeno"),
    }


def test_marcar_visitado_y_volver(data):
    bar, luis = data["bar"], data["luis"]
    services.mark_visited(bar, luis)
    assert bar.status == Place.Status.VISITED and bar.visited_on == timezone.localdate()
    services.mark_visited(bar, luis, visited=False)
    assert bar.status == Place.Status.PENDING and bar.visited_on is None


def test_pendiente_no_guarda_fecha_de_visita(data):
    place = services.create_place(
        data["household"], data["ana"], name="X", status="pending", visited_on=timezone.localdate()
    )
    assert place.visited_on is None


def test_azar_por_categoria_y_visibilidad(data):
    luis, household = data["luis"], data["household"]
    picks = {services.pick_random(luis, household).name for _ in range(30)}
    assert picks == {"La Bodeguita", "Ruta del Cares"}
    assert services.pick_random(luis, household, "nature").name == "Ruta del Cares"
    services.mark_visited(data["hike"], luis)
    assert services.pick_random(luis, household, "nature") is None
    assert services.pick_random(luis, household, "", exclude=data["bar"].pk).name == "La Bodeguita"


def test_listado_filtros(data):
    ana, household = data["ana"], data["household"]
    services.mark_visited(data["bar"], ana)
    assert {p.name for p in services.listing(ana, household)} == {"Ruta del Cares", "Spa sorpresa"}
    assert [p.name for p in services.listing(ana, household, "visitados")] == ["La Bodeguita"]
    assert [p.name for p in services.listing(ana, household, "visitados", "", "centro")] == [
        "La Bodeguita"
    ]
    assert [p.name for p in services.listing(ana, household, "pendientes", "nature")] == [
        "Ruta del Cares"
    ]


def test_valoraciones(data):
    services.rate(data["bar"], data["ana"], 5)
    services.rate(data["bar"], data["luis"], 4)
    services.add_comment(data["bar"], data["luis"], "Croquetas top")
    item = services.listing(data["ana"], data["household"]).get(pk=data["bar"].pk)
    assert (item.avg_stars, item.rating_count, item.comment_count) == (4.5, 2, 1)


def test_permisos(data):
    luis = data["luis"]
    with pytest.raises(PermissionDenied):
        services.mark_visited(data["private"], luis)
    with pytest.raises(PermissionDenied):
        services.delete_place(data["bar"], luis, luis.memberships.get())
    with pytest.raises(PermissionDenied):
        services.make_shared(data["private"], luis)


# --- Vistas -------------------------------------------------------------------------------

PAGES = ["places:list", "places:create", "places:random"]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    response = client.get(reverse(name))
    assert response.status_code == 302 and reverse("core:login") in response.url


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


def test_listado_solo_lo_visible(login_as, data):
    html = login_as(data["luis"]).get(reverse("places:list")).content.decode()
    assert "La Bodeguita" in html
    assert "Spa sorpresa" not in html and "Sitio ajeno" not in html


@pytest.mark.parametrize("name", ["places:detail", "places:edit"])
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_ajeno_da_404_al_verlo(login_as, data, name, who, target):
    assert login_as(data[who]).get(reverse(name, args=[data[target].pk])).status_code == 404


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("places:edit", {"name": "Hackeado", "category": "bar", "status": "pending"}),
        ("places:visited", {"visited": "1"}),
        ("places:share", {}),
        ("places:delete", {}),
        ("places:rate", {"stars": "5"}),
        ("places:comment_add", {"body": "hola"}),
    ],
)
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_ajeno_da_404_al_modificarlo(login_as, data, name, payload, who, target):
    place = data[target]
    response = login_as(data[who]).post(reverse(name, args=[place.pk]), payload, **UNDO)
    assert response.status_code == 404
    place.refresh_from_db()
    assert place.name != "Hackeado" and place.status == Place.Status.PENDING
    assert not place.ratings.exists() and not place.comments.exists()


def test_crear_editar_y_visitar(login_as, data):
    client = login_as(data["luis"])
    response = client.post(
        reverse("places:create"),
        {
            "name": "Museo del Prado",
            "category": "culture",
            "visibility": "shared",
            "status": "pending",
            "location": "Madrid",
            "url": "museodelprado.es",
        },
    )
    place = Place.objects.get(name="Museo del Prado")
    assert response.status_code == 302 and place.url == "https://museodelprado.es"
    assert client.post(reverse("places:create"), {"name": "", "category": "bar"}).status_code == 400
    client.post(reverse("places:visited", args=[place.pk]), {"visited": "1"})
    place.refresh_from_db()
    assert place.status == "visited" and place.visited_on


def test_detalle_con_mapa_y_valoracion(login_as, data):
    client = login_as(data["luis"])
    response = client.post(reverse("places:rate", args=[data["bar"].pk]), {"stars": "3"}, **HTMX)
    assert response.status_code == 200
    assert PlaceRating.objects.get(place=data["bar"]).stars == 3
    html = client.get(reverse("places:detail", args=[data["bar"].pk])).content.decode()
    assert "openstreetmap.org/search?query=Centro" in html


def test_azar_con_htmx(login_as, data):
    response = login_as(data["luis"]).get(reverse("places:random") + "?categoria=nature", **HTMX)
    html = response.content.decode()
    assert "Ruta del Cares" in html and "<html" not in html


def test_comentarios_y_borrado(login_as, data):
    client = login_as(data["luis"])
    client.post(reverse("places:comment_add", args=[data["bar"].pk]), {"body": "Volveremos"})
    comment = PlaceComment.objects.get()
    assert (
        client.post(reverse("places:comment_delete", args=[comment.pk]), **UNDO).status_code == 204
    )
    admin = login_as(data["ana"])
    admin.post(reverse("places:share", args=[data["private"].pk]))
    data["private"].refresh_from_db()
    assert data["private"].visibility == Visibility.SHARED
    assert admin.post(reverse("places:delete", args=[data["bar"].pk]), **UNDO).status_code == 204
