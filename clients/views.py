import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count
from .models import Client
from .forms import ClientForm
from .decorators import roles_required

# Import fingerprint functions
from .fingerprint_service import enroll_client_from_base64, verify_client_from_base64, capture_fingerprint


# ---------------------------
# CLIENT DASHBOARD / LIST
# ---------------------------
@login_required
@roles_required("admin", "agent")
def client_list(request):
    search_query = request.GET.get("search", "")
    gender_filter = request.GET.get("gender", "")
    agent_filter = request.GET.get("agent", "")

    clients = Client.objects.all()

    if search_query:
        clients = clients.filter(
            first_name__icontains=search_query
        ) | clients.filter(last_name__icontains=search_query) | clients.filter(email__icontains=search_query)

    if gender_filter:
        clients = clients.filter(gender=gender_filter)

    if agent_filter:
        clients = clients.filter(registered_by__id=agent_filter)

    # Pagination
    paginator = Paginator(clients.order_by("-id"), 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # KPI counts
    total_clients = Client.objects.count()
    verified_clients = Client.objects.filter(status="verified").count()
    pending_clients = Client.objects.filter(status="pending").count()
    failed_clients = Client.objects.filter(status="failed").count()

    # Gender chart
    male_clients = Client.objects.filter(gender="male").count()
    female_clients = Client.objects.filter(gender="female").count()
    other_clients = Client.objects.filter(gender="other").count()

    # Monthly chart (new clients by month)
    month_data_qs = Client.objects.extra({'month': "strftime('%%m', dob)"}).values('month').annotate(count=Count('id')).order_by('month')
    months = [m['month'] for m in month_data_qs]
    month_data = [m['count'] for m in month_data_qs]

    context = {
        "clients": page_obj,
        "page_obj": page_obj,
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
        "agents": None,  # populate with User.objects.filter(role='agent') if needed
    }
    return render(request, "clients/client_list.html", context)


# ---------------------------
# ADD CLIENT
# ---------------------------
@login_required
@roles_required("admin", "agent")
def add_client(request):
    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES)
        if form.is_valid():
            client = form.save(commit=False)
            fingerprint_base64 = request.POST.get("fingerprint_base64")
            if fingerprint_base64:
                try:
                    enroll_client_from_base64(client, fingerprint_base64)
                    client.status = "verified"
                except Exception as e:
                    client.status = "failed"
                    messages.warning(request, f"Fingerprint enrollment failed: {e}")
            else:
                client.status = "pending"

            client.registered_by = request.user
            client.save()
            messages.success(request, f"Client '{client.full_name}' registered successfully!")
            return redirect("clients:client_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ClientForm()
    return render(request, "clients/client_form.html", {"form": form, "dashboard_title": "Register New Client"})


# ---------------------------
# EDIT CLIENT
# ---------------------------
@login_required
@roles_required("admin", "agent")
def edit_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        form = ClientForm(request.POST, request.FILES, instance=client)
        if form.is_valid():
            client = form.save(commit=False)
            fingerprint_base64 = request.POST.get("fingerprint_base64")
            if fingerprint_base64:
                try:
                    enroll_client_from_base64(client, fingerprint_base64)
                    client.status = "verified"
                except Exception as e:
                    messages.warning(request, f"Fingerprint enrollment failed: {e}")
            client.save()
            messages.success(request, f"Client '{client.full_name}' updated successfully!")
            return redirect("clients:client_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ClientForm(instance=client)
    return render(request, "clients/client_form.html", {"form": form, "dashboard_title": f"Edit Client: {client.full_name}"})


from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from .models import Client
from policies.models import Policy


import secrets
from django.utils import timezone

def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)

    # ✅ Active policy
    active_policy = (
        Policy.objects
        .filter(
            client=client,
            is_active=True,
            is_archived=False,
            expiry_date__gte=timezone.now().date()
        )
        .order_by("-start_date")
        .first()
    )

    # 🔒 Generate a one-time secure token for QR login verification
    if not hasattr(client, 'secure_token') or not client.secure_token:
        client.secure_token = secrets.token_urlsafe(16)
        client.save(update_fields=['secure_token'])

    context = {
        "client": client,
        "active_policy": active_policy,
        "now": timezone.now(),
    }
    return render(request, "clients/client_detail.html", context)





# ---------------------------
# FINGERPRINT CAPTURE (AJAX)
# ---------------------------
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import base64
from .fingerprint_service import capture_fingerprint as capture_fp

@login_required
@roles_required("admin", "agent")
def capture_fingerprint(request):
    """
    Capture fingerprint via Digital Persona SDK (Windows/Linux).
    Returns Base64 encoded template.
    """
    try:
        template_bytes = capture_fp()  # call fingerprint_service.py
        template_base64 = base64.b64encode(template_bytes).decode("utf-8")
        return JsonResponse({"success": True, "fingerprint": template_base64})
    except Exception as e:
        return JsonResponse({"success": False, "fingerprint": None, "error": str(e)})



# ---------------------------
# DRF VIEWSET (optional)
# ---------------------------
from rest_framework import viewsets
from .serializers import ClientSerializer

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
