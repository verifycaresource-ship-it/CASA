import base64
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
from django.conf import settings
from django.http import JsonResponse

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Client
from .forms import ClientForm
from .serializers import ClientSerializer
from accounts.utils import roles_required
from accounts.models import User

# ---------------------------
# Fingerprint Service
# ---------------------------
FINGERPRINT_SERVICE_URL = getattr(settings, "FINGERPRINT_SERVICE_URL", "http://127.0.0.1:5000/enroll")


def capture_fingerprint_from_service():
    """Call external fingerprint service to capture fingerprint; returns Base64 string."""
    try:
        resp = requests.get(FINGERPRINT_SERVICE_URL, timeout=30)
        data = resp.json()
        if data.get("success") and data.get("template"):
            return data["template"]
    except Exception as e:
        print("Fingerprint capture error:", e)
    return None


def handle_fingerprint(client, fingerprint_base64: str):
    """Decode Base64 fingerprint and update client verification status."""
    if fingerprint_base64:
        try:
            client.fingerprint_data = base64.b64decode(fingerprint_base64)
            client.fingerprint_verified = True
            client.status = "verified"
        except Exception:
            client.fingerprint_verified = False
            client.status = "pending"
    else:
        client.fingerprint_verified = False
        client.status = "pending"
    return client


@login_required
def capture_fingerprint(request):
    """AJAX endpoint to capture fingerprint from Flask service."""
    fingerprint_base64 = capture_fingerprint_from_service()
    if fingerprint_base64:
        return JsonResponse({"success": True, "fingerprint": fingerprint_base64})
    return JsonResponse({"success": False, "fingerprint": None})


# ---------------------------
# Web Views
# ---------------------------
@login_required
@roles_required("admin", "agent")
def client_list(request):
    user = request.user
    search_query = request.GET.get("search", "").strip()
    gender_filter = request.GET.get("gender", "").strip()
    agent_filter = request.GET.get("agent", "").strip()

    # Agent sees only their clients
    clients = Client.objects.filter(registered_by=user) if user.role == "agent" else Client.objects.all()

    # Apply filters
    if search_query:
        clients = clients.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    if gender_filter:
        clients = clients.filter(gender__iexact=gender_filter)
    if agent_filter and user.role == "admin":
        clients = clients.filter(registered_by_id=agent_filter)

    # Pagination
    paginator = Paginator(clients.order_by("-created_at"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Stats
    total_clients = clients.count()
    verified_clients = clients.filter(status="verified").count()
    pending_clients = clients.filter(status="pending").count()
    failed_clients = clients.filter(status="failed").count()

    gender_counts = clients.values("gender").annotate(count=Count("id"))
    male_clients = next((g["count"] for g in gender_counts if g["gender"] == "male"), 0)
    female_clients = next((g["count"] for g in gender_counts if g["gender"] == "female"), 0)
    other_clients = next((g["count"] for g in gender_counts if g["gender"] == "other"), 0)

    month_counts = clients.annotate(month=TruncMonth("created_at")).values("month").annotate(count=Count("id")).order_by("month")
    months = [m["month"].strftime("%b %Y") for m in month_counts]
    month_data = [m["count"] for m in month_counts]

    agents = User.objects.filter(role="agent") if user.role == "admin" else None

    context = {
        "clients": page_obj,
        "page_obj": page_obj,
        "agents": agents,
        "search_query": search_query,
        "gender_filter": gender_filter,
        "agent_filter": agent_filter,
        "total_clients": total_clients,
        "verified_clients": verified_clients,
        "pending_clients": pending_clients,
        "failed_clients": failed_clients,
        "male_clients": male_clients,
        "female_clients": female_clients,
        "other_clients": other_clients,
        "months": months,
        "month_data": month_data,
    }
    return render(request, "clients/client_list.html", context)


@login_required
@roles_required("admin", "agent")
def add_client(request):
    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            client = form.save(commit=False)
            fingerprint_base64 = request.POST.get("fingerprint_base64") or capture_fingerprint_from_service()
            client = handle_fingerprint(client, fingerprint_base64)
            client.registered_by = request.user
            client.save()
            messages.success(request, f"Client '{client.full_name}' registered successfully!")
            return redirect("clients:client_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ClientForm()
    return render(request, "clients/client_form.html", {"form": form, "dashboard_title": "Register New Client"})


@login_required
@roles_required("admin", "agent")
def edit_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            client = form.save(commit=False)
            fingerprint_base64 = request.POST.get("fingerprint_base64")
            client = handle_fingerprint(client, fingerprint_base64)
            client.save()
            messages.success(request, f"Client '{client.full_name}' updated successfully!")
            return redirect("clients:client_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ClientForm(instance=client)
    return render(request, "clients/client_form.html", {"form": form, "dashboard_title": f"Edit Client: {client.full_name}"})


@login_required
@roles_required("admin", "agent")
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(request, "clients/client_detail.html", {"client": client, "dashboard_title": f"Client: {client.full_name}"})


# ---------------------------
# DRF API
# ---------------------------
class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        fingerprint_base64 = self.request.data.get("fingerprint_base64")
        client = serializer.save(registered_by=self.request.user)
        client = handle_fingerprint(client, fingerprint_base64)
        client.save()

    def perform_update(self, serializer):
        fingerprint_base64 = self.request.data.get("fingerprint_base64")
        client = serializer.save()
        if fingerprint_base64:
            client = handle_fingerprint(client, fingerprint_base64)
            client.save()

    @action(detail=False, methods=["post"])
    def verify_fingerprint(self, request):
        fingerprint_base64 = request.data.get("fingerprint_base64")
        if not fingerprint_base64:
            return Response({"error": "No fingerprint provided"}, status=400)
        try:
            fingerprint_bytes = base64.b64decode(fingerprint_base64)
        except Exception:
            return Response({"error": "Invalid Base64"}, status=400)
        client = Client.objects.filter(fingerprint_data=fingerprint_bytes).first()
        if client:
            return Response({
                "success": True,
                "client_id": client.id,
                "status": client.status,
                "fingerprint_verified": client.fingerprint_verified
            })
        return Response({"success": False}, status=404)