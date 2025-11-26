import base64
import uuid
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import viewsets, permissions

from .models import Policy, InsuredPerson
from .serializers import PolicySerializer
from clients.models import Client
from accounts.utils import roles_required
from hospitals.models import HospitalAssignment, Hospital
from claims.models import Claim


# ------------------------------
# DRF API View
# ------------------------------
class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [permissions.IsAuthenticated]


# ------------------------------
# Policy List
# ------------------------------
@login_required
@roles_required("admin", "finance_officer")
def policy_list(request):
    policies = Policy.objects.select_related("client").all().order_by("-start_date")
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
# Add / Edit Policy (with Insured Persons)
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
        files = request.FILES
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
                    policy = Policy.objects.create(
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

                # ----------------------
                # Handle Insured Persons
                # ----------------------
                full_names = data.getlist("insured_full_name[]")
                relationships = data.getlist("insured_relationship[]")
                dobs = data.getlist("insured_dob[]")
                genders = data.getlist("insured_gender[]")
                photos = files.getlist("insured_photo[]")
                insured_ids = data.getlist("insured_id[]")  # hidden inputs

                for i in range(len(full_names)):
                    name = full_names[i].strip() if i < len(full_names) else ""
                    rel = relationships[i].strip() if i < len(relationships) else ""
                    dob_str = dobs[i] if i < len(dobs) else ""
                    gender = genders[i] if i < len(genders) else ""
                    photo = photos[i] if i < len(photos) else None
                    insured_id = insured_ids[i] if i < len(insured_ids) else None

                    if not name or not rel:
                        continue

                    dob_value = None
                    if dob_str:
                        try:
                            dob_value = datetime.strptime(dob_str, "%Y-%m-%d").date()
                        except ValueError:
                            dob_value = None

                    # Update existing insured
                    if insured_id:
                        insured = InsuredPerson.objects.filter(id=insured_id, policy=policy).first()
                        if insured:
                            insured.full_name = name
                            insured.relationship = rel
                            insured.dob = dob_value or insured.dob
                            insured.gender = gender or insured.gender
                            if photo:
                                insured.photo = photo
                            insured.save()
                            continue

                    # Create new insured
                    insured = InsuredPerson.objects.create(
                        policy=policy,
                        full_name=name,
                        relationship=rel,
                        dob=dob_value,
                        gender=gender or None,
                        photo=photo
                    )

                    # Fingerprint capture for adults
                    if insured.is_adult:
                        fingerprint_base64 = data.get(f"fingerprint_base64_{i}")
                        if fingerprint_base64:
                            insured.fingerprint_data = base64.b64decode(fingerprint_base64)
                            insured.fingerprint_verified = True
                            insured.save()

                return redirect("policies:policy_detail", pk=policy.pk)

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
        "GENDER_CHOICES": Client.GENDER_CHOICES,  # ✅ Pass gender choices
    })


# ------------------------------
# Policy Detail
# ------------------------------
@login_required
@roles_required("admin", "finance_officer", "hospital")
def policy_detail(request, pk):
    policy = get_object_or_404(Policy, pk=pk)
    assigned_clients = policy.hospital_assignments.select_related("client", "hospital", "assigned_by")
    insured_persons = policy.insured_persons.all()

    return render(request, "policies/policy_detail.html", {
        "policy": policy,
        "assigned_clients": assigned_clients,
        "insured_persons": insured_persons,
    })


# ------------------------------
# Assign Policy to Hospital
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


# ------------------------------
# Add Insured Person separately
# ------------------------------
@login_required
@roles_required("admin", "finance_officer")
def add_insured_person(request, policy_id):
    policy = get_object_or_404(Policy, id=policy_id)
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        relationship = request.POST.get("relationship")
        dob_str = request.POST.get("dob")
        gender = request.POST.get("gender")
        photo = request.FILES.get("photo")
        fingerprint_base64 = request.POST.get("fingerprint_base64")

        dob_value = None
        if dob_str:
            try:
                dob_value = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                dob_value = None

        if full_name and relationship and dob_value:
            insured = policy.insured_persons.create(
                full_name=full_name.strip(),
                relationship=relationship.strip(),
                dob=dob_value,
                gender=gender or None,
                photo=photo
            )
            if insured.is_adult and fingerprint_base64:
                insured.fingerprint_data = base64.b64decode(fingerprint_base64)
                insured.fingerprint_verified = True
                insured.save()
            messages.success(request, f"{full_name} added to policy {policy.policy_number}.")
            return redirect("policies:policy_detail", pk=policy.id)
        else:
            messages.error(request, "Full name, relationship, and valid DOB are required.")

    return render(request, "policies/add_insured_person.html", {"policy": policy, "GENDER_CHOICES": Client.GENDER_CHOICES})


# ------------------------------
# Edit Insured Person
# ------------------------------
@login_required
@roles_required("admin", "finance_officer")
def edit_insured_person(request, person_id):
    person = get_object_or_404(InsuredPerson, id=person_id)
    policy = person.policy

    if request.method == "POST":
        full_name = request.POST.get("full_name")
        relationship = request.POST.get("relationship")
        dob_str = request.POST.get("dob")
        gender = request.POST.get("gender")

        if full_name:
            person.full_name = full_name.strip()
        if relationship:
            person.relationship = relationship.strip()
        if dob_str:
            try:
                person.dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                messages.warning(request, "Invalid date format, DOB not updated.")

        person.gender = gender if gender else person.gender

        if request.FILES.get("photo"):
            person.photo = request.FILES.get("photo")

        person.save()
        messages.success(request, f"{person.full_name} updated successfully.")
        return redirect("policies:policy_detail", pk=policy.id)

    return render(request, "policies/edit_insured_person.html", {
        "person": person,
        "policy": policy,
        "GENDER_CHOICES": Client.GENDER_CHOICES
    })


# ------------------------------
# Delete Insured Person
# ------------------------------
@login_required
@roles_required("admin", "finance_officer")
def delete_insured_person(request, person_id):
    person = get_object_or_404(InsuredPerson, id=person_id)
    policy_id = person.policy.id
    if request.method == "POST":
        person.delete()
        messages.success(request, f"{person.full_name} removed successfully.")
    return redirect("policies:policy_detail", pk=policy_id)
