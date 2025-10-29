from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # AUTH
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # DASHBOARDS
    path("dashboard/", views.dashboard, name="dashboard"),
    path("agent/dashboard/", views.agent_dashboard, name="agent_dashboard"),

    # USER MANAGEMENT
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/toggle-status/", views.toggle_user_status, name="toggle_user_status"),
    path("users/<int:user_id>/reset-password/", views.reset_user_password, name="reset_user_password"),
    path("add-user/", views.add_user, name="add_user"),

    # AGENT MANAGEMENT
    path("agents/register/", views.register_agent, name="register_agent"),
    path("agents/", views.agent_list, name="agent_list"),

    # REPORTS
    path("reports/", views.admin_reports, name="admin_reports"),
    path("reports/export/<str:format>/", views.export_report, name="export_report"),
]
