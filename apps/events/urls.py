from django.urls import path

from . import views

app_name = "calendar"

urlpatterns = [
    path("", views.MonthView.as_view(), name="month"),
    path("semana/", views.WeekView.as_view(), name="week"),
    path("agenda/", views.AgendaView.as_view(), name="agenda"),
    path("nuevo/", views.EventCreateView.as_view(), name="create"),
    path("<int:pk>/", views.EventDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.EventEditView.as_view(), name="edit"),
    path("<int:pk>/compartir/", views.EventShareView.as_view(), name="share"),
    path("<int:pk>/borrar/", views.EventDeleteView.as_view(), name="delete"),
]
