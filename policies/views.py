# ---------------------------
# PYTHON STANDARD LIBRARY
# ---------------------------
import uuid
import io
import csv
import base64
from datetime import date, datetime, timedelta
from .models import Client
# ---------------------------
# DJANGO CORE
# ---------------------------
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Q, Count, Sum
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET

# ---------------------------
# THIRD-PARTY LIBRARIES
# ---------------------------
from rest_framework import viewsets, permissions
from weasyprint import HTML
from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
import requests

# ---------------------------
# LOCAL / APP IMPORTS
# ---------------------------
from .models import (
    Policy,
    InsuredPerson,
    PolicyAudit,
    PAYMENT_MODE_CHOICES,
    COVERAGE_LEVEL_CHOICES,
    GENDER_CHOICES,
)
from .serializers import PolicySerializer
from .decorators import roles_required

from clients.models import Client
from hospitals.models import HospitalAssignment, Hospital
from claims.models import Claim


# -------------------------------------------------------------------
# DRF API VIEW
# -------------------------------------------------------------------
class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [permissions.IsAuthenticated]


# -------------------------------------------------------------------
# POLICY LIST + FILTERS + DASHBOARD ANALYTICS
# -------------------------------------------------------------------

from datetime import date, timedelta, datetime
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncMonth

from .models import Policy
from clients.models import Client  # Make sure your Client model is imported
# from users.decorators import roles_required  # Your custom role decorator

@login_required
@roles_required("admin", "finance_officer")
def policy_list(request):
    today = date.today()

    # -------------------------------
    # BASE QUERY
    # -------------------------------
    policies = Policy.objects.select_related("client").order_by("-start_date")

    # -------------------------------
    # FILTERS
    # -------------------------------
    search = request.GET.get("search", "").strip()
    policy_type = request.GET.get("type", "")
    active = request.GET.get("active", "")
    month_only = request.GET.get("monthly", "")
    start_date = request.GET.get("start", "")
    end_date = request.GET.get("end", "")

    if search:
        policies = policies.filter(
            Q(policy_number__icontains=search) |
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search)
        )

    if policy_type:
        policies = policies.filter(policy_type=policy_type)

    if active == "true":
        policies = policies.filter(is_active=True)
    elif active == "false":
        policies = policies.filter(is_active=False)

    try:
        if start_date:
            policies = policies.filter(start_date__gte=datetime.strptime(start_date, "%Y-%m-%d").date())
        if end_date:
            policies = policies.filter(start_date__lte=datetime.strptime(end_date, "%Y-%m-%d").date())
    except ValueError:
        pass

    if month_only:
        policies = policies.filter(start_date__year=today.year, start_date__month=today.month)

    # -------------------------------
    # KPI METRICS
    # -------------------------------
    total_count = Policy.objects.count()
    active_count = Policy.objects.filter(is_active=True).count()
    monthly_count = Policy.objects.filter(start_date__year=today.year, start_date__month=today.month).count()
    total_revenue = Policy.objects.aggregate(total=Sum("premium"))["total"] or 0
    monthly_revenue = Policy.objects.filter(start_date__year=today.year, start_date__month=today.month).aggregate(total=Sum("premium"))["total"] or 0

    # -------------------------------
    # RENEWAL + EXPIRY ALERTS
    # -------------------------------
    renewals = Policy.objects.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).order_by("expiry_date")
    expired_alerts = Policy.objects.filter(expiry_date__lt=today).order_by("-expiry_date")[:10]

    # -------------------------------
    # MONTHLY ANALYTICS
    # -------------------------------
    monthly_sales = Policy.objects.annotate(month=TruncMonth("start_date")).values("month").annotate(
        count=Count("id"),
        revenue=Sum("premium")
    ).order_by("month")

    chart_labels = [record["month"].strftime("%b %Y") for record in monthly_sales]
    chart_counts = [record["count"] for record in monthly_sales]
    chart_revenue = [float(record["revenue"] or 0) for record in monthly_sales]

    # -------------------------------
    # CLIENTS FOR ADD POLICY MODAL
    # -------------------------------
    clients = Client.objects.filter(is_active=True).order_by("first_name", "last_name")

    # -------------------------------
    # PAGINATION
    # -------------------------------
    paginator = Paginator(policies, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # -------------------------------
    # TEMPLATE CONTEXT
    # -------------------------------
    context = {
        "policies": page_obj.object_list,
        "page_obj": page_obj,

        # Filters
        "search": search,
        "policy_type": policy_type,
        "active": active,
        "start": start_date,
        "end": end_date,

        # KPI
        "total_count": total_count,
        "active_count": active_count,
        "monthly_count": monthly_count,
        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,

        # Alerts
        "renewals": renewals,
        "expired_alerts": expired_alerts,

        # Charts
        "chart_labels": chart_labels,
        "chart_counts": chart_counts,
        "chart_revenue": chart_revenue,

        # Clients for modal
        "clients": clients,

        # Metadata
        "dashboard_title": "Policy Analytics",
        "role": getattr(request.user, "role", "guest"),
    }

    return render(request, "policies/policy_list.html", context)







@login_required
@roles_required("admin", "finance_officer", "hospital")
def policy_detail(request, pk):
    policy = get_object_or_404(Policy, pk=pk)

    assigned_clients = policy.hospital_assignments.select_related(
        "client", "hospital", "assigned_by"
    )

    insured_persons = policy.insured_persons.all()

    # 🔴 NEW: fetch claims linked to this policy
    claims = Claim.objects.select_related(
        "client", "hospital"
    ).filter(policy=policy).order_by("-created_at")

    return render(request, "policies/policy_detail.html", {
        "policy": policy,
        "assigned_clients": assigned_clients,
        "insured_persons": insured_persons,
        "claims": claims,  # 👈 IMPORTANT
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
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from .models import Policy

@login_required
@roles_required("admin", "finance_officer")
@require_GET
def verify_policy(request):
    """
    AJAX endpoint to verify a policy number.
    Returns JSON with policy and client info.
    """
    number = request.GET.get("number", "").strip()
    if not number:
        return JsonResponse({"error": "Policy number is required."}, status=400)

    try:
        policy = Policy.objects.select_related("client").get(policy_number=number)
    except Policy.DoesNotExist:
        return JsonResponse({"error": f"No policy found with number {number}."}, status=404)

    client = policy.client
    today = timezone.now().date()
    days_left = (policy.expiry_date - today).days if policy.expiry_date else 0

    data = {
        "id": policy.id,
        "client_name": f"{client.first_name} {client.last_name}",
        "policy_number": policy.policy_number,
        "policy_type": policy.policy_type,
        "coverage_level": policy.coverage_level,
        "coverage": policy.coverage_details or "",
        "nric_passport": client.nric_or_passport or "",
        "nric_passport": policy.nric_or_passport or "Not provided",  # <-- use policy field

        "premium": float(policy.premium or 0),
        "payment_mode": policy.payment_mode or "",
        "start_date": policy.start_date.strftime("%Y-%m-%d") if policy.start_date else "",
        "expiry_date": policy.expiry_date.strftime("%Y-%m-%d") if policy.expiry_date else "",
        "status": "Active" if policy.is_active else "Inactive",
        "days_left": days_left,
        "client_url": f"/clients/{client.id}/detail/",  # adjust your client detail URL
    }
    return JsonResponse(data)

# -------------------------------------------------------------------
# DRF API VIEW
# -------------------------------------------------------------------
class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [permissions.IsAuthenticated]

# -------------------------------------------------------------------
# POLICY LIST + FILTERS + DASHBOARD ANALYTICS
# -------------------------------------------------------------------




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


@login_required
@roles_required("admin", "finance_officer")
@require_GET
def verify_policy(request):
    """
    AJAX endpoint to verify a policy number.
    Returns JSON with policy and client info.
    """
    number = request.GET.get("number", "").strip()
    if not number:
        return JsonResponse({"error": "Policy number is required."}, status=400)

    try:
        policy = Policy.objects.select_related("client").get(policy_number=number)
    except Policy.DoesNotExist:
        return JsonResponse({"error": f"No policy found with number {number}."}, status=404)

    client = policy.client
    today = timezone.now().date()
    days_left = (policy.expiry_date - today).days if policy.expiry_date else 0

    data = {
        "id": policy.id,
        "client_name": f"{client.first_name} {client.last_name}",
        "policy_number": policy.policy_number,
        "policy_type": policy.policy_type,
        "coverage_level": policy.coverage_level,
        "coverage": policy.coverage_details or "",
        "nric_passport": client.nric_or_passport or "",
        "nric_passport": policy.nric_or_passport or "Not provided",  # <-- use policy field

        "premium": float(policy.premium or 0),
        "payment_mode": policy.payment_mode or "",
        "start_date": policy.start_date.strftime("%Y-%m-%d") if policy.start_date else "",
        "expiry_date": policy.expiry_date.strftime("%Y-%m-%d") if policy.expiry_date else "",
        "status": "Active" if policy.is_active else "Inactive",
        "days_left": days_left,
        "client_url": f"/clients/{client.id}/detail/",  # adjust your client detail URL
    }
    return JsonResponse(data)


# -------------------------------------------------------------------
# DRF API VIEW
# -------------------------------------------------------------------
class PolicyViewSet(viewsets.ModelViewSet):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer
    permission_classes = [permissions.IsAuthenticated]


@login_required
@roles_required("admin", "finance_officer")
def policy_form(request, pk=None, client_id=None):
    policy = get_object_or_404(Policy, pk=pk) if pk else None
    clients = Client.objects.all().order_by("first_name", "last_name")
    auto_policy_number = policy.policy_number if policy else f"POL-{uuid.uuid4().hex[:8].upper()}"
    today = timezone.now().date()
    next_year = today.replace(year=today.year + 1)

    # Preselect client if client_id is passed
    selected_client = None
    if client_id:
        selected_client = get_object_or_404(Client, pk=client_id)

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
            if policy:
                # Update existing
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
                # Create new
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
            # (keep your existing logic here unchanged)
            # ...

            return redirect("policies:policy_detail", pk=policy.pk)

        except IntegrityError:
            messages.error(request, "Policy number already exists.")

    return render(request, "policies/policy_form.html", {
        "policy": policy,
        "clients": clients,
        "selected_client": selected_client,
        "policy_types": Policy.POLICY_TYPE,
        "payment_modes": PAYMENT_MODE_CHOICES,
        "coverage_levels": COVERAGE_LEVEL_CHOICES,
        "dashboard_title": "Edit Policy" if policy else "Add New Policy",
        "role": getattr(request.user, "role", "guest"),
        "auto_policy_number": auto_policy_number,
        "today": today,
        "next_year": next_year,
        "GENDER_CHOICES": GENDER_CHOICES,
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
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime, date
import base64

from .models import Policy, InsuredPerson
from .decorators import roles_required


@login_required
@roles_required("admin", "finance_officer")
def add_insured_person(request, policy_id):
    """
    Matches insuredPersonsForm Alpine template EXACTLY
    """
    policy = get_object_or_404(Policy, id=policy_id)

    if request.method == "POST":
        index = 0
        saved_count = 0

        while f"full_name_{index}" in request.POST:
            full_name = request.POST.get(f"full_name_{index}", "").strip()
            relationship = request.POST.get(f"relationship_{index}", "").strip()
            dob_str = request.POST.get(f"dob_{index}")
            gender = request.POST.get(f"gender_{index}")
            fingerprint_base64 = request.POST.get(f"fingerprint_base64_{index}")
            photo = request.FILES.get(f"photo_{index}")

            # --- Validate ---
            if not full_name or not relationship or not dob_str:
                index += 1
                continue

            try:
                dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                index += 1
                continue

            # --- Create insured person ---
            person = InsuredPerson.objects.create(
                policy=policy,
                full_name=full_name,
                relationship=relationship,
                dob=dob,
                gender=gender if gender else None,
                photo=photo,
            )

            # --- Adult check ---
            today = date.today()
            age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )

            if age >= 18 and fingerprint_base64:
                try:
                    person.fingerprint_data = base64.b64decode(fingerprint_base64)
                    person.fingerprint_verified = True
                    person.save()
                except Exception:
                    pass  # fingerprint optional

            saved_count += 1
            index += 1

        messages.success(
            request,
            f"{saved_count} insured person(s) added to policy {policy.policy_number}."
        )

        return redirect("policies:policy_detail", pk=policy.id)

    return render(request, "policies/add_insured_person.html", {
        "policy": policy,
    })

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

@login_required
@roles_required("admin", "finance_officer")
@require_GET
def verify_policy(request):
    """
    AJAX endpoint to verify a policy number.
    Returns JSON with policy and client info.
    """
    number = request.GET.get("number", "").strip()
    if not number:
        return JsonResponse({"error": "Policy number is required."}, status=400)

    try:
        policy = Policy.objects.select_related("client").get(policy_number=number)
    except Policy.DoesNotExist:
        return JsonResponse({"error": f"No policy found with number {number}."}, status=404)

    client = policy.client
    today = timezone.now().date()
    days_left = (policy.expiry_date - today).days if policy.expiry_date else 0

    data = {
        "id": policy.id,
        "client_name": f"{client.first_name} {client.last_name}",
        "policy_number": policy.policy_number,
        "policy_type": policy.policy_type,
        "coverage_level": policy.coverage_level,
        "coverage": policy.coverage_details or "",
        "nric_passport": client.nric_or_passport or "",
        "nric_passport": policy.nric_or_passport or "Not provided",  # <-- use policy field

        "premium": float(policy.premium or 0),
        "payment_mode": policy.payment_mode or "",
        "start_date": policy.start_date.strftime("%Y-%m-%d") if policy.start_date else "",
        "expiry_date": policy.expiry_date.strftime("%Y-%m-%d") if policy.expiry_date else "",
        "status": "Active" if policy.is_active else "Inactive",
        "days_left": days_left,
        "client_url": f"/clients/{client.id}/detail/",  # adjust your client detail URL
    }
    return JsonResponse(data)

# ---------------------------
# ARCHIVED POLICIES LIST
# ---------------------------
@login_required
@roles_required("admin", "finance_officer")
def archived_policies(request):
    """
    Show archived/expired policies with optional search by policy number or client name.
    """
    search = request.GET.get("search", "").strip()
    policies = Policy.objects.select_related("client").filter(is_archived=True).order_by("-updated_at")

    if search:
        policies = policies.filter(
            Q(policy_number__icontains=search) |
            Q(client__first_name__icontains=search) |
            Q(client__last_name__icontains=search)
        )

    context = {
        "policies": policies,
        "search": search,
        "dashboard_title": "Archived Policies",
    }
    return render(request, "policies/archived_list.html", context)


# ---------------------------
# RENEW POLICY
# ---------------------------

@login_required
def renew_policy(request, pk):
    """Renew a policy — must archive first if expired/inactive."""
    old_policy = get_object_or_404(Policy, pk=pk)

    # Check if policy is active or expired
    if not old_policy.is_active or old_policy.is_expired:
        # Archive first
        old_policy.is_archived = True
        old_policy.is_active = False
        old_policy.save()

        PolicyAudit.objects.create(
            policy=old_policy,
            action="archived_before_renew",
            performed_by=request.user
        )
    else:
        messages.warning(request, "Policy is still active; archiving not required.")

    # Create a new policy
    today = timezone.now().date()
    next_year = today.replace(year=today.year + 1)
    
    new_policy = Policy.objects.create(
        client=old_policy.client,
        policy_number=f"POL-{uuid.uuid4().hex[:8].upper()}",
        policy_type=old_policy.policy_type,
        payment_mode=old_policy.payment_mode,
        coverage_level=old_policy.coverage_level,
        nric_or_passport=old_policy.nric_or_passport,
        start_date=today,
        expiry_date=next_year,
        premium=old_policy.premium,
        is_active=True,
        coverage_details=old_policy.coverage_details,
        max_claim_limit=old_policy.max_claim_limit,
        waiting_period_days=old_policy.waiting_period_days,
        created_by=request.user,
    )

    # Copy insured persons
    for person in old_policy.insured_persons.all():
        InsuredPerson.objects.create(
            policy=new_policy,
            full_name=person.full_name,
            relationship=person.relationship,
            dob=person.dob,
            gender=person.gender,
            photo=person.photo,
            fingerprint_data=person.fingerprint_data,
            fingerprint_verified=person.fingerprint_verified
        )

    messages.success(
        request,
        f"Policy {old_policy.policy_number} archived and renewed as {new_policy.policy_number}."
    )
    return redirect("policies:policy_detail", pk=new_policy.pk)

# ---------------------------
# UNDO ARCHIVE
# ---------------------------
@login_required
@roles_required("admin", "finance_officer")
def undo_archive_policy(request, pk):
    """
    Restore an archived policy.
    """
    policy = get_object_or_404(Policy, pk=pk)
    policy.is_archived = False
    policy.is_active = True
    policy.save()

    PolicyAudit.objects.create(
        policy=policy,
        action="undo_archive",
        performed_by=request.user
    )

    messages.success(request, "Policy restored successfully.")
    return redirect("policies:archived_policies")

# ---------------------------
# EXPORT ARCHIVED CSV
# ---------------------------
@login_required
@roles_required("admin", "finance_officer")
def export_archived_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="archived_policies.csv"'

    writer = csv.writer(response)
    writer.writerow(["Policy", "Client", "Premium", "Expiry", "Archived At"])

    for p in Policy.objects.filter(is_archived=True):
        writer.writerow([p.policy_number, str(p.client), p.premium, p.expiry_date, p.updated_at])

    return response

# ---------------------------
# EXPORT ARCHIVED PDF
# ---------------------------
@login_required
@roles_required("admin", "finance_officer")
def export_archived_pdf(request):
    """
    Export all archived policies to a PDF with full information.
    """
    # Get all archived policies
    policies = Policy.objects.filter(is_archived=True).select_related("client").prefetch_related("insured_persons")

    # Render HTML template for PDF
    html = render_to_string("policies/archived_pdf.html", {
        "policies": policies,
    })

    # Convert HTML to PDF
    pdf_file = HTML(string=html).write_pdf()

    # Return as PDF response
    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="archived_policies_full.pdf"'
    return response

@login_required
def archive_policy(request, pk):
    policy = get_object_or_404(Policy, pk=pk)
    policy.is_archived = True
    policy.is_active = False
    policy.save()

    # Optional audit
    PolicyAudit.objects.create(
        policy=policy,
        action="archive",
        performed_by=request.user
    )

    messages.success(request, f"Policy {policy.policy_number} archived successfully.")
    return redirect("policies:policy_list")  # Adjust redirect as needed
@login_required
@roles_required("admin", "finance_officer")
def policy_form(request, pk=None):
    """
    Add or edit a policy. If 'client' GET parameter is present, preselect the client.
    """
    policy = get_object_or_404(Policy, pk=pk) if pk else None

    # All clients for dropdown
    clients = Client.objects.all()

    # Check if client is pre-selected (from modal)
    client_id = request.GET.get("client")
    selected_client = None
    if client_id:
        selected_client = Client.objects.filter(pk=client_id).first()
    elif policy:
        selected_client = policy.client

    auto_policy_number = policy.policy_number if policy else f"POL-{uuid.uuid4().hex[:8].upper()}"
    today = timezone.now().date()
    next_year = today.replace(year=today.year + 1)

    if request.method == "POST":
        data = request.POST
        files = request.FILES

        # Ensure client is selected
        client = get_object_or_404(Client, pk=data.get("client"))
        policy_number = data.get("policy_number") or auto_policy_number

        # Validate required fields
        required_fields = ["policy_type", "start_date", "expiry_date", "premium"]
        if not all(data.get(f) for f in required_fields):
            messages.error(request, "Please fill in all required fields.")
            return redirect(request.path)

        try:
            if policy:
                # Update existing
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
                # Create new
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

            return redirect("policies:policy_detail", pk=policy.pk)

        except IntegrityError:
            messages.error(request, "Policy number already exists.")

    return render(request, "policies/policy_form.html", {
        "policy": policy,
        "clients": clients,
        "selected_client": selected_client,  # <-- this is new
        "policy_types": Policy.POLICY_TYPE,
        "payment_modes": PAYMENT_MODE_CHOICES,
        "coverage_levels": COVERAGE_LEVEL_CHOICES,
        "dashboard_title": "Edit Policy" if policy else "Add New Policy",
        "auto_policy_number": auto_policy_number,
        "today": today,
        "next_year": next_year,
        "GENDER_CHOICES": GENDER_CHOICES,
    })



@login_required
@roles_required("admin", "finance_officer")
def add_policy_redirect(request):
    client_id = request.GET.get("client")
    if client_id:
        return redirect('policies:add_policy') + f"?client={client_id}"
    messages.error(request, "Please select a client first.")
    return redirect('policies:policy_list')
