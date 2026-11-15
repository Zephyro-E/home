"""Finanzas: saldos, privacidad, resumen mensual, vistas y autorización."""

from datetime import date

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.core.models import Visibility
from apps.core.money import format_euros
from apps.finance import services
from apps.finance.models import Account, Category, Transaction

pytestmark = pytest.mark.django_db
UNDO = {"HTTP_X_UNDO_COMMIT": "1"}
NOV = date(2026, 11, 10)


@pytest.fixture
def data(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    services.ensure_default_categories(household, ana)
    common = services.create_account(household, ana, name="Común", initial_balance_cents=100_000)
    ana_private = services.create_account(
        household, ana, name="Nómina Ana", visibility="private", initial_balance_cents=50_000
    )
    eva_acc = services.create_account(other, eva, name="De Eva")
    cat = Category.objects.get(household=household, name="Supermercado")
    salary = Category.objects.get(household=household, name="Nómina")
    return {
        "household": household,
        "ana": ana,
        "luis": luis,
        "eva": eva,
        "common": common,
        "ana_private": ana_private,
        "eva_acc": eva_acc,
        "cat": cat,
        "salary": salary,
    }


def expense(d, user, account, cents, **extra):
    return services.create_transaction(
        d["household"],
        user,
        kind="expense",
        amount_cents=cents,
        date=extra.pop("date", NOV),
        account=account,
        category=extra.pop("category", d["cat"]),
        **extra,
    )


def test_formato_negativo():
    assert format_euros(-1250) == "−12,50 €"


def test_categorias_por_defecto_una_sola_vez(data):
    count = Category.objects.filter(household=data["household"]).count()
    services.ensure_default_categories(data["household"], data["luis"])
    assert Category.objects.filter(household=data["household"]).count() == count > 5


def test_saldos_con_gastos_ingresos_y_transferencias(data):
    d = data
    expense(d, d["luis"], d["common"], 2_550)
    services.create_transaction(
        d["household"],
        d["ana"],
        kind="income",
        amount_cents=200_000,
        date=NOV,
        account=d["ana_private"],
        category=d["salary"],
    )
    services.create_transaction(
        d["household"],
        d["ana"],
        kind="transfer",
        amount_cents=30_000,
        date=NOV,
        account=d["ana_private"],
        to_account=d["common"],
    )
    b = services.balances([d["common"], d["ana_private"]])
    assert b[d["common"].pk] == 100_000 - 2_550 + 30_000
    assert b[d["ana_private"].pk] == 50_000 + 200_000 - 30_000


def test_privacidad_de_movimientos(data):
    d = data
    solo_ana = expense(d, d["ana"], d["ana_private"], 1_000)
    comun = expense(d, d["luis"], d["common"], 2_000)
    aportacion = services.create_transaction(
        d["household"],
        d["ana"],
        kind="transfer",
        amount_cents=5_000,
        date=NOV,
        account=d["ana_private"],
        to_account=d["common"],
    )
    assert solo_ana.visibility == Visibility.PRIVATE
    assert comun.visibility == Visibility.SHARED
    assert aportacion.visibility == Visibility.SHARED  # toca la cuenta común
    luis_ve = set(services.transactions_for(d["luis"], d["household"]))
    assert luis_ve == {comun, aportacion}
    # Luis ve la aportación pero no puede editarla: no puede usar la cuenta de Ana.
    assert not aportacion.can_edit(d["luis"])
    with pytest.raises(PermissionDenied):
        services.update_transaction(
            aportacion,
            d["luis"],
            kind="transfer",
            amount_cents=1,
            date=NOV,
            account=d["ana_private"],
            to_account=d["common"],
        )


def test_no_se_usan_cuentas_ajenas(data):
    d = data
    with pytest.raises(ValidationError):
        expense(d, d["luis"], d["ana_private"], 100)
    with pytest.raises(ValidationError):
        expense(d, d["ana"], d["eva_acc"], 100)


@pytest.mark.parametrize(
    "extra",
    [
        {"kind": "transfer", "to_account": None},
        {"kind": "transfer", "to_account": "same"},
        {"kind": "expense", "amount_cents": 0},
        {"kind": "income", "category": "expense-cat"},
        {"kind": "loan"},
    ],
)
def test_movimientos_invalidos(data, extra):
    d = data
    payload = {
        "kind": "expense",
        "amount_cents": 100,
        "date": NOV,
        "account": d["common"],
        "category": None,
    }
    payload.update(extra)
    if payload.get("to_account") == "same":
        payload["to_account"] = d["common"]
    if payload.get("category") == "expense-cat":
        payload["category"] = d["cat"]
    with pytest.raises(ValidationError):
        services.create_transaction(d["household"], d["ana"], **payload)


def test_transferencia_no_lleva_categoria(data):
    d = data
    tx = services.create_transaction(
        d["household"],
        d["ana"],
        kind="transfer",
        amount_cents=100,
        date=NOV,
        account=d["common"],
        to_account=d["ana_private"],
        category=d["cat"],
    )
    assert tx.category is None


def test_resumen_mensual(data):
    d = data
    expense(d, d["luis"], d["common"], 6_000)
    expense(d, d["luis"], d["common"], 4_000, category=None)
    expense(d, d["ana"], d["ana_private"], 1_000)
    expense(d, d["luis"], d["common"], 9_999, date=date(2026, 12, 1))  # otro mes
    services.create_transaction(
        d["household"],
        d["ana"],
        kind="income",
        amount_cents=150_000,
        date=NOV,
        account=d["ana_private"],
        category=d["salary"],
    )
    services.create_transaction(  # las transferencias no cuentan
        d["household"],
        d["ana"],
        kind="transfer",
        amount_cents=50_000,
        date=NOV,
        account=d["ana_private"],
        to_account=d["common"],
    )
    ana = services.month_summary(d["ana"], d["household"], NOV)
    assert (ana["income"], ana["expense"], ana["net"]) == (150_000, 11_000, 139_000)
    assert [r["total"] for r in ana["by_category"]] == [7_000, 4_000]
    assert ana["by_category"][1]["name"] == "Sin categoría"
    luis = services.month_summary(d["luis"], d["household"], NOV)
    assert (luis["income"], luis["expense"]) == (0, 10_000)
    assert services.month_summary(d["ana"], d["household"], NOV, "mio")["expense"] == 1_000
    assert services.month_summary(d["ana"], d["household"], NOV, "comun")["expense"] == 10_000


def test_cuenta_con_movimientos_no_se_borra(data):
    d = data
    expense(d, d["ana"], d["common"], 100)
    with pytest.raises(ValidationError):
        services.delete_account(d["common"], d["ana"], d["ana"].memberships.get())
    services.set_archived(d["common"], d["luis"], True)
    assert d["common"] not in services.accounts_for(
        d["luis"], d["household"], include_archived=False
    )
    empty = services.create_account(d["household"], d["ana"], name="Vacía")
    services.delete_account(empty, d["ana"], d["ana"].memberships.get())


def test_cuenta_no_cambia_de_privacidad(data):
    d = data
    services.update_account(d["common"], d["luis"], name="Común casa", visibility="private")
    d["common"].refresh_from_db()
    assert d["common"].visibility == Visibility.SHARED and d["common"].name == "Común casa"


def test_borrar_categoria_deja_movimientos_sin_categoria(data):
    d = data
    tx = expense(d, d["ana"], d["common"], 100)
    services.delete_category(d["cat"])
    tx.refresh_from_db()
    assert tx.category is None


def test_categoria_duplicada(data):
    with pytest.raises(ValidationError):
        services.create_category(data["household"], data["luis"], "supermercado", "expense", "teal")
    services.create_category(data["household"], data["luis"], "Supermercado", "income", "teal")


# --- Vistas -------------------------------------------------------------------------------

PAGES = [
    "finance:summary",
    "finance:transactions",
    "finance:transaction_create",
    "finance:accounts",
    "finance:account_create",
    "finance:categories",
]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    response = client.get(reverse(name))
    assert response.status_code == 302 and reverse("core:login") in response.url


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


def test_vistas_no_muestran_lo_privado_ajeno(login_as, data):
    d = data
    expense(d, d["ana"], d["ana_private"], 1_234, description="Regalo secreto")
    services.create_transaction(
        d["household"],
        d["ana"],
        kind="transfer",
        amount_cents=5_000,
        date=date.today(),
        account=d["ana_private"],
        to_account=d["common"],
        description="Aportación",
    )
    client = login_as(d["luis"])
    for name in ("finance:summary", "finance:transactions", "finance:accounts"):
        html = client.get(reverse(name) + "?mes=" + date.today().strftime("%Y-%m")).content.decode()
        assert "Nómina Ana" not in html and "Regalo secreto" not in html and "De Eva" not in html
    html = client.get(reverse("finance:transactions")).content.decode()
    assert "Aportación" in html and "Cuenta personal de Ana" in html
    form = client.get(reverse("finance:transaction_create")).content.decode()
    assert "Nómina Ana" not in form


@pytest.mark.parametrize(("who", "target"), [("luis", "private"), ("ana", "foreign")])
def test_movimiento_ajeno_da_404(login_as, data, who, target):
    d = data
    tx = (
        expense(d, d["ana"], d["ana_private"], 100)
        if target == "private"
        else Transaction.objects.create(
            household=d["eva_acc"].household,
            owner=d["eva"],
            kind="expense",
            amount_cents=1,
            date=NOV,
            account=d["eva_acc"],
        )
    )
    client = login_as(d[who])
    assert client.get(reverse("finance:transaction_edit", args=[tx.pk])).status_code == 404
    assert (
        client.post(reverse("finance:transaction_delete", args=[tx.pk]), **UNDO).status_code == 404
    )
    assert Transaction.objects.filter(pk=tx.pk).exists()


@pytest.mark.parametrize(("who", "target"), [("luis", "ana_private"), ("ana", "eva_acc")])
def test_cuenta_ajena_da_404(login_as, data, who, target):
    acc = data[target]
    client = login_as(data[who])
    assert client.get(reverse("finance:account_edit", args=[acc.pk])).status_code == 404
    client.post(reverse("finance:account_edit", args=[acc.pk]), {"archive": "1"})
    acc.refresh_from_db()
    assert not acc.is_archived


def test_crear_movimiento_desde_formulario(login_as, data):
    d = data
    response = login_as(d["luis"]).post(
        reverse("finance:transaction_create"),
        {
            "kind": "expense",
            "amount": "45,90",
            "date": "2026-11-12",
            "description": "Compra",
            "account": d["common"].pk,
            "expense_category": d["cat"].pk,
        },
    )
    assert response.status_code == 302
    tx = Transaction.objects.get(description="Compra")
    assert (tx.amount_cents, tx.category, tx.owner) == (4_590, d["cat"], d["luis"])


def test_formulario_rechaza_cuenta_privada_ajena(login_as, data):
    d = data
    response = login_as(d["luis"]).post(
        reverse("finance:transaction_create"),
        {"kind": "expense", "amount": "5", "date": "2026-11-12", "account": d["ana_private"].pk},
    )
    assert response.status_code == 400
    assert not Transaction.objects.exists()


@pytest.mark.parametrize("amount", ["", "abc", "-5", "0"])
def test_formulario_importe_invalido(login_as, data, amount):
    response = login_as(data["luis"]).post(
        reverse("finance:transaction_create"),
        {"kind": "expense", "amount": amount, "date": "2026-11-12", "account": data["common"].pk},
    )
    assert response.status_code == 400


def test_editar_y_borrar_movimiento(login_as, data):
    d = data
    tx = expense(d, d["ana"], d["common"], 1_000)
    client = login_as(d["luis"])
    html = client.get(reverse("finance:transaction_edit", args=[tx.pk])).content.decode()
    assert 'value="10,00"' in html
    client.post(
        reverse("finance:transaction_edit", args=[tx.pk]),
        {
            "kind": "income",
            "amount": "12",
            "date": "2026-11-12",
            "account": d["common"].pk,
            "income_category": d["salary"].pk,
        },
    )
    tx.refresh_from_db()
    assert (tx.kind, tx.amount_cents, tx.category) == ("income", 1_200, d["salary"])
    # Luis no es admin ni dueño: no puede borrarlo.
    assert (
        client.post(reverse("finance:transaction_delete", args=[tx.pk]), **UNDO).status_code == 403
    )
    admin = login_as(d["ana"])
    assert (
        admin.post(reverse("finance:transaction_delete", args=[tx.pk]), **UNDO).status_code == 204
    )


def test_crear_cuenta_y_saldo_negativo(login_as, data):
    client = login_as(data["luis"])
    client.post(
        reverse("finance:account_create"),
        {"name": "Tarjeta", "kind": "card", "visibility": "private", "initial_balance": "-120,50"},
    )
    acc = Account.objects.get(name="Tarjeta")
    assert acc.initial_balance_cents == -12_050 and acc.owner == data["luis"]
    html = client.get(reverse("finance:accounts")).content.decode()
    assert "−120,50 €" in html


def test_categorias_desde_la_vista(login_as, data):
    client = login_as(data["luis"])
    assert (
        client.post(
            reverse("finance:categories"), {"name": "Mascotas", "kind": "expense", "color": "amber"}
        ).status_code
        == 302
    )
    cat = Category.objects.get(name="Mascotas")
    assert client.post(reverse("finance:category_delete", args=[cat.pk]), **UNDO).status_code == 204


def test_filtros_y_mes_raro(login_as, data):
    d = data
    expense(d, d["luis"], d["common"], 100, description="Pan")
    client = login_as(d["luis"])
    html = client.get(
        reverse("finance:transactions") + f"?mes=2026-11&cuenta={d['common'].pk}&tipo=expense"
    ).content.decode()
    assert "Pan" in html
    assert client.get(reverse("finance:summary") + "?mes=99999-1").status_code == 200
