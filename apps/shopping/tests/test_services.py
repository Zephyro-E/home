"""Reglas de negocio de compras."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.models import Visibility
from apps.core.money import format_euros, parse_euros
from apps.shopping import services
from apps.shopping.models import GroceryItem, WishItem

pytestmark = pytest.mark.django_db


def wish(household, owner, visibility=Visibility.SHARED, **extra):
    return services.create_wish(household, owner, name="Sofá", visibility=visibility, **extra)


# --- Importes -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "cents"),
    [("12", 1200), ("12,5", 1250), ("12.50", 1250), (" 0,99 € ", 99), ("1000", 100000)],
)
def test_parse_euros_validos(text, cents):
    assert parse_euros(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "-5", "1.000,50", "12,345", "1e3"])
def test_parse_euros_invalidos(text):
    assert parse_euros(text) is None


def test_format_euros():
    assert format_euros(123456) == "1 234,56 €"  # Django separa los miles con espacio
    assert format_euros(None) == ""


# --- Lista de la compra -------------------------------------------------------------------


def test_anadir_producto_es_compartido(home):
    household, ana, luis = home
    item = services.add_grocery(household, ana, "  Leche   entera ", "2 l")
    assert item.name == "Leche entera"
    assert item.visibility == Visibility.SHARED
    assert list(services.grocery_for(luis, household)) == [item]


def test_anadir_repetido_no_duplica_y_reactiva(home):
    household, ana, luis = home
    item = services.add_grocery(household, ana, "Pan")
    services.set_grocery_checked(item, luis, True)
    again = services.add_grocery(household, luis, "pan", "2")
    assert again.pk == item.pk
    assert not again.is_checked and again.checked_by is None
    assert again.quantity == "2"
    assert GroceryItem.objects.count() == 1


def test_anadir_vacio_falla(home):
    household, ana, _luis = home
    with pytest.raises(ValidationError):
        services.add_grocery(household, ana, "   ")


def test_marcar_y_desmarcar(home):
    household, ana, luis = home
    item = services.add_grocery(household, ana, "Huevos")
    services.set_grocery_checked(item, luis, True)
    item.refresh_from_db()
    assert item.is_checked and item.checked_by == luis and item.checked_at
    services.set_grocery_checked(item, ana, False)
    item.refresh_from_db()
    assert not item.is_checked and item.checked_by is None and item.checked_at is None


def test_borrar_solo_afecta_al_hogar_propio(home, other_home):
    household, ana, _luis = home
    other, eva = other_home
    mine = services.add_grocery(household, ana, "Arroz")
    theirs = services.add_grocery(other, eva, "Arroz")
    assert services.delete_groceries(eva, other, [mine.pk, theirs.pk]) == 1
    assert GroceryItem.objects.filter(pk=mine.pk).exists()


# --- Deseos -------------------------------------------------------------------------------


def test_deseo_personal_solo_lo_ve_su_duenno(home):
    household, ana, luis = home
    item = wish(household, ana, Visibility.PRIVATE)
    assert item in services.wishes_for(ana, household)
    assert item not in services.wishes_for(luis, household)


def test_cualquier_miembro_edita_y_cambia_estado_de_lo_compartido(home):
    household, ana, luis = home
    item = wish(household, ana)
    services.update_wish(item, luis, name="Sofá cama")
    services.change_status(item, luis, WishItem.Status.APPROVED)
    item.refresh_from_db()
    assert item.name == "Sofá cama"
    assert item.status == WishItem.Status.APPROVED
    assert item.status_changed_by == luis and item.status_changed_at


def test_estado_no_valido(home):
    household, ana, _luis = home
    with pytest.raises(ValidationError):
        services.change_status(wish(household, ana), ana, "regalado")


def test_editar_no_cambia_la_visibilidad(home):
    household, ana, _luis = home
    item = wish(household, ana)
    services.update_wish(item, ana, visibility=Visibility.PRIVATE, name="Otro")
    item.refresh_from_db()
    assert item.visibility == Visibility.SHARED


def test_pasar_de_personal_a_compartido_sin_copiar(home):
    household, ana, luis = home
    item = wish(household, ana, Visibility.PRIVATE)
    with pytest.raises(PermissionDenied):
        services.make_shared(item, luis)
    services.make_shared(item, ana)
    assert WishItem.objects.count() == 1
    assert item in services.wishes_for(luis, household)


def test_borrar_compartido_duenno_o_admin(home):
    household, ana, luis = home
    de_ana = wish(household, ana)
    with pytest.raises(PermissionDenied):
        services.delete_wish(de_ana, luis, luis.memberships.get())
    de_luis = wish(household, luis)
    services.delete_wish(de_luis, ana, ana.memberships.get())  # ana es admin
    assert not WishItem.objects.filter(pk=de_luis.pk).exists()


def test_votos_uno_por_persona_modificable_y_retirable(home):
    household, ana, luis = home
    item = wish(household, ana)
    assert services.vote(item, luis, 1) == 1
    assert services.vote(item, luis, -1) == -1
    assert item.votes.count() == 1
    assert services.vote(item, luis, -1) is None
    assert item.votes.count() == 0


def test_votos_no_cambian_el_estado(home):
    household, ana, luis = home
    item = wish(household, ana)
    services.vote(item, ana, 1)
    services.vote(item, luis, 1)
    item.refresh_from_db()
    assert item.status == WishItem.Status.PENDING


def test_no_se_vota_ni_comenta_lo_personal(home):
    household, ana, _luis = home
    item = wish(household, ana, Visibility.PRIVATE)
    with pytest.raises(ValidationError):
        services.vote(item, ana, 1)
    with pytest.raises(ValidationError):
        services.add_comment(item, ana, "hola")


def test_voto_no_valido(home):
    household, ana, _luis = home
    with pytest.raises(ValidationError):
        services.vote(wish(household, ana), ana, 5)


def test_estadisticas_no_se_multiplican_con_comentarios(home):
    household, ana, luis = home
    item = wish(household, ana)
    services.vote(item, ana, 1)
    services.vote(item, luis, 1)
    for text in ("uno", "dos", "tres"):
        services.add_comment(item, luis, text)
    annotated = WishItem.objects.with_stats().get(pk=item.pk)
    assert (annotated.up_count, annotated.down_count, annotated.score) == (2, 0, 2)
    assert annotated.comment_count == 3


def test_solo_el_autor_borra_su_comentario(home):
    household, ana, luis = home
    comment = services.add_comment(wish(household, ana), luis, "¿Y en gris?")
    with pytest.raises(PermissionDenied):
        services.delete_comment(comment, ana)
    services.delete_comment(comment, luis)


def test_resumen_del_inicio(home):
    household, ana, luis = home
    services.add_grocery(household, ana, "Leche")
    hecho = services.add_grocery(household, ana, "Pan")
    services.set_grocery_checked(hecho, ana, True)
    propuesta = wish(household, ana)
    wish(household, ana, Visibility.PRIVATE)  # personal: no cuenta
    services.vote(propuesta, ana, 1)

    assert services.dashboard_summary(ana, household) == {
        "grocery_count": 1,
        "grocery_preview": ["Leche"],
        "wishes_to_vote": 0,
    }
    assert services.dashboard_summary(luis, household)["wishes_to_vote"] == 1
