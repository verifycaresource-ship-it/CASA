import uuid
from datetime import date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.utils import timezone
from django.db.models import Q

from rest_framework import viewsets, permissions

from .models import Policy
from .serializers import PolicySerializer
from clients.models import Client
from accounts.utils import roles_required
from hospitals.models import HospitalAssignment, Hospital


# ------------------------------
# ✅ DRF API View
# ------------------------------
class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [permissions.IsAuthenticated]


# ------------------------------
# ✅ List Policies
# ------------------------------
@login_required
@roles_required("admin", "finance_officer")
def policy_list(request):
    policies = Policy.objects.select_related("client").all().order_by("-start_date")

    # Monthly stats
    today = date.today()
    monthly_policies = policies.filter(start_date__year=today.year, start_date__month=today.month)

    context = {
        "policies": policies,
        "monthly_policies": monthly_policies,
        "dashboard_title": "Policies",
        "role": getattr(request.user, "role", "guest"),
    }
    return render(request, "policies/policy_list.html", context)


# ------------------------------
# ✅ Add / Edit Policy
# ------------------------------
@login_required
@roles_required("admin", "finance_officer")
def policy_form(request, pk=None):
    policy = get_object_or_404(Policy, pk=pk) if pk else None
    clients = Client.objects.all()
    auto_policy_number = policy.policy_number if policy else f"POL-{uuid.uuid4().hex[:8].upper()}"
    today = timezone.now().date()
    next_year = today.replace(year=today.year + 1)

    if request.method == "POST":
        data = request.POST
        client = get_object_or_404(Client, pk=data.get("client"))
        policy_number = data.get("policy_number") or auto_policy_number
        required_fields = ["policy_type", "start_date", "expiry_date", "premium"]

        if all(data.get(f) for f in required_fields):
            try:
                if policy:
                    # Update existing policy
                    policy.client = client
                    policy.policy_number = policy_number
                    policy.policy_type = data.get("policy_type")
                    policy.start_date = data.get("start_date")
                    policy.expiry_date = data.get("expiry_date")
                    policy.premium = data.get("premium")
                    policy.is_active = data.get("is_active") == "on"
                    policy.coverage_details = data.get("coverage_details", "")
                    policy.max_claim_limit = data.get("max_claim_limit") or 0
                    policy.waiting_period_days = data.get("waiting_period_days") or 0
                    policy.save()
                    messages.success(request, f"Policy '{policy.policy_number}' updated successfully.")
                else:
                    # Create new policy
                    Policy.objects.create(
                        client=client,
                        policy_number=policy_number,
                        policy_type=data.get("policy_type"),
                        start_date=data.get("start_date"),
                        expiry_date=data.get("expiry_date"),
                        premium=data.get("premium"),
                        is_active=data.get("is_active") == "on",
                        coverage_details=data.get("coverage_details", ""),
                        max_claim_limit=data.get("max_claim_limit") or 0,
                        waiting_period_days=data.get("waiting_period_days") or 0,
                        created_by=request.user,
                    )
                    messages.success(request, f"Policy '{policy_number}' added successfully.")
                return redirect("policies:policy_list")
            except IntegrityError:
                messages.error(request, "Policy number already exists.")
        else:
            messages.error(request, "Please fill in all required fields.")

    return render(request, "policies/policy_form.html", {
        "policy": policy,
        "clients": clients,
        "policy_types": Policy.POLICY_TYPE,
        "dashboard_title": "Edit Policy" if policy else "Add New Policy",
        "role": getattr(request.user, "role", "guest"),
        "auto_policy_number": auto_policy_number,
        "today": today,
        "next_year": next_year,
    })


# ------------------------------
# ✅ Policy Detail View
# ------------------------------
@login_required
@roles_required("admin", "finance_officer", "hospital")
def policy_detail(request, pk):
    policy = get_object_or_404(Policy, pk=pk)
    assigned_clients = policy.hospital_assignments.select_related("client", "hospital", "assigned_by")
    return render(request, "policies/policy_detail.html", {
        "policy": policy,
        "assigned_clients": assigned_clients,
        "dashboard_title": f"Policy Detail: {policy.policy_number}"
    })


# ------------------------------
# ✅ Assign Policy to Hospital
# ------------------------------
@login_required
@roles_required("admin", "finance_officer")
def assign_to_hospital(request, pk):
    policy = get_object_or_404(Policy, pk=pk)
    hospitals = Hospital.objects.filter(verified=True)

    if request.method == "POST":
        hospital_id = request.POST.get("hospital")
        hospital = get_object_or_404(Hospital, id=hospital_id)

        assignment, created = HospitalAssignment.objects.get_or_create(
            client=policy.client,
            policy=policy,
            hospital=hospital,
            defaults={"assigned_by": request.user}
        )
        if created:
            messages.success(request, f"{policy.client} successfully assigned to {hospital.name}.")
        else:
            messages.info(request, f"{policy.client} is already assigned to {hospital.name}.")
        return redirect("policies:policy_detail", pk=policy.pk)

    return render(request, "policies/assign_hospital.html", {
        "policy": policy,
        "hospitals": hospitals,
        "dashboard_title": f"Assign Hospital for {policy.policy_number}",
    })
