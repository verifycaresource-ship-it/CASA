from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db.models import Sum, F, FloatField
from django.db.models.functions import Coalesce
from django.urls import reverse
from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import base64

from .models import Hospital, HospitalAssignment
from .serializers import HospitalSerializer
from clients.models import Client
from policies.models import Policy
from claims.models import Claim
from accounts.utils import roles_required
from .forms import HospitalForm

User = get_user_model()


@login_required
@roles_required("hospital")
def assignment_detail(request, pk):
    hospital = getattr(request.user, "hospital_profile", None)
    assignment = get_object_or_404(HospitalAssignment, pk=pk, hospital=hospital)
    return render(request, "hospitals/assignment_detail.html", {
        "assignment": assignment,
        "dashboard_title": f"Assignment Details: {assignment.client.first_name} {assignment.client.last_name}",
        "hospital": hospital,
    })

# =========================
# 🏥 HOSPITAL CRUD
# =========================
@login_required
@roles_required("admin", "finance_officer")
def hospital_delete(request, pk):
    hospital = get_object_or_404(Hospital, pk=pk)
    hospital_name = hospital.name
    if request.method == "POST":
        if hospital.user:
            hospital.user.delete()
        hospital.delete()
        messages.success(request, f"Hospital '{hospital_name}' deleted successfully.")
        return redirect("hospitals:hospital_list")
    return render(request, "hospitals/hospital_confirm_delete.html", {
        "hospital": hospital,
        "dashboard_title": f"Delete Hospital: {hospital.name}"
    })


@login_required
def hospital_list(request):
    user = request.user
    role = getattr(user, "role", "guest")
    if user.is_superuser or role in ["admin", "finance_officer"]:
        hospitals = Hospital.objects.all().order_by('-created_at')
        title = "All Hospitals"
    else:
        hospitals = Hospital.objects.filter(verified=True).order_by('-created_at')
        title = "Verified Hospitals"
    return render(request, "hospitals/hospital_list.html", {
        "hospitals": hospitals,
        "role": role,
        "user": user,
        "dashboard_title": title,
    })


@login_required
def hospital_detail(request, pk):
    hospital = get_object_or_404(Hospital, pk=pk)
    return render(request, "hospitals/hospital_detail.html", {
        "hospital": hospital,
        "role": getattr(request.user, "role", "guest"),
        "dashboard_title": f"Hospital: {hospital.name}",
    })


@login_required
@roles_required("admin", "finance_officer")
def hospital_form(request, pk=None):
    hospital = get_object_or_404(Hospital, pk=pk) if pk else None
    if request.method == "POST":
        form = HospitalForm(request.POST, request.FILES, instance=hospital)
        if form.is_valid():
            hospital_obj = form.save(commit=False)
            if not hospital:
                username = request.POST.get("username")
                password = request.POST.get("password")
                if not username or not password:
                    messages.error(request, "Username and password are required.")
                    return render(request, "hospitals/hospital_form.html", {"form": form})
                if User.objects.filter(username=username).exists():
                    messages.error(request, f"Username '{username}' is already taken.")
                    return render(request, "hospitals/hospital_form.html", {"form": form})
                user = User.objects.create(
                    username=username,
                    email=form.cleaned_data.get("email"),
                    password=make_password(password),
                    role="hospital",
                    is_active=True
                )
                hospital_obj.user = user
                messages.success(request, f"Hospital '{hospital_obj.name}' created with user '{username}'.")
            else:
                messages.success(request, f"Hospital '{hospital_obj.name}' updated successfully.")
            hospital_obj.save()
            return redirect("hospitals:hospital_list")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = HospitalForm(instance=hospital)
    return render(request, "hospitals/hospital_form.html", {
        "form": form,
        "hospital": hospital,
        "dashboard_title": "Edit Hospital" if hospital else "Add New Hospital",
    })


# =========================
# 🏥 HOSPITAL DASHBOARD
# =========================
@login_required
def hospital_dashboard(request):
    hospital = getattr(request.user, "hospital_profile", None)
    if not hospital:
        messages.error(request, "Your hospital profile is missing.")
        return redirect("accounts:dashboard")
    claims = Claim.objects.filter(hospital=hospital).order_by("-created_at")
    context = {
        "dashboard_title": f"{hospital.name} Dashboard",
        "hospital": hospital,
        "claims": claims,
        "total_claims": claims.count(),
        "pending_claims": claims.filter(status="pending").count(),
        "approved_claims": claims.filter(status="approved").count(),
        "rejected_claims": claims.filter(status="rejected").count(),
        "revenue_collected": claims.filter(status__in=["approved", "reimbursed"]).aggregate(
            total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0)
        )["total"],
        "pending_amount": claims.filter(status="pending").aggregate(
            total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0)
        )["total"],
        "recent_claims": claims[:5],
    }
    return render(request, "hospitals/dashboard.html", context)


# =========================
# 🌐 API VIEWSET
# =========================
class HospitalViewSet(viewsets.ModelViewSet):
    queryset = Hospital.objects.all().order_by('-created_at')
    serializer_class = HospitalSerializer
    permission_classes = [permissions.IsAuthenticated]


# =========================
# 🧭 ADMIN DASHBOARD
# =========================
@login_required
def admin_dashboard(request):
    user = request.user
    role = getattr(user, "role", "guest")
    if not (user.is_superuser or role in ["admin", "finance_officer"]):
        return redirect("accounts:dashboard")
    total_clients = Client.objects.count()
    total_policies = Policy.objects.count()
    total_claims = Claim.objects.count()
    total_hospitals = Hospital.objects.count()
    total_revenue = Policy.objects.aggregate(
        total=Coalesce(Sum(F("premium"), output_field=FloatField()), 0.0)
    )["total"]
    cards = [
        {"label": "Clients", "value": total_clients, "color": "blue"},
        {"label": "Policies", "value": total_policies, "color": "green"},
        {"label": "Claims", "value": total_claims, "color": "yellow"},
        {"label": "Hospitals", "value": total_hospitals, "color": "red"},
        {"label": "Revenue", "value": f"${total_revenue:,.2f}", "color": "purple"},
    ]
    claims_labels = ["Pending", "Approved", "Rejected"]
    claims_data = [
        Claim.objects.filter(status="pending").count(),
        Claim.objects.filter(status="approved").count(),
        Claim.objects.filter(status="rejected").count(),
    ]
    return render(request, "dashboard/dashboard.html", {
        "dashboard_title": "Admin Dashboard",
        "user": user,
        "role": role,
        "cards": cards,
        "claims_labels": json.dumps(claims_labels),
        "claims_data": json.dumps(claims_data),
    })


# =========================
# 🧾 ASSIGN POLICYHOLDER
# =========================
@login_required
@roles_required("admin", "finance_officer")
def assign_policyholder(request):
    hospitals = Hospital.objects.filter(verified=True)
    policies = Policy.objects.filter(is_active=True)
    if request.method == "POST":
        policy_id = request.POST.get("policy")
        hospital_id = request.POST.get("hospital")
        if policy_id and hospital_id:
            policy = Policy.objects.get(pk=policy_id)
            hospital = Hospital.objects.get(pk=hospital_id)
            client = policy.client
            assignment, created = HospitalAssignment.objects.get_or_create(
                client=client,
                policy=policy,
                hospital=hospital,
                defaults={"assigned_by": request.user}
            )
            if created:
                messages.success(request, f"{client} assigned to {hospital} successfully.")
            else:
                messages.warning(request, f"{client} is already assigned to {hospital} for this policy.")
            return redirect("hospitals:assign_policyholder")
        else:
            messages.error(request, "All fields are required.")
    return render(request, "hospitals/assign_policyholder.html", {
        "hospitals": hospitals,
        "policies": policies,
        "dashboard_title": "Assign Policyholder",
    })


# =========================
# 📋 ASSIGNED CLIENTS (Hospital Side)
# =========================
@login_required
@roles_required("hospital")
def assigned_clients(request):
    hospital = getattr(request.user, "hospital_profile", None)
    if not hospital:
        messages.error(request, "Hospital profile missing.")
        return redirect("accounts:dashboard")
    assignments = HospitalAssignment.objects.filter(hospital=hospital).select_related("client", "policy")
    return render(request, "hospitals/assigned_clients.html", {
        "assignments": assignments,
        "dashboard_title": "Assigned Policyholders",
        "hospital": hospital,
    })


# =========================
# 💬 ACCEPT / REJECT ASSIGNMENT
# =========================
@login_required
@roles_required("hospital")
def accept_assignment(request, pk):
    assignment = get_object_or_404(HospitalAssignment, pk=pk, hospital=request.user.hospital_profile)
    assignment.status = "accepted"
    assignment.save()
    messages.success(request, f"Assignment accepted for {assignment.client}.")
    return redirect("hospitals:assigned_clients")


@login_required
@roles_required("hospital")
def approve_assignment(request, pk):
    assignment = get_object_or_404(HospitalAssignment, id=pk, hospital=request.user.hospital_profile)
    if assignment.status == "pending":
        assignment.status = "accepted"
        assignment.save()
        messages.success(request, f"Assignment for {assignment.client} approved.")
    return redirect("hospitals:assigned_clients")


@login_required
@roles_required("hospital")
def reject_assignment(request, pk):
    assignment = get_object_or_404(HospitalAssignment, id=pk, hospital=request.user.hospital_profile)
    assignment.status = "rejected"
    assignment.save()
    messages.warning(request, f"Assignment for {assignment.client} rejected.")
    return redirect("hospitals:assigned_clients")


# =========================
# 🧾 SUBMIT CLAIM WITH FINGERPRINT
# =========================
@login_required
@roles_required("hospital")
def submit_claim(request):
    hospital = getattr(request.user, "hospital_profile", None)
    if not hospital:
        messages.error(request, "Your hospital profile is missing.")
        return redirect("accounts:dashboard")

    client_id = request.GET.get("client")
    policy_id = request.GET.get("policy")
    assignment_id = request.GET.get("assignment")
    client = Client.objects.filter(id=client_id).first() if client_id else None
    policy = Policy.objects.filter(id=policy_id).first() if policy_id else None
    assignment = HospitalAssignment.objects.filter(id=assignment_id).first() if assignment_id else None

    if request.method == "POST":
        client_id = request.POST.get("client")
        policy_id = request.POST.get("policy")
        amount = request.POST.get("amount")
        notes = request.POST.get("notes")
        document = request.FILES.get("document")
        fingerprint_verified = request.POST.get("fingerprint_verified") == "true"

        if not all([client_id, policy_id, amount]):
            messages.error(request, "All required fields must be filled.")
            return redirect(request.path)

        if not fingerprint_verified:
            messages.error(request, "Fingerprint verification is required before submitting the claim.")
            return redirect(request.path)

        client = get_object_or_404(Client, id=client_id)
        policy = get_object_or_404(Policy, id=policy_id)

        claim_number = f"CLM-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        claim = Claim.objects.create(
            claim_number=claim_number,
            client=client,
            policy=policy,
            hospital=hospital,
            amount=amount,
            notes=notes,
            document=document,
            created_by=request.user,
            status="pending",
        )

        if assignment:
            assignment.status = "claimed"
            assignment.claim = claim
            assignment.save(update_fields=["status", "claim"])

        messages.success(request, f"Claim {claim.claim_number} submitted successfully.")
        return redirect("hospitals:assigned_clients")

    clients = Client.objects.filter(hospital_assignments__hospital=hospital).distinct().order_by("first_name")
    policies = Policy.objects.filter(client__in=clients, is_active=True).distinct().order_by("policy_number")

    context = {
        "dashboard_title": "Submit Claim",
        "hospital": hospital,
        "clients": clients,
        "policies": policies,
        "selected_client": client,
        "selected_policy": policy,
        "assignment": assignment,
    }
    return render(request, "hospitals/submit_claim.html", context)


@login_required
@roles_required("hospital")
def submit_claim_for_assignment(request, assignment_id):
    assignment = get_object_or_404(HospitalAssignment, id=assignment_id)
    url = reverse("hospitals:submit_claim") + f"?client={assignment.client.id}&policy={assignment.policy.id}&assignment={assignment.id}"
    return redirect(url)


# =========================
# 🛡 FINGERPRINT VERIFICATION API
# =========================
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from clients.models import Client
from hospitals.models import HospitalAssignment

from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework.response import Response
import requests

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def verify_fingerprint(request, client_id):
    """
    Receive fingerprint template from frontend and verify via Flask service.
    """
    hospital = getattr(request.user, "hospital_profile", None)
    if not hospital:
        return Response({"verified": False, "error": "Hospital profile missing."})

    template = request.data.get("template")
    if not template:
        return Response({"verified": False, "error": "No fingerprint template provided."})

    try:
        # Call Flask service
        resp = requests.post("http://127.0.0.1:5000/verify", json={"template": template}, timeout=10)
        data = resp.json()
        verified = data.get("success", False)
        return Response({"verified": verified})
    except Exception as e:
        return Response({"verified": False, "error": str(e)})




# Example placeholder comparison function
def compare_fingerprints(template1, template2):
    # TODO: Replace with actual SDK comparison logic
    return template1 == template2
