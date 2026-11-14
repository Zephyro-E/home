from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    # Acceso
    path("entrar/", views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("bienvenida/", views.SetupView.as_view(), name="setup"),
    path("invitacion/<str:token>/", views.AcceptInvitationView.as_view(), name="invitation"),
    # Hogar
    path("sin-hogar/", views.NoHouseholdView.as_view(), name="no_household"),
    path("hogar/", views.HouseholdSettingsView.as_view(), name="household"),
    path("hogar/nombre/", views.HouseholdRenameView.as_view(), name="household_rename"),
    path("hogar/cambiar/<uuid:household_id>/", views.switch_household, name="switch_household"),
    path("hogar/salir/", views.LeaveHouseholdView.as_view(), name="household_leave"),
    path("hogar/invitaciones/", views.InvitationCreateView.as_view(), name="invitation_create"),
    path(
        "hogar/invitaciones/<uuid:pk>/anular/",
        views.InvitationRevokeView.as_view(),
        name="invitation_revoke",
    ),
    path("hogar/miembros/<int:pk>/rol/", views.MemberRoleView.as_view(), name="member_role"),
    path("hogar/miembros/<int:pk>/quitar/", views.MemberRemoveView.as_view(), name="member_remove"),
    # Perfil
    path("perfil/", views.ProfileView.as_view(), name="profile"),
    path("perfil/contrasena/", views.PasswordChangeView.as_view(), name="password_change"),
    path("perfil/tema/", views.save_theme, name="save_theme"),
]
