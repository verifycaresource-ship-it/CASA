# clients/views.py

import base64
import os
import calendar
import io

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import ExtractMonth
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets
import qrcode

from .models import Client, ClientVerificationToken
from .forms import ClientForm
from .decorators import roles_required
from .fingerprint_service import enroll_client_from_base64
from policies.models import Policy
from .serializers import ClientSerializer

User = get_user_model()

# ======================================================
# CLIENT DASHBOARD / LIST
# ======================================================
@login_required
@roles_required("admin", "agent")
def client_list(request):
    search_query = request.GET.get("search", "")
    gender_filter = request.GET.get("gender", "")
    agent_filter = request.GET.get("agent", "")
    status_filter = request.GET.get("status", "")

    clients = Client.objects.all()

    if search_query:
        clients = clients.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    if gender_filter:
        clients = clients.filter(gender=gender_filter)

    if agent_filter:
        clients = clients.filter(registered_by__id=agent_filter)

    if status_filter:
        clients = clients.filter(status=status_filter)

    paginator = Paginator(clients.order_by("-id"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    total_clients = Client.objects.count()
    verified_clients = Client.objects.filter(status="verified").count()
    pending_clients = Client.objects.filter(status="pending").count()
    failed_clients = Client.objects.filter(status="failed").count()

    male_clients = Client.objects.filter(gender="male").count()
    female_clients = Client.objects.filter(gender="female").count()
    other_clients = Client.objects.filter(gender="other").count()

    month_data_qs = Client.objects.annotate(
        month=ExtractMonth("created_at")
    ).values("month").annotate(count=Count("id")).order_by("month")

    months = [calendar.month_name[m["month"]] for m in month_data_qs]
    month_data = [m["count"] for m in month_data_qs]

    agents = User.objects.filter(role="agent")

    context = {
        "clients": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "gender_filter": gender_filter,
        "agent_filter": agent_filter,
        "status_filter": status_filter,
        "total_clients": total_clients,
        "verified_clients": verified_clients,
        "pending_clients": pending_clients,
        "failed_clients": failed_clients,
        "male_clients": male_clients,
        "female_clients": female_clients,
        "other_clients": other_clients,
        "months": months,
        "month_data": month_data,
        "agents": agents,
    }
    return render(request, "clients/client_list.html", context)

# ======================================================
# ADD / EDIT CLIENT HELPER
# ======================================================
def save_client_form(request, form, client=None):
    if form.is_valid():
        client = form.save(commit=False)

        fingerprint_base64 = request.POST.get("fingerprint_base64")
        if fingerprint_base64:
            try:
                enroll_client_from_base64(client, fingerprint_base64)
                client.status = "verified"
                client.fingerprint_verified = True
            except Exception as e:
                client.status = "failed"
                messages.warning(request, f"Fingerprint enrollment failed: {e}")
        else:
            if not client.pk:
                client.status = "pending"

        if not client.pk:
            client.registered_by = request.user

        client.save()

        messages.success(
            request,
            f"Client '{client.full_name}' {'updated' if client.pk else 'registered'} successfully!"
        )
        return redirect("clients:client_list")

    messages.error(request, "Please correct the errors below.")
    return render(
        request,
        "clients/client_form.html",
        {"form": form, "dashboard_title": "Client Form"},
    )

# ======================================================
# ADD CLIENT
# ======================================================
@login_required
@roles_required("admin", "agent")
def add_client(request):
    form = ClientForm(request.POST or None, request.FILES or None)
    return save_client_form(request, form)

# ======================================================
# EDIT CLIENT
# ======================================================
@login_required
@roles_required("admin", "agent")
def edit_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, request.FILES or None, instance=client)
    return save_client_form(request, form, client)

# ======================================================
# CLIENT DETAIL + QR GENERATION
# ======================================================
@login_required
@roles_required("admin", "agent")
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)

    active_policy = (
        Policy.objects.filter(
            client=client,
            is_active=True,
            is_archived=False,
            expiry_date__gte=timezone.now().date(),
        )
        .order_by("-start_date")
        .first()
    )

    # Create short-lived verification token for QR
    token_obj = ClientVerificationToken.objects.create(client=client)
    secure_url = request.build_absolute_uri(
        reverse("clients:verify_client", args=[token_obj.token])
    )

    context = {
        "client": client,
        "active_policy": active_policy,
        "secure_url": secure_url,
        "now": timezone.now(),
    }
    return render(request, "clients/client_detail.html", context)

# ======================================================
# HOSPITAL VERIFICATION PAGE
# ======================================================
@login_required
def verify_client(request, token):
    token_obj = get_object_or_404(ClientVerificationToken, token=token)

    if not token_obj.is_valid():
        return render(request, "clients/verify_failed.html")

    client = token_obj.client

    return render(
        request,
        "clients/verify_client.html",
        {"client": client, "expires_at": token_obj.expires_at},
    )

# ======================================================
# QR IMAGE GENERATOR (OPTIONAL API)
# ======================================================
@login_required
@roles_required("agent")
def generate_qr(request, client_id):
    client = get_object_or_404(Client, pk=client_id)

    token_obj = ClientVerificationToken.objects.create(client=client)
    qr_data = request.build_absolute_uri(
        reverse("clients:verify_client", args=[token_obj.token])
    )

    qr_img = qrcode.make(qr_data)

    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    return HttpResponse(buffer.getvalue(), content_type="image/png")

# ======================================================
# FINGERPRINT CAPTURE (AJAX)
# ======================================================
@login_required
@roles_required("admin", "agent")
def capture_fingerprint(request):
    try:
        if os.environ.get("RENDER") or not os.environ.get("FINGERPRINT_HARDWARE"):
            dummy_bytes = b"dummy_fingerprint_template"
            template_base64 = base64.b64encode(dummy_bytes).decode("utf-8")
        else:
            from .fingerprint_hardware import capture_fingerprint as hw_capture
            template_bytes = hw_capture()
            template_base64 = base64.b64encode(template_bytes).decode("utf-8")

        return JsonResponse({"success": True, "fingerprint": template_base64})
    except Exception as e:
        return JsonResponse(
            {"success": False, "fingerprint": None, "error": str(e)}
        )

# ======================================================
# QR VERIFY API (OPTIONAL MOBILE / SCANNER)
# ======================================================
@login_required
@roles_required("agent")
@csrf_exempt
def verify_qr_api(request):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Invalid request method."}
        )

    token = request.POST.get("verify_token")
    if not token:
        return JsonResponse(
            {"success": False, "error": "Missing token."}
        )

    try:
        token_obj = ClientVerificationToken.objects.get(token=token)

        if not token_obj.is_valid():
            return JsonResponse(
                {"success": False, "error": "Token expired."}
            )

        client = token_obj.client
        client.status = "verified"
        client.fingerprint_verified = True
        client.save(update_fields=["status", "fingerprint_verified"])

        token_obj.delete()

        return JsonResponse(
            {
                "success": True,
                "message": f"Client {client.full_name} verified successfully!",
            }
        )
    except ClientVerificationToken.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Invalid token."}
        )

# ======================================================
# DRF VIEWSET
# ======================================================
class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
