from django.urls import path
from . import views

app_name = "hospitals"

urlpatterns = [
    # Dashboard
    path("", views.hospital_dashboard, name="dashboard"),

    # Hospital CRUD
    path("list/", views.hospital_list, name="hospital_list"),
    path("add/", views.hospital_form, name="hospital_add"),            # Add hospital
    path("<int:pk>/edit/", views.hospital_form, name="hospital_edit"), # Edit hospital
    path("<int:pk>/", views.hospital_detail, name="hospital_detail"),
    path("<int:pk>/delete/", views.hospital_delete, name="hospital_delete"),

    # Assignments
    path("assign-policyholder/", views.assign_policyholder, name="assign_policyholder"),
    path("assigned-clients/", views.assigned_clients, name="assigned_clients"),
    path("approve-assignment/<int:pk>/", views.approve_assignment, name="approve_assignment"),
    path("reject-assignment/<int:pk>/", views.reject_assignment, name="reject_assignment"),
    path("assignment/<int:pk>/", views.assignment_detail, name="assignment_detail"),

    # Claims
    path("submit-claim/", views.submit_claim, name="submit_claim"),
    path("api/verify-fingerprint/<int:client_id>/", views.verify_fingerprint, name="verify_fingerprint"),

    path("submit-claim/<int:assignment_id>/", views.submit_claim_for_assignment, name="submit_claim_for_assignment"),
]
