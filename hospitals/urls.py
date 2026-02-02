from django.urls import path
from . import views

app_name = "hospitals"

urlpatterns = [
    # DASHBOARD
    path("", views.hospital_dashboard, name="dashboard"),

    # HOSPITAL CRUD
    path("list/", views.hospital_list, name="hospital_list"),
    path("add/", views.hospital_form, name="hospital_add"),
    path("<int:pk>/edit/", views.hospital_form, name="hospital_edit"),
    path("<int:pk>/", views.hospital_detail, name="hospital_detail"),
    path("<int:pk>/delete/", views.hospital_delete, name="hospital_delete"),

    # ASSIGNMENTS
    path("assign-policyholder/", views.assign_policyholder, name="assign_policyholder"),
    path("assigned-clients/", views.assigned_clients, name="assigned_clients"),
    path("approve-assignment/<int:pk>/", views.approve_assignment, name="approve_assignment"),
    path("reject-assignment/<int:pk>/", views.reject_assignment, name="reject_assignment"),
    path("assignment/<int:pk>/", views.assignment_detail, name="assignment_detail"),
    path("verify-policy/", views.verify_policy, name="verify_policy"),  # AJAX verify

    # CLAIMS
    path("submit-claim/", views.submit_claim, name="submit_claim"),
    path("submit-claim/<int:assignment_id>/", views.submit_claim_for_assignment, name="submit_claim_for_assignment"),

    # FINGERPRINT API
    path("api/verify-fingerprint/<int:client_id>/", views.verify_fingerprint, name="verify_fingerprint"),
    path("print/<int:assignment_id>/", views.print_claim_certificate, name="print_claim_certificate")

]
