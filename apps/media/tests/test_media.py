"""Películas y series: reglas, vistas y autorización."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.core.models import Visibility
from apps.media import services
from apps.media.models import SeriesProgress, Title, TitleComment, TitleRating

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
        "movie": services.create_title(household, ana, title="Amélie", kind="movie", genre="Comedia"),
        "series": services.create_title(household, ana, title="Dark", kind="series"),
        "private": services.create_title(household, ana, title="Secreta", visibility="private"),
        "foreign": services.create_title(other, eva, title="Ajena"),
    }


# --- Servicios ----------------------------------------------------------------------------


def test_valorar_cambiar_y_retirar(data):
    movie, luis = data["movie"], data["luis"]
    assert services.rate(movie, luis, 4) == 4
    assert services.rate(movie, luis, 2) == 2
    assert TitleRating.objects.filter(title=movie).count() == 1
    assert services.rate(movie, luis, 2) is None
    with pytest.raises(ValidationError):
        services.rate(movie, luis, 6)


def test_media_de_valoraciones_no_se_altera_con_comentarios(data):
    movie = data["movie"]
    services.rate(movie, data["ana"], 5)
    services.rate(movie, data["luis"], 2)
    for n in range(3):
        services.add_comment(movie, data["luis"], f"c{n}")
    item = services.listing(data["ana"], data["household"]).get(pk=movie.pk)
    assert (item.avg_stars, item.rating_count, item.comment_count) == (3.5, 2, 3)


def test_progreso_de_series(data):
    series, luis = data["series"], data["luis"]
    services.next_episode(series, luis)
    services.next_episode(series, luis)
    progress = SeriesProgress.objects.get(title=series, user=luis)
    assert (progress.season, progress.episode) == (1, 2)
    series.refresh_from_db()
    assert series.status == Title.Status.WATCHING  # al empezar, pasa a "viendo"
    services.set_progress(series, luis, 2, 0)
    progress.refresh_from_db()
    assert (progress.season, progress.episode) == (2, 0)
    with pytest.raises(ValidationError):
        services.set_progress(data["movie"], luis, 1, 1)
    with pytest.raises(ValidationError):
        services.set_progress(series, luis, 0, 1)


def test_filtros_y_busqueda(data):
    household, ana = data["household"], data["ana"]
    services.set_status(data["movie"], ana, Title.Status.WATCHED)
    pending = {t.title for t in services.listing(ana, household)}
    assert pending == {"Dark", "Secreta"}
    assert [t.title for t in services.listing(ana, household, "vistas")] == ["Amélie"]
    assert [t.title for t in services.listing(ana, household, "por-ver", "series")] == ["Dark"]
    assert [t.title for t in services.listing(ana, household, "vistas", "", "comed")] == ["Amélie"]


def test_azar_solo_lo_visible_y_por_ver(data):
    luis, household = data["luis"], data["household"]
    picks = {services.pick_random(luis, household).title for _ in range(30)}
    assert picks == {"Amélie", "Dark"}
    assert services.pick_random(luis, household, "series").title == "Dark"
    other = services.pick_random(luis, household, "", exclude=data["movie"].pk)
    assert other.title == "Dark"


def test_azar_sin_nada(data):
    assert services.pick_random(data["eva"], data["household"]) is None


def test_permisos(data):
    luis = data["luis"]
    with pytest.raises(PermissionDenied):
        services.update_title(data["private"], luis, title="x")
    with pytest.raises(PermissionDenied):
        services.delete_title(data["movie"], luis, luis.memberships.get())
    with pytest.raises(PermissionDenied):
        services.make_shared(data["private"], luis)
    services.update_title(data["movie"], luis, title="Amélie (2001)")


# --- Vistas -------------------------------------------------------------------------------


PAGES = ["media:list", "media:create", "media:random"]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    response = client.get(reverse(name))
    assert response.status_code == 302 and reverse("core:login") in response.url


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


def test_listado_solo_lo_visible(login_as, data):
    html = login_as(data["luis"]).get(reverse("media:list")).content.decode()
    assert "Amélie" in html and "Dark" in html
    assert "Secreta" not in html and "Ajena" not in html


@pytest.mark.parametrize("name", ["media:detail", "media:edit"])
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_ajeno_da_404_al_verlo(login_as, data, name, who, target):
    assert login_as(data[who]).get(reverse(name, args=[data[target].pk])).status_code == 404


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("media:edit", {"title": "Hackeado", "kind": "movie", "status": "pending"}),
        ("media:status", {"status": "watched"}),
        ("media:share", {}),
        ("media:delete", {}),
        ("media:rate", {"stars": "5"}),
        ("media:progress", {"next": "1"}),
        ("media:comment_add", {"body": "hola"}),
    ],
)
@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_ajeno_da_404_al_modificarlo(login_as, data, name, payload, who, target):
    item = data[target]
    response = login_as(data[who]).post(reverse(name, args=[item.pk]), payload, **UNDO)
    assert response.status_code == 404
    item.refresh_from_db()
    assert item.title != "Hackeado" and item.status == Title.Status.PENDING
    assert not item.ratings.exists() and not item.comments.exists()


def test_crear_y_editar(login_as, data):
    client = login_as(data["luis"])
    response = client.post(
        reverse("media:create"),
        {"title": "Severance", "kind": "series", "visibility": "shared", "status": "pending",
         "platform": "Apple TV", "year": "2022"},
    )
    item = Title.objects.get(title="Severance")
    assert response.status_code == 302 and item.owner == data["luis"] and item.year == 2022
    bad = client.post(
        reverse("media:create"),
        {"title": "X", "kind": "movie", "visibility": "shared", "status": "pending", "year": "3000"},
    )
    assert bad.status_code == 400
    client.post(
        reverse("media:edit", args=[item.pk]),
        {"title": "Severance", "kind": "series", "status": "watching", "platform": "Apple TV+"},
    )
    item.refresh_from_db()
    assert item.platform == "Apple TV+" and item.status == "watching"


def test_valorar_con_htmx(login_as, data):
    movie = data["movie"]
    response = login_as(data["luis"]).post(reverse("media:rate", args=[movie.pk]), {"stars": "4"}, **HTMX)
    assert response.status_code == 200
    assert f'id="rating-{movie.pk}"' in response.content.decode()
    assert TitleRating.objects.get(title=movie, user=data["luis"]).stars == 4
    bad = login_as(data["luis"]).post(reverse("media:rate", args=[movie.pk]), {"stars": "9"}, **HTMX)
    assert bad.status_code == 400


def test_detalle_de_serie_con_progreso(login_as, data):
    services.set_progress(data["series"], data["ana"], 3, 4)
    client = login_as(data["luis"])
    client.post(reverse("media:progress", args=[data["series"].pk]), {"season": "1", "episode": "5"})
    html = client.get(reverse("media:detail", args=[data["series"].pk])).content.decode()
    assert "T3 E4" in html  # el progreso de Ana
    assert 'value="5"' in html  # el suyo, en el formulario


def test_azar_con_htmx(login_as, data):
    response = login_as(data["luis"]).get(reverse("media:random") + "?tipo=series", **HTMX)
    html = response.content.decode()
    assert "Dark" in html and "<html" not in html


def test_comentarios(login_as, data):
    movie = data["movie"]
    client = login_as(data["luis"])
    client.post(reverse("media:comment_add", args=[movie.pk]), {"body": "¡Qué bonita!"})
    comment = TitleComment.objects.get(title=movie)
    other = login_as(data["ana"]).post(reverse("media:comment_delete", args=[comment.pk]), **UNDO)
    assert other.status_code == 403
    eva = login_as(data["eva"]).post(reverse("media:comment_delete", args=[comment.pk]), **UNDO)
    assert eva.status_code == 404
    mine = login_as(data["luis"]).post(reverse("media:comment_delete", args=[comment.pk]), **UNDO)
    assert mine.status_code == 204


def test_borrar_y_compartir(login_as, data):
    client = login_as(data["ana"])
    client.post(reverse("media:share", args=[data["private"].pk]))
    data["private"].refresh_from_db()
    assert data["private"].visibility == Visibility.SHARED
    assert client.post(reverse("media:delete", args=[data["movie"].pk]), **UNDO).status_code == 204
    assert not Title.objects.filter(pk=data["movie"].pk).exists()
