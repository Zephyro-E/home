from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.BoardView.as_view(), name="board"),
    path("rapida/", views.QuickAddView.as_view(), name="quick_add"),
    path("nueva/", views.TaskCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TaskDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.TaskEditView.as_view(), name="edit"),
    path("<int:pk>/mover/", views.MoveView.as_view(), name="move"),
    path("<int:pk>/estado/", views.StatusView.as_view(), name="status"),
    path("<int:pk>/compartir/", views.TaskShareView.as_view(), name="share"),
    path("<int:pk>/borrar/", views.TaskDeleteView.as_view(), name="delete"),
    path("<int:pk>/subtareas/", views.SubtaskAddView.as_view(), name="subtask_add"),
    path("subtareas/<int:pk>/marcar/", views.SubtaskToggleView.as_view(), name="subtask_toggle"),
    path("subtareas/<int:pk>/borrar/", views.SubtaskDeleteView.as_view(), name="subtask_delete"),
    path("<int:pk>/comentar/", views.CommentAddView.as_view(), name="comment_add"),
    path("comentarios/<int:pk>/borrar/", views.CommentDeleteView.as_view(), name="comment_delete"),
    path("etiquetas/", views.LabelsView.as_view(), name="labels"),
    path("etiquetas/<int:pk>/borrar/", views.LabelDeleteView.as_view(), name="label_delete"),
]
