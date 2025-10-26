from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
import base64

from rest_framework import viewsets, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Client
from .forms import ClientForm
from .serializers import ClientSerializer
from accounts.utils import roles_required
from accounts.models import User  # Agent as User with role='agent'

# ==========================
# 🌍 Helper function
# ==========================
def handle_fingerprint(client, fingerprint_file=None, fingerprint_base64=None):
    """Update client fingerprint and status"""
    if fingerprint_file:
        client.fingerprint_data = fingerprint_file.read()
        client.fingerprint_verified = True
        client.status = "verified"
    elif fingerprint_base64:
        try:
            client.fingerprint_data = base64.b64decode(fingerprint_base64)
            client.fingerprint_verified = True
            client.status = "verified"
        except Exception:
            # Keep previous status if decoding fails
            messages.warning(
                None, "Invalid fingerprint data. Status not changed."
            )
    # If neither, leave status unchanged for edit or pending for new client
    return client


# ==========================
# 🌍 Web Views
# ==========================
from django.db.models.functions import TruncMonth
from django.db.models import Count
from datetime import datetime

@login_required
@roles_required("admin", "agent")
def client_list(request):
    user = request.user
    search_query = request.GET.get("search", "").strip()
    gender_filter = request.GET.get("gender", "").strip()
    agent_filter = request.GET.get("agent", "").strip()

    # Base queryset
    clients = Client.objects.filter(agent=user) if getattr(user, "role", None) == "agent" else Client.objects.all()

    # Apply search
    if search_query:
        clients = clients.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    # Apply gender filter
    if gender_filter:
        clients = clients.filter(gender__iexact=gender_filter)

    # Filter by agent if admin
    if agent_filter and getattr(user, "role", None) == "admin":
        clients = clients.filter(agent_id=agent_filter)

    # Pagination
    paginator = Paginator(clients.order_by("-created_at"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Agents list for filter dropdown
    agents = User.objects.filter(role="agent") if getattr(user, "role", None) == "admin" else None

    # === Dashboard Stats ===
    total_clients = clients.count()
    verified_clients = clients.filter(status="verified").count()
    pending_clients = clients.filter(status="pending").count()
    failed_clients = clients.filter(status="failed").count()

    # Gender distribution for charts
    gender_counts = clients.values("gender").annotate(count=Count("id"))
    male_clients = next((g["count"] for g in gender_counts if g["gender"]=="Male"), 0)
    female_clients = next((g["count"] for g in gender_counts if g["gender"]=="Female"), 0)
    other_clients = next((g["count"] for g in gender_counts if g["gender"]=="Other"), 0)

    # Clients by registration month
    month_counts = (
        clients.annotate(month=TruncMonth("created_at"))
               .values("month")
               .annotate(count=Count("id"))
               .order_by("month")
    )
    # Prepare data for chart.js
    months = [m["month"].strftime("%b %Y") for m in month_counts]
    month_data = [m["count"] for m in month_counts]

    context = {
        "clients": page_obj,
        "page_obj": page_obj,
        "agents": agents,
        "search_query": search_query,
        "gender_filter": gender_filter,
        "agent_filter": agent_filter,
        "dashboard_title": "Clients Dashboard",
        # Stats
        "total_clients": total_clients,
        "verified_clients": verified_clients,
        "pending_clients": pending_clients,
        "failed_clients": failed_clients,
        # Gender chart data
        "male_clients": male_clients,
        "female_clients": female_clients,
        "other_clients": other_clients,
        # Monthly registration chart data
        "months": months,
        "month_data": month_data,
    }
    return render(request, "clients/client_list.html", context)



@login_required
@roles_required("admin", "agent")
def add_client(request):
    """Add/register a new client with optional fingerprint"""
    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            client = form.save(commit=False)
            fingerprint_file = request.FILES.get("fingerprint_file")
            fingerprint_base64 = request.POST.get("fingerprint_base64")

            client = handle_fingerprint(client, fingerprint_file, fingerprint_base64)

            if not client.status:
                client.status = "pending"

            client.registered_by = request.user
            client.save()
            messages.success(request, f"Client '{client}' registered successfully!")
            return redirect("clients:client_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ClientForm()

    return render(request, "clients/client_form.html", {
        "form": form,
        "dashboard_title": "Register New Client",
    })


@login_required
@roles_required("admin", "agent")
def edit_client(request, pk):
    """Edit existing client"""
    client = get_object_or_404(Client, pk=pk)

    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            client = form.save(commit=False)
            fingerprint_file = request.FILES.get("fingerprint_file")
            fingerprint_base64 = request.POST.get("fingerprint_base64")

            client = handle_fingerprint(client, fingerprint_file, fingerprint_base64)
            client.save()
            messages.success(request, f"Client '{client.first_name} {client.last_name}' updated successfully!")
            return redirect("clients:client_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ClientForm(instance=client)

    return render(request, "clients/client_form.html", {
        "form": form,
        "dashboard_title": f"Edit Client: {client.first_name} {client.last_name}"
    })


@login_required
@roles_required("admin", "agent")
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(request, "clients/client_detail.html", {
        "client": client,
        "dashboard_title": f"Client: {client.first_name} {client.last_name}",
    })


# ==========================
# 🌐 API Views (DRF)
# ==========================
class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        fingerprint_base64 = self.request.data.get("fingerprint_base64")
        client = serializer.save(registered_by=self.request.user)
        client = handle_fingerprint(client, fingerprint_base64=fingerprint_base64)
        if not client.status:
            client.status = "pending"
        client.save()

    def perform_update(self, serializer):
        fingerprint_base64 = self.request.data.get("fingerprint_base64")
        client = serializer.save()
        if fingerprint_base64:
            client = handle_fingerprint(client, fingerprint_base64=fingerprint_base64)
            client.save()

    @action(detail=False, methods=["post"])
    def verify_fingerprint(self, request):
        fingerprint_base64 = request.data.get("fingerprint_base64")
        if not fingerprint_base64:
            return Response({"error": "No fingerprint provided"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            fingerprint_bytes = base64.b64decode(fingerprint_base64)
        except Exception:
            return Response({"error": "Invalid Base64 fingerprint"}, status=status.HTTP_400_BAD_REQUEST)

        client = Client.objects.filter(fingerprint_data=fingerprint_bytes).first()
        if client:
            return Response({
                "success": True,
                "client_id": client.id,
                "status": client.status,
                "fingerprint_verified": client.fingerprint_verified
            })
        return Response({"success": False}, status=status.HTTP_404_NOT_FOUND)

