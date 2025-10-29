import datetime
import io
import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, F, FloatField, Q
from django.db.models.functions import Coalesce
from django.utils.timezone import make_aware, now
from django.http import HttpResponse
from django.template.loader import render_to_string
import openpyxl
from xhtml2pdf import pisa  # pip install xhtml2pdf
from rest_framework import viewsets, permissions

from .models import User
from .forms import AgentRegistrationForm, AdminPasswordResetForm
from .serializers import UserSerializer
from .utils import roles_required
from clients.models import Client
from policies.models import Policy
from claims.models import Claim
from hospitals.models import Hospital


# ==============================
# ADMIN REPORTS
# ==============================
@login_required(login_url="accounts:login")
@roles_required("admin")
def admin_reports(request):
    """Admin report page with filters, summary, and export-ready data."""
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    status_filter = request.GET.get("status")  # 'verified', 'pending', 'failed'

    # Base querysets
    clients = Client.objects.all()
    policies = Policy.objects.all()
    claims = Claim.objects.all()

    # Date filtering
    try:
        if start_date:
            start = make_aware(datetime.datetime.strptime(start_date, "%Y-%m-%d"))
            clients = clients.filter(created_at__gte=start)
            policies = policies.filter(created_at__gte=start)
            claims = claims.filter(created_at__gte=start)
        if end_date:
            end = make_aware(datetime.datetime.strptime(end_date, "%Y-%m-%d")) + datetime.timedelta(days=1)
            clients = clients.filter(created_at__lte=end)
            policies = policies.filter(created_at__lte=end)
            claims = claims.filter(created_at__lte=end)
    except ValueError:
        pass

    # Status filtering
    if status_filter:
        clients = clients.filter(status=status_filter)
        claims = claims.filter(status=status_filter)
        policies = policies.filter(Q(status=status_filter) | Q(policy_type__isnull=False))

    # Summary counts
    summary = {
        "clients": clients.count(),
        "policies": policies.count(),
        "claims": claims.count(),
    }

    context = {
        "dashboard_title": "Admin Reports | HealthInsure",
        "clients": clients,
        "policies": policies,
        "claims": claims,
        "start_date": start_date,
        "end_date": end_date,
        "status_filter": status_filter,
        "summary": summary,
    }
    return render(request, "accounts/admin_reports.html", context)


@login_required(login_url="accounts:login")
@roles_required("admin")
def export_report(request, format):
    """Export reports as CSV, XLS, or PDF."""
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    status_filter = request.GET.get("status")

    clients = Client.objects.all()
    policies = Policy.objects.all()
    claims = Claim.objects.all()

    # Apply filters
    try:
        if start_date:
            start = make_aware(datetime.datetime.strptime(start_date, "%Y-%m-%d"))
            clients = clients.filter(created_at__gte=start)
            policies = policies.filter(created_at__gte=start)
            claims = claims.filter(created_at__gte=start)
        if end_date:
            end = make_aware(datetime.datetime.strptime(end_date, "%Y-%m-%d")) + datetime.timedelta(days=1)
            clients = clients.filter(created_at__lte=end)
            policies = policies.filter(created_at__lte=end)
            claims = claims.filter(created_at__lte=end)
    except ValueError:
        pass

    if status_filter:
        clients = clients.filter(status=status_filter)
        claims = claims.filter(status=status_filter)
        policies = policies.filter(Q(status=status_filter) | Q(policy_type__isnull=False))

    timestamp = now().strftime("%Y%m%d_%H%M%S")

    # CSV Export
    if format.lower() == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="report_{timestamp}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Category", "Count"])
        writer.writerow(["Clients", clients.count()])
        writer.writerow(["Policies", policies.count()])
        writer.writerow(["Claims", claims.count()])
        return response

    # XLS Export
    elif format.lower() in ["xls", "xlsx"]:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Report"
        ws.append(["Category", "Count"])
        ws.append(["Clients", clients.count()])
        ws.append(["Policies", policies.count()])
        ws.append(["Claims", claims.count()])
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="report_{timestamp}.xlsx"'
        wb.save(response)
        return response

    # PDF Export
    elif format.lower() == "pdf":
        html = render_to_string("accounts/report_pdf.html", {
            "clients": clients,
            "policies": policies,
            "claims": claims,
            "start_date": start_date,
            "end_date": end_date,
            "status_filter": status_filter,
        })
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="report_{timestamp}.pdf"'
        pisa_status = pisa.CreatePDF(io.BytesIO(html.encode("UTF-8")), dest=response)
        if pisa_status.err:
            return HttpResponse("Error generating PDF", status=500)
        return response

    return HttpResponse("Invalid export format", status=400)


# ==============================
# AUTHENTICATION
# ==============================
def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            if not user.is_active_for_login():
                messages.error(request, "Your account is inactive or suspended.")
            else:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                redirect_map = {
                    "hospital": "claims:hospital_claim_dashboard",
                    "agent": "accounts:agent_dashboard"
                }
                return redirect(redirect_map.get(user.role, "accounts:dashboard"))
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "registration/login.html")


@login_required(login_url="accounts:login")
def logout_view(request):
    logout(request)
    messages.info(request, "You have logged out successfully.")
    return redirect("accounts:login")


# ==============================
# DASHBOARDS
# ==============================
@login_required(login_url="accounts:login")
def dashboard(request):
    """Admin dashboard."""
    user = request.user
    if user.role == "agent":
        return redirect("accounts:agent_dashboard")

    total_clients = Client.objects.count()
    verified_clients = Client.objects.filter(status="verified").count()
    pending_clients = Client.objects.filter(status="pending").count()
    failed_clients = Client.objects.filter(status="failed").count()
    active_policies = Policy.objects.filter(is_active=True).count()
    total_claims = Claim.objects.count()
    total_hospitals = Hospital.objects.count()
    total_revenue = Claim.objects.filter(status__in=["approved","reimbursed"]).aggregate(
        total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0)
    )["total"]

    cards = [
        {"label": "Clients", "value": total_clients, "color": "blue"},
        {"label": "Verified Clients", "value": verified_clients, "color": "green"},
        {"label": "Pending Clients", "value": pending_clients, "color": "yellow"},
        {"label": "Failed Clients", "value": failed_clients, "color": "red"},
        {"label": "Active Policies", "value": active_policies, "color": "green"},
        {"label": "Claims", "value": total_claims, "color": "yellow"},
        {"label": "Hospitals", "value": total_hospitals, "color": "red"},
        {"label": "Revenue Collected", "value": f"${total_revenue:,.2f}", "color": "teal"},
    ]

    shortcuts = []
    if user.role in ["admin", "finance_officer"] or user.is_superuser:
        shortcuts = [
            {"name": "👥 Manage Users", "url": "/accounts/users/", "color": "blue"},
            {"name": "➕ Add Client", "url": "/clients/add/", "color": "green"},
            {"name": "📑 Add Policy", "url": "/policies/add/", "color": "yellow"},
            {"name": "💰 Manage Claims", "url": "/claims/", "color": "purple"},
            {"name": "🏥 Manage Hospitals", "url": "/hospitals/", "color": "red"},
            {"name": "➕ Add Agent", "url": "/accounts/agents/register/", "color": "green"},
            {"name": "📄 Reports & Export", "url": "/accounts/reports/", "color": "purple"},
        ]

    # Chart data
    policies_labels = list(Policy.objects.values_list("policy_type", flat=True).distinct())
    policies_data = [Policy.objects.filter(policy_type=t).count() for t in policies_labels]
    claims_pending_count = Claim.objects.filter(status="pending").count()
    claims_approved_count = Claim.objects.filter(status="approved").count()
    claims_rejected_count = Claim.objects.filter(status="rejected").count()
    hospitals_labels = ["Verified", "Unverified"]
    hospitals_data = [Hospital.objects.filter(verified=True).count(), Hospital.objects.filter(verified=False).count()]

    context = {
        "dashboard_title": "Admin Dashboard | HealthInsure",
        "user": user,
        "cards": cards,
        "shortcuts": shortcuts,
        "policies_labels": json.dumps(policies_labels),
        "policies_data": json.dumps(policies_data),
        "claims_approved_count": claims_approved_count,
        "claims_pending_count": claims_pending_count,
        "claims_rejected_count": claims_rejected_count,
        "hospitals_labels": json.dumps(hospitals_labels),
        "hospitals_data": json.dumps(hospitals_data),
    }
    return render(request, "dashboard/dashboard.html", context)


@login_required(login_url="accounts:login")
def agent_dashboard(request):
    """Agent dashboard."""
    user = request.user
    if user.role != "agent":
        return redirect("accounts:dashboard")

    clients_qs = Client.objects.filter(agent=user)
    total_clients = clients_qs.count()
    verified_clients = clients_qs.filter(status="verified").count()
    pending_clients = clients_qs.filter(status="pending").count()
    failed_clients = clients_qs.filter(status="failed").count()

    cards = [
        {"label": "My Clients", "value": total_clients, "color": "blue"},
        {"label": "Verified", "value": verified_clients, "color": "green"},
        {"label": "Pending", "value": pending_clients, "color": "yellow"},
        {"label": "Failed", "value": failed_clients, "color": "red"},
    ]

    shortcuts = [
        {"name": "➕ Register Client", "url": "/clients/add/", "color": "green"},
        {"name": "👥 View Clients", "url": "/clients/", "color": "blue"},
    ]

    context = {
        "dashboard_title": "Agent Dashboard | HealthInsure",
        "user": user,
        "cards": cards,
        "shortcuts": shortcuts,
    }
    return render(request, "accounts/agent_dashboard.html", context)


# ==============================
# USER MANAGEMENT
# ==============================
@login_required(login_url="accounts:login")
def user_list(request):
    if not request.user.is_superuser and getattr(request.user, "role", "") != "admin":
        messages.error(request, "You do not have permission to view this page.")
        return redirect("accounts:dashboard")
    users = User.objects.all().order_by("id")
    return render(request, "dashboard/user_list.html", {"users": users})


@login_required(login_url="accounts:login")
def toggle_user_status(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect("accounts:user_list")
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    messages.success(request, f"User '{user.username}' status updated.")
    return redirect("accounts:user_list")


@login_required(login_url="accounts:login")
@roles_required("admin")
def reset_user_password(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = AdminPasswordResetForm(request.POST, instance=user)
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            user.set_password(new_password)
            user.save()
            messages.success(request, f"Password for '{user.username}' has been reset successfully.")
            return redirect("accounts:user_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = AdminPasswordResetForm(instance=user)
    return render(request, "registration/reset_user_password.html", {
        "form": form,
        "user_obj": user,
        "dashboard_title": f"Reset Password for {user.username}",
    })


@login_required(login_url="accounts:login")
@roles_required("admin")
def add_user(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        role = request.POST.get("role")
        if not all([username, email, password, role]):
            messages.error(request, "All fields are required.")
            return redirect("accounts:user_list")
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("accounts:user_list")
        User.objects.create_user(username=username, email=email, password=password, role=role)
        messages.success(request, f"User '{username}' created successfully!")
        return redirect("accounts:user_list")


# ==============================
# AGENT MANAGEMENT
# ==============================
@login_required(login_url="accounts:login")
@roles_required("admin")
def register_agent(request):
    if request.method == "POST":
        form = AgentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            agent = form.save(commit=False)
            agent.role = "agent"
            agent.save()
            messages.success(request, f"Agent '{agent.username}' registered successfully!")
            return redirect("accounts:agent_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = AgentRegistrationForm()
    return render(request, "accounts/register_agent.html", {"form": form, "dashboard_title": "Register New Agent"})


@login_required(login_url="accounts:login")
@roles_required("admin")
def agent_list(request):
    agents = User.objects.filter(role="agent").order_by("id")
    return render(request, "accounts/agent_list.html", {"agents": agents})


# ==============================
# API VIEWSET
# ==============================
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
