"""Invitaciones y gestión de miembros."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Invitation, Membership, User, hash_token

pytestmark = pytest.mark.django_db

SIGNUP = {
    "name": "Marta",
    "email": "marta@casa.test",
    "password1": "una-clave-larga-123",
    "password2": "una-clave-larga-123",
}


def create_link(client):
    client.post(reverse("core:invitation_create"), {"role": "member"})
    url = client.get(reverse("core:household")).context["new_invite_url"]
    return url.split("/invitacion/")[1].rstrip("/")


# --- Invitaciones ------------------------------------------------------------------------


def test_admin_crea_invitacion_y_solo_se_guarda_el_hash(login_as, home):
    _household, ana, _luis = home
    token = create_link(login_as(ana))
    invitation = Invitation.objects.get()
    assert invitation.token_hash == hash_token(token)
    assert token not in invitation.token_hash


def test_el_enlace_solo_se_muestra_una_vez(login_as, home):
    _household, ana, _luis = home
    client = login_as(ana)
    create_link(client)
    assert client.get(reverse("core:household")).context["new_invite_url"] is None


def test_un_miembro_no_puede_invitar(login_as, home):
    _household, _ana, luis = home
    response = login_as(luis).post(reverse("core:invitation_create"))
    assert response.status_code == 403
    assert not Invitation.objects.exists()


def test_registro_con_invitacion(client, home):
    household, ana, _luis = home
    _invitation, token = Invitation.create_for(household, ana)
    url = reverse("core:invitation", args=[token])
    assert client.get(url).status_code == 200
    response = client.post(url, SIGNUP)
    assert response.status_code == 302
    marta = User.objects.get(email="marta@casa.test")
    membership = Membership.objects.get(user=marta)
    assert membership.household == household and membership.role == Membership.Role.MEMBER
    assert client.get(reverse("core:home")).status_code == 200


def test_la_invitacion_solo_sirve_una_vez(client, home):
    household, ana, _luis = home
    _invitation, token = Invitation.create_for(household, ana)
    url = reverse("core:invitation", args=[token])
    client.post(url, SIGNUP)
    client.logout()
    response = client.post(url, {**SIGNUP, "email": "otra@casa.test"})
    assert response.status_code == 410
    assert not User.objects.filter(email="otra@casa.test").exists()


def test_invitacion_caducada_o_inventada(client, home):
    household, ana, _luis = home
    invitation, token = Invitation.create_for(household, ana)
    invitation.expires_at = timezone.now() - timedelta(minutes=1)
    invitation.save()
    assert client.get(reverse("core:invitation", args=[token])).status_code == 410
    assert client.get(reverse("core:invitation", args=["inventado"])).status_code == 410


def test_usuario_existente_se_une_con_la_invitacion(login_as, home, other_home):
    household, ana, _luis = home
    _other, eva = other_home
    _invitation, token = Invitation.create_for(household, ana)
    response = login_as(eva).post(reverse("core:invitation", args=[token]))
    assert response.status_code == 302
    assert Membership.objects.filter(household=household, user=eva).exists()


def test_registro_con_email_existente_pide_iniciar_sesion(client, home):
    household, ana, _luis = home
    _invitation, token = Invitation.create_for(household, ana)
    response = client.post(reverse("core:invitation", args=[token]), {**SIGNUP, "email": ana.email})
    assert response.status_code == 400
    assert Invitation.objects.get().used_at is None


def test_anular_invitacion_de_otro_hogar_da_404(login_as, home, other_home):
    household, ana, _luis = home
    _other, eva = other_home
    invitation, _token = Invitation.create_for(household, ana)
    response = login_as(eva).post(reverse("core:invitation_revoke", args=[invitation.pk]))
    assert response.status_code == 404
    assert Invitation.objects.filter(pk=invitation.pk).exists()


def test_anular_invitacion(login_as, home):
    household, ana, _luis = home
    invitation, _token = Invitation.create_for(household, ana)
    login_as(ana).post(reverse("core:invitation_revoke", args=[invitation.pk]))
    assert not Invitation.objects.exists()


# --- Miembros ----------------------------------------------------------------------------


def test_admin_cambia_rol_y_quita_miembros(login_as, home):
    household, ana, luis = home
    client = login_as(ana)
    luis_m = household.memberships.get(user=luis)
    client.post(reverse("core:member_role", args=[luis_m.pk]), {"role": "admin"})
    luis_m.refresh_from_db()
    assert luis_m.is_admin
    client.post(reverse("core:member_remove", args=[luis_m.pk]))
    assert not household.memberships.filter(user=luis).exists()


def test_un_miembro_no_gestiona_miembros(login_as, home):
    household, ana, luis = home
    client = login_as(luis)
    ana_m = household.memberships.get(user=ana)
    assert (
        client.post(reverse("core:member_role", args=[ana_m.pk]), {"role": "member"}).status_code
        == 403
    )
    assert client.post(reverse("core:member_remove", args=[ana_m.pk])).status_code == 403
    assert client.post(reverse("core:household_rename"), {"name": "X"}).status_code == 403


def test_no_se_gestionan_miembros_de_otro_hogar(login_as, home, other_home):
    _household, ana, _luis = home
    other, eva = other_home
    eva_m = other.memberships.get(user=eva)
    response = login_as(ana).post(reverse("core:member_remove", args=[eva_m.pk]))
    assert response.status_code == 404


def test_siempre_queda_alguien_con_administracion(login_as, home):
    household, ana, _luis = home
    client = login_as(ana)
    ana_m = household.memberships.get(user=ana)
    client.post(reverse("core:member_role", args=[ana_m.pk]), {"role": "member"})
    ana_m.refresh_from_db()
    assert ana_m.is_admin
    client.post(reverse("core:household_leave"))
    assert household.memberships.filter(user=ana).exists()


def test_un_miembro_puede_salir(login_as, home):
    household, _ana, luis = home
    client = login_as(luis)
    client.post(reverse("core:household_leave"))
    assert not household.memberships.filter(user=luis).exists()
    assert client.get(reverse("core:home")).url == reverse("core:no_household")


def test_renombrar_hogar(login_as, home):
    household, ana, _luis = home
    login_as(ana).post(reverse("core:household_rename"), {"name": "Nuestra casa"})
    household.refresh_from_db()
    assert household.name == "Nuestra casa"


def test_colores_distintos_por_miembro(home):
    household, _ana, _luis = home
    colors = list(household.memberships.values_list("color", flat=True))
    assert len(colors) == len(set(colors))
