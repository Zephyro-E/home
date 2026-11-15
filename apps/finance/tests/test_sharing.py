"""Finanzas II: repartos, saldos entre miembros, pagos, presupuestos, ahorro y gráficos."""

from datetime import date

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from apps.core import services as core_services
from apps.core.models import Membership, Visibility
from apps.finance import planning, services, sharing
from apps.finance.models import Budget, Category, SavingsGoal, Settlement, Transaction

pytestmark = pytest.mark.django_db
NOV = date(2026, 11, 10)
UNDO = {"HTTP_X_UNDO_COMMIT": "1"}


@pytest.fixture
def data(home, other_home):
    household, ana, luis = home
    other, eva = other_home
    services.ensure_default_categories(household, ana)
    return {
        "household": household,
        "ana": ana,
        "luis": luis,
        "eva": eva,
        "other": other,
        "common": services.create_account(household, ana, name="Común"),
        "ana_card": services.create_account(
            household, ana, name="Tarjeta Ana", visibility="private"
        ),
        "luis_cash": services.create_account(
            household, luis, name="Efectivo Luis", visibility="private"
        ),
        "cat": Category.objects.get(household=household, name="Supermercado"),
    }


def split_expense(d, user, account, cents, shares=None, **extra):
    return services.create_transaction(
        d["household"],
        user,
        kind="expense",
        amount_cents=cents,
        date=extra.pop("date", NOV),
        account=account,
        category=extra.pop("category", d["cat"]),
        is_split=True,
        split_shares=shares,
        **extra,
    )


# --- Reparto al céntimo -------------------------------------------------------------------


def test_allocate_suma_exacta_y_determinista():
    assert sharing.allocate(1001, [("a", 5000), ("b", 5000)]) == [("a", 501), ("b", 500)]
    assert sharing.allocate(100, [("a", 3333), ("b", 3333), ("c", 3334)]) == [
        ("a", 33),
        ("b", 33),
        ("c", 34),
    ]
    parts = sharing.allocate(9999, [("a", 7000), ("b", 3000)])
    assert sum(c for _k, c in parts) == 9999
    with pytest.raises(ValidationError):
        sharing.allocate(100, [("a", 5000), ("b", 4000)])


def test_reparto_por_defecto_normalizado(data, make_user):
    shares = sharing.default_shares(data["household"])
    assert [(u.name, bp) for u, bp in shares] == [("Ana", 5000), ("Luis", 5000)]
    third = make_user(name="Teo")
    core_services.add_member(data["household"], third)  # tres miembros con 5000 cada uno
    shares = sharing.default_shares(data["household"])
    assert sum(bp for _u, bp in shares) == 10_000
    assert sorted(bp for _u, bp in shares) == [3333, 3333, 3334]


def test_cambiar_reparto_por_defecto(data):
    d = data
    ana_m = d["ana"].memberships.get()
    luis_m = d["luis"].memberships.get()
    with pytest.raises(PermissionDenied):
        sharing.set_default_shares(d["household"], luis_m, {d["ana"].pk: 6000, d["luis"].pk: 4000})
    with pytest.raises(ValidationError):
        sharing.set_default_shares(d["household"], ana_m, {d["ana"].pk: 6000, d["luis"].pk: 3000})
    sharing.set_default_shares(d["household"], ana_m, {d["ana"].pk: 6000, d["luis"].pk: 4000})
    assert [bp for _u, bp in sharing.default_shares(d["household"])] == [6000, 4000]


# --- Gastos compartidos y saldos ----------------------------------------------------------


def test_gasto_compartido_por_defecto_y_saldo(data):
    d = data
    tx = split_expense(d, d["ana"], d["ana_card"], 6_001)
    assert tx.is_split and tx.visibility == Visibility.SHARED
    assert sorted(s.amount_cents for s in tx.splits.all()) == [3_000, 3_001]
    assert tx in services.transactions_for(d["luis"], d["household"])
    net = sharing.balances(d["household"])
    luis_share = tx.splits.get(user=d["luis"]).amount_cents
    assert net == {d["ana"].pk: luis_share, d["luis"].pk: -luis_share}
    assert sharing.suggested_payments(net) == [(d["luis"].pk, d["ana"].pk, luis_share)]


def test_excepcion_de_reparto(data):
    d = data
    tx = split_expense(d, d["luis"], d["luis_cash"], 10_000, [(d["ana"], 10_000), (d["luis"], 0)])
    assert [(s.user, s.amount_cents) for s in tx.splits.all()] == [(d["ana"], 10_000)]
    assert sharing.balances(d["household"]) == {d["luis"].pk: 10_000, d["ana"].pk: -10_000}


def test_no_se_reparte_lo_pagado_desde_la_cuenta_comun(data):
    with pytest.raises(ValidationError):
        split_expense(data, data["ana"], data["common"], 1_000)


def test_reparto_invalido(data, other_home):
    d = data
    with pytest.raises(ValidationError):
        split_expense(d, d["ana"], d["ana_card"], 100, [(d["ana"], 5000), (d["luis"], 4000)])
    with pytest.raises(ValidationError):
        split_expense(d, d["ana"], d["ana_card"], 100, [(d["ana"], 5000), (d["eva"], 5000)])


def test_solo_los_gastos_se_reparten(data):
    d = data
    tx = services.create_transaction(
        d["household"],
        d["ana"],
        kind="income",
        amount_cents=100,
        date=NOV,
        account=d["ana_card"],
        is_split=True,
    )
    assert not tx.is_split and tx.visibility == Visibility.PRIVATE and not tx.splits.exists()


def test_editar_quita_y_rehace_el_reparto(data):
    d = data
    tx = split_expense(d, d["ana"], d["ana_card"], 2_000)
    services.update_transaction(
        tx,
        d["ana"],
        kind="expense",
        amount_cents=3_000,
        date=NOV,
        account=d["ana_card"],
        is_split=True,
        split_shares=[(d["ana"], 2_500), (d["luis"], 7_500)],
    )
    assert sorted(s.amount_cents for s in tx.splits.all()) == [750, 2_250]
    services.update_transaction(
        tx,
        d["ana"],
        kind="expense",
        amount_cents=3_000,
        date=NOV,
        account=d["ana_card"],
        is_split=False,
    )
    tx.refresh_from_db()
    assert not tx.is_split and not tx.splits.exists() and tx.visibility == Visibility.PRIVATE
    assert sharing.balances(d["household"]) == {}


def test_luis_ve_pero_no_edita_el_gasto_de_ana(data):
    d = data
    tx = split_expense(d, d["ana"], d["ana_card"], 2_000)
    assert not tx.can_edit(d["luis"])


def test_pagos_entre_miembros_saldan(data):
    d = data
    split_expense(d, d["ana"], d["ana_card"], 6_000)
    pay = sharing.create_settlement(d["household"], d["luis"], d["luis"], d["ana"], 3_000, NOV)
    assert sharing.balances(d["household"]) == {}
    with pytest.raises(ValidationError):
        sharing.create_settlement(d["household"], d["luis"], d["luis"], d["luis"], 100, NOV)
    with pytest.raises(ValidationError):
        sharing.create_settlement(d["household"], d["luis"], d["luis"], d["eva"], 100, NOV)
    with pytest.raises(ValidationError):
        sharing.create_settlement(d["household"], d["luis"], d["luis"], d["ana"], 0, NOV)
    sharing.delete_settlement(pay, d["ana"], d["ana"].memberships.get())
    assert sharing.balances(d["household"]) != {}


def test_pagos_minimos_con_tres_personas():
    net = {1: 5_000, 2: -3_000, 3: -2_000}
    assert sharing.suggested_payments(net) == [(2, 1, 3_000), (3, 1, 2_000)]
    assert sharing.suggested_payments({}) == []


def test_borrar_pago_ajeno(data, make_user):
    d = data
    teo = make_user(name="Teo")
    core_services.add_member(d["household"], teo)
    pay = sharing.create_settlement(d["household"], d["luis"], d["luis"], d["ana"], 100, NOV)
    with pytest.raises(PermissionDenied):
        sharing.delete_settlement(pay, teo, teo.memberships.get())


# --- Presupuestos y ahorro ----------------------------------------------------------------


def test_presupuesto_cuenta_lo_comun(data):
    d = data
    planning.set_budget(d["household"], d["ana"], d["cat"], 10_000)
    services.create_transaction(
        d["household"],
        d["luis"],
        kind="expense",
        amount_cents=7_000,
        date=NOV,
        account=d["common"],
        category=d["cat"],
    )
    split_expense(d, d["ana"], d["ana_card"], 2_500)  # compartido: cuenta
    services.create_transaction(  # personal: no cuenta
        d["household"],
        d["ana"],
        kind="expense",
        amount_cents=9_999,
        date=NOV,
        account=d["ana_card"],
        category=d["cat"],
    )
    (row,) = planning.budget_progress(d["luis"], d["household"], NOV)
    assert (row["spent"], row["left"], row["percent"], row["state"]) == (9_500, 500, 95, "warn")
    planning.set_budget(d["household"], d["ana"], d["cat"], 5_000)
    (row,) = planning.budget_progress(d["luis"], d["household"], NOV)
    assert row["state"] == "over" and row["bar"] == 100
    planning.set_budget(d["household"], d["ana"], d["cat"], 0)
    assert not Budget.objects.exists()


def test_presupuesto_solo_categorias_de_gasto(data):
    d = data
    income = Category.objects.get(household=d["household"], name="Nómina")
    with pytest.raises(ValidationError):
        planning.set_budget(d["household"], d["ana"], income, 100)


def test_meta_con_cuenta_y_manual(data):
    d = data
    savings = services.create_account(
        d["household"], d["ana"], name="Ahorro", kind="savings", initial_balance_cents=40_000
    )
    linked = planning.create_goal(
        d["household"], d["ana"], name="Vacaciones", target_cents=100_000, account=savings
    )
    manual = planning.create_goal(d["household"], d["luis"], name="Sofá", target_cents=50_000)
    planning.contribute(manual, d["ana"], 20_000)
    planning.contribute(manual, d["ana"], -5_000)
    with pytest.raises(ValidationError):
        planning.contribute(linked, d["ana"], 100)
    rows = {r["goal"].name: r for r in planning.goal_progress([linked, manual])}
    assert (rows["Vacaciones"]["saved"], rows["Vacaciones"]["percent"]) == (40_000, 40)
    assert (rows["Sofá"]["saved"], rows["Sofá"]["left"]) == (15_000, 35_000)


def test_meta_comun_no_usa_cuenta_personal(data):
    d = data
    with pytest.raises(ValidationError):
        planning.create_goal(
            d["household"], d["ana"], name="X", target_cents=1, account=d["ana_card"]
        )
    with pytest.raises(ValidationError):
        planning.create_goal(
            d["household"],
            d["luis"],
            name="X",
            target_cents=1,
            account=d["ana_card"],
            visibility="private",
        )
    planning.create_goal(
        d["household"],
        d["ana"],
        name="Mía",
        target_cents=1,
        account=d["ana_card"],
        visibility="private",
    )


def test_grafico_doce_meses(data):
    d = data
    services.create_transaction(
        d["household"],
        d["ana"],
        kind="expense",
        amount_cents=5_000,
        date=date(2026, 3, 5),
        account=d["common"],
        category=d["cat"],
    )
    services.create_transaction(
        d["household"],
        d["ana"],
        kind="income",
        amount_cents=10_000,
        date=NOV,
        account=d["common"],
    )
    rows = planning.monthly_totals(d["ana"], d["household"], NOV)
    assert (
        len(rows) == 12
        and rows[0]["month"] == date(2025, 12, 1)
        and rows[-1]["month"] == date(2026, 11, 1)
    )
    march = next(r for r in rows if r["month"] == date(2026, 3, 1))
    assert (march["expense"], march["expense_pct"]) == (5_000, 50)
    assert rows[-1]["income_pct"] == 100


# --- Vistas -------------------------------------------------------------------------------

PAGES = ["finance:shared", "finance:budgets", "finance:goals"]


@pytest.mark.parametrize("name", PAGES)
def test_anonimo_va_a_la_entrada(client, data, name):
    assert reverse("core:login") in client.get(reverse(name)).url


@pytest.mark.parametrize("name", PAGES)
def test_paginas_responden(login_as, data, name):
    assert login_as(data["luis"]).get(reverse(name)).status_code == 200


def test_formulario_de_gasto_compartido(login_as, data):
    d = data
    client = login_as(d["luis"])
    form = client.get(reverse("finance:transaction_create")).content.decode()
    assert f'name="share_{d["ana"].pk}"' in form
    response = client.post(
        reverse("finance:transaction_create"),
        {
            "kind": "expense",
            "amount": "30",
            "date": "2026-11-10",
            "account": d["luis_cash"].pk,
            "is_split": "on",
            f"share_{d['ana'].pk}": "70",
            f"share_{d['luis'].pk}": "30",
        },
    )
    assert response.status_code == 302
    tx = Transaction.objects.get()
    assert [(s.user, s.amount_cents) for s in tx.splits.all()] == [
        (d["ana"], 2_100),
        (d["luis"], 900),
    ]
    bad = client.post(
        reverse("finance:transaction_create"),
        {
            "kind": "expense",
            "amount": "30",
            "date": "2026-11-10",
            "account": d["luis_cash"].pk,
            "is_split": "on",
            f"share_{d['ana'].pk}": "70",
            f"share_{d['luis'].pk}": "20",
        },
    )
    assert bad.status_code == 400 and Transaction.objects.count() == 1


def test_pagina_compartidos_muestra_deudas(login_as, data):
    d = data
    split_expense(d, d["ana"], d["ana_card"], 6_000, description="Compra grande")
    html = login_as(d["luis"]).get(reverse("finance:shared") + "?mes=2026-11").content.decode()
    assert "Compra grande" in html and "30,00 €" in html and "Tarjeta Ana" not in html


def test_registrar_y_borrar_pago(login_as, data):
    d = data
    client = login_as(d["luis"])
    response = client.post(
        reverse("finance:settlement_create"),
        {"from_user": d["luis"].pk, "to_user": d["ana"].pk, "amount": "12,5", "date": "2026-11-10"},
    )
    assert response.status_code == 302
    pay = Settlement.objects.get()
    assert pay.amount_cents == 1_250
    bad = client.post(
        reverse("finance:settlement_create"),
        {"from_user": d["luis"].pk, "to_user": d["eva"].pk, "amount": "5", "date": "2026-11-10"},
    )
    assert bad.status_code == 400
    assert (
        client.post(reverse("finance:settlement_delete", args=[pay.pk]), **UNDO).status_code == 204
    )


def test_pago_de_otro_hogar_da_404(login_as, data):
    d = data
    pay = sharing.create_settlement(d["household"], d["ana"], d["luis"], d["ana"], 100, NOV)
    response = login_as(d["eva"]).post(reverse("finance:settlement_delete", args=[pay.pk]), **UNDO)
    assert response.status_code == 404


def test_reparto_por_defecto_desde_la_vista(login_as, data):
    d = data
    payload = {f"share_{d['ana'].pk}": "60", f"share_{d['luis'].pk}": "40"}
    assert login_as(d["luis"]).post(reverse("finance:default_split"), payload).status_code == 403
    login_as(d["ana"]).post(reverse("finance:default_split"), payload)
    assert Membership.objects.get(user=d["ana"]).default_share_bp == 6_000


def test_presupuestos_y_metas_desde_la_vista(login_as, data):
    d = data
    client = login_as(d["luis"])
    assert (
        client.post(
            reverse("finance:budgets"), {"category": d["cat"].pk, "amount": "300"}
        ).status_code
        == 302
    )
    assert Budget.objects.get().amount_cents == 30_000
    client.post(
        reverse("finance:goals"), {"name": "Viaje", "target": "1000", "visibility": "shared"}
    )
    goal = SavingsGoal.objects.get()
    client.post(reverse("finance:goal_contribute", args=[goal.pk]), {"amount": "150"})
    goal.refresh_from_db()
    assert goal.saved_cents == 15_000
    html = client.get(reverse("finance:summary")).content.decode()
    assert "Últimos 12 meses" in html


def test_meta_privada_ajena_da_404(login_as, data):
    d = data
    goal = planning.create_goal(
        d["household"], d["ana"], name="Secreta", target_cents=1, visibility="private"
    )
    client = login_as(d["luis"])
    assert client.get(reverse("finance:goal_edit", args=[goal.pk])).status_code == 404
    client.post(reverse("finance:goal_contribute", args=[goal.pk]), {"amount": "5"})
    assert client.post(reverse("finance:goal_delete", args=[goal.pk]), **UNDO).status_code == 404
    goal.refresh_from_db()
    assert goal.saved_cents == 0
