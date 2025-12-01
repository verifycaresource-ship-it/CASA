import base64
import uuid
from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import viewsets, permissions
import io
import requests
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from django.contrib.auth.decorators import login_required
from .models import Policy
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
from django.db.models.functions import TruncMonth

from datetime import date, timedelta, datetime

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator

from accounts.decorators import roles_required
from .models import Policy

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
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.core.paginator import Paginator

from accounts.decorators import roles_required
from .models import Policy


# -------------------------------------------------------------------
# POLICY LIST + FILTERS + DASHBOARD ANALYTICS
# -------------------------------------------------------------------

@login_required
@roles_required("admin", "finance_officer")
def policy_list(request):

    today = date.today()

    # -------------------------------------------------------
    # BASE QUERY
    # -------------------------------------------------------
    policies = (
        Policy.objects
        .select_related("client")
        .order_by("-start_date")
    )

    # -------------------------------------------------------
    # FILTERS
    # -------------------------------------------------------
    search = request.GET.get("search", "").strip()
    policy_type = request.GET.get("type", "")
    active = request.GET.get("active", "")
    month_only = request.GET.get("monthly", "")
    start_date = request.GET.get("start", "")
    end_date = request.GET.get("end", "")

    # ---- SEARCH (Policy No + Client Names) ----
    if search:
        policies = policies.filter(
            Q(policy_number__icontains=search) |
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search)
        )

    # ---- POLICY TYPE ----
    if policy_type:
        policies = policies.filter(policy_type=policy_type)

    # ---- ACTIVE FILTER ----
    if active == "true":
        policies = policies.filter(is_active=True)
    elif active == "false":
        policies = policies.filter(is_active=False)

    # ---- DATE RANGE FILTER ----
    try:
        if start_date:
            policies = policies.filter(
                start_date__gte=datetime.strptime(start_date, "%Y-%m-%d").date()
            )

        if end_date:
            policies = policies.filter(
                start_date__lte=datetime.strptime(end_date, "%Y-%m-%d").date()
            )
    except ValueError:
        pass   # ignore invalid date input safely

    # ---- CURRENT MONTH FILTER ----
    if month_only:
        policies = policies.filter(
            start_date__year=today.year,
            start_date__month=today.month
        )

    # -------------------------------------------------------
    # KPI METRICS
    # -------------------------------------------------------
    total_count = Policy.objects.count()
    active_count = Policy.objects.filter(is_active=True).count()

    monthly_count = Policy.objects.filter(
        start_date__year=today.year,
        start_date__month=today.month
    ).count()

    total_revenue = (
        Policy.objects.aggregate(total=Sum("premium"))["total"] or 0
    )

    monthly_revenue = (
        Policy.objects.filter(
            start_date__year=today.year,
            start_date__month=today.month
        )
        .aggregate(total=Sum("premium"))["total"] or 0
    )

    # -------------------------------------------------------
    # RENEWAL + EXPIRY ALERTS
    # -------------------------------------------------------
    renewals = (
        Policy.objects
        .filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=30)
        )
        .order_by("expiry_date")
    )

    expired_alerts = (
        Policy.objects
        .filter(expiry_date__lt=today)
        .order_by("-expiry_date")[:10]
    )

    # -------------------------------------------------------
    # MONTHLY ANALYTICS (Charts)
    # -------------------------------------------------------
    monthly_sales = (
        Policy.objects
        .annotate(month=TruncMonth("start_date"))
        .values("month")
        .annotate(
            count=Count("id"),
            revenue=Sum("premium")
        )
        .order_by("month")
    )

    chart_labels = [
        record["month"].strftime("%b %Y")
        for record in monthly_sales
    ]

    chart_counts = [
        record["count"]
        for record in monthly_sales
    ]

    chart_revenue = [
        float(record["revenue"] or 0)
        for record in monthly_sales
    ]

    # -------------------------------------------------------
    # PAGINATION
    # -------------------------------------------------------
    paginator = Paginator(policies, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # -------------------------------------------------------
    # TEMPLATE CONTEXT
    # -------------------------------------------------------
    context = {
        "policies": page_obj.object_list,
        "page_obj": page_obj,

        # Search & Filters
        "search": search,
        "policy_type": policy_type,
        "active": active,
        "start": start_date,
        "end": end_date,

        # KPI Summary
        "total_count": total_count,
        "active_count": active_count,
        "monthly_count": monthly_count,
        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,

        # Renewal Alerts
        "renewals": renewals,
        "expired_alerts": expired_alerts,

        # Charts
        "chart_labels": chart_labels,
        "chart_counts": chart_counts,
        "chart_revenue": chart_revenue,

        # Metadata
        "dashboard_title": "Policy Analytics",
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


@login_required
def view_policy_pdf(request, pk):
    # Get the policy and insured persons
    policy = get_object_or_404(Policy, pk=pk)
    insured_persons = policy.insured_persons.all()

    # Render HTML
    html_string = render_to_string("policies/policy_pdf.html", {
        "policy": policy,
        "insured_persons": insured_persons,
    })

    # Convert HTML to PDF
    pdf_file = HTML(string=html_string).write_pdf()

    # --- Add seal (same logic as download) ---
    seal_url = "https://res.cloudinary.com/dzflw2ka9/image/upload/v1764246165/casaseal_mrw3dw.png"
    seal_img = Image.open(io.BytesIO(requests.get(seal_url).content))

    seal_pdf_stream = io.BytesIO()
    c = canvas.Canvas(seal_pdf_stream, pagesize=letter)

    seal_width = 100
    seal_height = 100
    

    page_width, page_height = letter
    x = (page_width - seal_width) / 2
    y = 40  # bottom

    c.drawImage(ImageReader(seal_img), x, y, width=seal_width, height=seal_height, mask='auto')
    c.save()
    seal_pdf_stream.seek(0)

    reader = PdfReader(io.BytesIO(pdf_file))
    seal_reader = PdfReader(seal_pdf_stream)

    writer = PdfWriter()
    seal_page = seal_reader.pages[0]

    total_pages = len(reader.pages)

    for i, page in enumerate(reader.pages):
        if i == total_pages - 1:
            page.merge_page(seal_page)
        writer.add_page(page)

    final_pdf_stream = io.BytesIO()
    writer.write(final_pdf_stream)
    final_pdf_stream.seek(0)

    # 👉 IMPORTANT: View inline (no download)
    response = HttpResponse(final_pdf_stream.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Policy_{policy.policy_number}.pdf"'

    return response
