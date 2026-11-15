from django.urls import path

from . import views

app_name = "places"

urlpatterns = [
    path("", views.PlaceListView.as_view(), name="list"),
    path("azar/", views.RandomView.as_view(), name="random"),
    path("nuevo/", views.PlaceCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PlaceDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.PlaceEditView.as_view(), name="edit"),
    path("<int:pk>/visitado/", views.VisitedView.as_view(), name="visited"),
    path("<int:pk>/compartir/", views.ShareView.as_view(), name="share"),
    path("<int:pk>/borrar/", views.DeleteView.as_view(), name="delete"),
    path("<int:pk>/valorar/", views.RateView.as_view(), name="rate"),
    path("<int:pk>/comentar/", views.CommentAddView.as_view(), name="comment_add"),
    path("comentarios/<int:pk>/borrar/", views.CommentDeleteView.as_view(), name="comment_delete"),
]
