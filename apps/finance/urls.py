from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.SummaryView.as_view(), name="summary"),
    path("movimientos/", views.TransactionListView.as_view(), name="transactions"),
    path("movimientos/nuevo/", views.TransactionCreateView.as_view(), name="transaction_create"),
    path("movimientos/<int:pk>/", views.TransactionEditView.as_view(), name="transaction_edit"),
    path(
        "movimientos/<int:pk>/borrar/",
        views.TransactionDeleteView.as_view(),
        name="transaction_delete",
    ),
    path("cuentas/", views.AccountListView.as_view(), name="accounts"),
    path("cuentas/nueva/", views.AccountCreateView.as_view(), name="account_create"),
    path("cuentas/<int:pk>/", views.AccountEditView.as_view(), name="account_edit"),
    path("compartidos/", views.SharedView.as_view(), name="shared"),
    path("compartidos/pago/", views.SettlementCreateView.as_view(), name="settlement_create"),
    path(
        "compartidos/pago/<int:pk>/borrar/",
        views.SettlementDeleteView.as_view(),
        name="settlement_delete",
    ),
    path("compartidos/reparto/", views.DefaultSplitView.as_view(), name="default_split"),
    path("presupuestos/", views.BudgetsView.as_view(), name="budgets"),
    path("ahorro/", views.GoalsView.as_view(), name="goals"),
    path("ahorro/<int:pk>/", views.GoalEditView.as_view(), name="goal_edit"),
    path("ahorro/<int:pk>/aportar/", views.GoalContributeView.as_view(), name="goal_contribute"),
    path("ahorro/<int:pk>/borrar/", views.GoalDeleteView.as_view(), name="goal_delete"),
    path("categorias/", views.CategoriesView.as_view(), name="categories"),
    path("categorias/<int:pk>/borrar/", views.CategoryDeleteView.as_view(), name="category_delete"),
]
