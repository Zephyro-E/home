from django.urls import path

from . import views

app_name = "shopping"

urlpatterns = [
    # Lista de la compra
    path("", views.GroceryListView.as_view(), name="list"),
    path("anadir/", views.GroceryAddView.as_view(), name="grocery_add"),
    path("<int:pk>/marcar/", views.GroceryToggleView.as_view(), name="grocery_toggle"),
    path("borrar/", views.GroceryDeleteView.as_view(), name="grocery_delete"),
    # Deseos
    path("deseos/", views.WishListView.as_view(), name="wishes"),
    path("deseos/nuevo/", views.WishCreateView.as_view(), name="wish_create"),
    path("deseos/<int:pk>/", views.WishDetailView.as_view(), name="wish_detail"),
    path("deseos/<int:pk>/editar/", views.WishEditView.as_view(), name="wish_edit"),
    path("deseos/<int:pk>/estado/", views.WishStatusView.as_view(), name="wish_status"),
    path("deseos/<int:pk>/compartir/", views.WishShareView.as_view(), name="wish_share"),
    path("deseos/<int:pk>/votar/", views.WishVoteView.as_view(), name="wish_vote"),
    path("deseos/<int:pk>/comentar/", views.WishCommentView.as_view(), name="wish_comment"),
    path("deseos/<int:pk>/borrar/", views.WishDeleteView.as_view(), name="wish_delete"),
    path("comentarios/<int:pk>/borrar/", views.CommentDeleteView.as_view(), name="comment_delete"),
]
