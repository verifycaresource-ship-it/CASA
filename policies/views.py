import base64
import uuid
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import viewsets, permissions

from .models import Policy, InsuredPerson, PAYMENT_MODE_CHOICES, COVERAGE_LEVEL_CHOICES
from .serializers import PolicySerializer
from clients.models import Client
from accounts.utils import roles_required
from hospitals.models import HospitalAssignment, Hospital
from claims.models import Claim
from .models import Policy, InsuredPerson, PAYMENT_MODE_CHOICES, COVERAGE_LEVEL_CHOICES, GENDER_CHOICES

from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
import requests
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader

# -------------------------------------------------------------------
# DRF API VIEW
# -------------------------------------------------------------------
class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [permissions.IsAuthenticated]


# -------------------------------------------------------------------
# POLICY LIST
# -------------------------------------------------------------------
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


# -------------------------------------------------------------------
# ADD / EDIT POLICY (WITH INSURED PERSONS)
# -------------------------------------------------------------------
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
        if not all(data.get(f) for f in required_fields):
            messages.error(request, "Please fill in all required fields.")
            return redirect(request.path)

        try:
            # ---------------- Update or Create Policy ----------------
            if policy:
                policy.client = client
                policy.policy_number = policy_number
                policy.policy_type = data.get("policy_type")
                policy.payment_mode = data.get("payment_mode")
                policy.coverage_level = data.get("coverage_level")
                policy.nric_or_passport = data.get("nric_or_passport")
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
                policy = Policy.objects.create(
                    client=client,
                    policy_number=policy_number,
                    policy_type=data.get("policy_type"),
                    payment_mode=data.get("payment_mode"),
                    coverage_level=data.get("coverage_level"),
                    nric_or_passport=data.get("nric_or_passport"),
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

            # ---------------- Insured Persons ----------------
            full_names = data.getlist("insured_full_name[]")
            relationships = data.getlist("insured_relationship[]")
            dobs = data.getlist("insured_dob[]")
            genders = data.getlist("insured_gender[]")
            photos = files.getlist("insured_photo[]")
            insured_ids = data.getlist("insured_id[]")

            for i in range(len(full_names)):
                name = full_names[i].strip()
                relationship = relationships[i].strip()
                if not name or not relationship:
                    continue

                dob_value = None
                if dobs[i]:
                    try:
                        dob_value = datetime.strptime(dobs[i], "%Y-%m-%d").date()
                    except ValueError:
                        pass

                gender = genders[i] if i < len(genders) else None
                photo = photos[i] if i < len(photos) else None
                insured_id = insured_ids[i] if i < len(insured_ids) else None

                # Update existing person
                if insured_id:
                    person = InsuredPerson.objects.filter(id=insured_id, policy=policy).first()
                    if person:
                        person.full_name = name
                        person.relationship = relationship
                        person.gender = gender or person.gender
                        if dob_value:
                            person.dob = dob_value
                        if photo:
                            person.photo = photo
                        person.save()
                        continue

                # Create new person
                new_person = InsuredPerson.objects.create(
                    policy=policy,
                    full_name=name,
                    relationship=relationship,
                    dob=dob_value,
                    gender=gender,
                    photo=photo,
                )

                # Save fingerprint if adult
                fingerprint_base64 = data.get(f"fingerprint_base64_{i}")
                if new_person.is_adult and fingerprint_base64:
                    new_person.fingerprint_data = base64.b64decode(fingerprint_base64)
                    new_person.fingerprint_verified = True
                    new_person.save()

            return redirect("policies:policy_detail", pk=policy.pk)

        except IntegrityError:
            messages.error(request, "Policy number already exists.")

    return render(request, "policies/policy_form.html", {
        "policy": policy,
        "clients": clients,
        "policy_types": Policy.POLICY_TYPE,
        "payment_modes": PAYMENT_MODE_CHOICES,
        "coverage_levels": COVERAGE_LEVEL_CHOICES,
        "dashboard_title": "Edit Policy" if policy else "Add New Policy",
        "role": getattr(request.user, "role", "guest"),
        "auto_policy_number": auto_policy_number,
        "today": today,
        "next_year": next_year,
        "GENDER_CHOICES": GENDER_CHOICES,   # <-- add here

    })


# -------------------------------------------------------------------
# POLICY DETAIL
# -------------------------------------------------------------------
@login_required
@roles_required("admin", "finance_officer", "hospital")
def policy_detail(request, pk):
    policy = get_object_or_404(Policy, pk=pk)
    assigned_clients = policy.hospital_assignments.select_related(
        "client", "hospital", "assigned_by"
    )
    insured_persons = policy.insured_persons.all()

    return render(request, "policies/policy_detail.html", {
        "policy": policy,
        "assigned_clients": assigned_clients,
        "insured_persons": insured_persons,
    })


# -------------------------------------------------------------------
# ASSIGN POLICY TO HOSPITAL
# -------------------------------------------------------------------
@login_required
@roles_required("admin", "finance_officer")
def assign_to_hospital(request, pk):
    policy = get_object_or_404(Policy, pk=pk)
    hospitals = Hospital.objects.filter(verified=True)

    if request.method == "POST":
        hospital = get_object_or_404(Hospital, id=request.POST.get("hospital"))
        assignment, created = HospitalAssignment.objects.get_or_create(
            client=policy.client,
            policy=policy,
            hospital=hospital,
            defaults={"assigned_by": request.user}
        )
        if created:
            messages.success(request, f"{policy.client} assigned to {hospital.name}.")
        else:
            messages.info(request, f"{policy.client} is already assigned to {hospital.name}.")

        return redirect("policies:policy_detail", pk=policy.pk)

    return render(request, "policies/assign_hospital.html", {
        "policy": policy,
        "hospitals": hospitals,
        "dashboard_title": f"Assign Hospital for {policy.policy_number}",
    })


# -------------------------------------------------------------------
# ADD INSURED PERSON
# -------------------------------------------------------------------
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
                pass

        if full_name and relationship and dob_value:
            person = policy.insured_persons.create(
                full_name=full_name.strip(),
                relationship=relationship.strip(),
                dob=dob_value,
                gender=gender if gender else None,
                photo=photo,
            )
            if person.is_adult and fingerprint_base64:
                person.fingerprint_data = base64.b64decode(fingerprint_base64)
                person.fingerprint_verified = True
                person.save()
            messages.success(request, f"{full_name} added to policy {policy.policy_number}.")
            return redirect("policies:policy_detail", pk=policy.id)

        messages.error(request, "Full name, relationship and valid DOB are required.")

    return render(request, "policies/add_insured_person.html", {"policy": policy})


# -------------------------------------------------------------------
# EDIT INSURED PERSON
# -------------------------------------------------------------------
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
                messages.warning(request, "Invalid date format.")
        if gender:
            person.gender = gender
        if request.FILES.get("photo"):
            person.photo = request.FILES.get("photo")

        person.save()
        messages.success(request, "Insured person updated successfully.")
        return redirect("policies:policy_detail", pk=policy.id)

    return render(request, "policies/edit_insured_person.html", {
        "person": person,
        "policy": policy,
    })


# -------------------------------------------------------------------
# DELETE INSURED PERSON
# -------------------------------------------------------------------
@login_required
@roles_required("admin", "finance_officer")
def delete_insured_person(request, person_id):
    person = get_object_or_404(InsuredPerson, id=person_id)
    policy_id = person.policy.id
    if request.method == "POST":
        person.delete()
        messages.success(request, "Insured person removed.")
    return redirect("policies:policy_detail", pk=policy_id)

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from .models import Policy

@login_required
def download_policy_pdf(request, pk):
    # Get the policy and insured persons
    policy = get_object_or_404(Policy, pk=pk)
    insured_persons = policy.insured_persons.all()

    # Render HTML
    html_string = render_to_string("policies/policy_pdf.html", {
        "policy": policy,
        "insured_persons": insured_persons,
    })

    # Convert HTML to PDF (WeasyPrint)
    pdf_file = HTML(string=html_string).write_pdf()

    # ---------------------------------------------------------------------
    # 1️⃣ Create a temporary PDF containing only the seal image
    # ---------------------------------------------------------------------
    seal_url = "https://res.cloudinary.com/dzflw2ka9/image/upload/v1764246165/casaseal_mrw3dw.png"

    # Download seal image
    seal_img = Image.open(io.BytesIO(requests.get(seal_url).content))
    seal_img_io = io.BytesIO()
    seal_img.save(seal_img_io, format="PNG")

    # Create temporary PDF with reportlab
    seal_pdf_stream = io.BytesIO()
    c = canvas.Canvas(seal_pdf_stream, pagesize=letter)

    # Seal position (bottom center)
    seal_width = 150
    seal_height = 150

    page_width, page_height = letter
    x = (page_width - seal_width) / 2
    y = 40  # bottom

    c.drawImage(ImageReader(seal_img), x, y, width=seal_width, height=seal_height, mask='auto')
    c.save()
    seal_pdf_stream.seek(0)

    # ---------------------------------------------------------------------
    # 2️⃣ Merge seal ONLY into last page
    # ---------------------------------------------------------------------
    reader = PdfReader(io.BytesIO(pdf_file))
    seal_reader = PdfReader(seal_pdf_stream)

    writer = PdfWriter()
    seal_page = seal_reader.pages[0]

    total_pages = len(reader.pages)

    for i, page in enumerate(reader.pages):
        if i == total_pages - 1:  # LAST PAGE
            page.merge_page(seal_page)
        writer.add_page(page)

    # Output final PDF
    final_pdf_stream = io.BytesIO()
    writer.write(final_pdf_stream)
    final_pdf_stream.seek(0)

    response = HttpResponse(final_pdf_stream.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Policy_{policy.policy_number}.pdf"'

    return response

from django.shortcuts import render, get_object_or_404
from .models import Policy

@login_required
def view_policy_document(request, pk):
    policy = get_object_or_404(Policy, pk=pk)
    insured_persons = policy.insured_persons.all()  # use related_name from your model

    return render(request, "policies/policy_document.html", {
        "policy": policy,
        "insured_persons": insured_persons,
        "user": request.user,
    })
