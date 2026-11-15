from django.urls import path

from . import views

app_name = "media"

urlpatterns = [
    path("", views.TitleListView.as_view(), name="list"),
    path("azar/", views.RandomView.as_view(), name="random"),
    path("nueva/", views.TitleCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TitleDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.TitleEditView.as_view(), name="edit"),
    path("<int:pk>/estado/", views.StatusView.as_view(), name="status"),
    path("<int:pk>/compartir/", views.ShareView.as_view(), name="share"),
    path("<int:pk>/borrar/", views.DeleteView.as_view(), name="delete"),
    path("<int:pk>/valorar/", views.RateView.as_view(), name="rate"),
    path("<int:pk>/progreso/", views.ProgressView.as_view(), name="progress"),
    path("<int:pk>/comentar/", views.CommentAddView.as_view(), name="comment_add"),
    path("comentarios/<int:pk>/borrar/", views.CommentDeleteView.as_view(), name="comment_delete"),
]
