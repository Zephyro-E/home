from django.urls import path

from . import views

app_name = "recipes"

urlpatterns = [
    path("", views.RecipeListView.as_view(), name="list"),
    path("nueva/", views.RecipeCreateView.as_view(), name="create"),
    path("<int:pk>/", views.RecipeDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.RecipeEditView.as_view(), name="edit"),
    path("<int:pk>/foto/", views.RecipeImageView.as_view(), name="image"),
    path("<int:pk>/compra/", views.AddToGroceryView.as_view(), name="add_to_grocery"),
    path("<int:pk>/compartir/", views.ShareView.as_view(), name="share"),
    path("<int:pk>/borrar/", views.DeleteView.as_view(), name="delete"),
    path("<int:pk>/valorar/", views.RateView.as_view(), name="rate"),
    path("<int:pk>/comentar/", views.CommentAddView.as_view(), name="comment_add"),
    path("comentarios/<int:pk>/borrar/", views.CommentDeleteView.as_view(), name="comment_delete"),
]
