from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, F, FloatField
from django.db.models.functions import Coalesce
from rest_framework import viewsets, permissions
import json

from .models import User
from .forms import AgentRegistrationForm
from clients.models import Client
from policies.models import Policy
from claims.models import Claim
from hospitals.models import Hospital
from .serializers import UserSerializer
from accounts.utils import roles_required

# ==============================
# 🌐 API ViewSet
# ==============================
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


# ==============================
# 🔐 LOGIN / LOGOUT
# ==============================
def login_view(request):
    """Authenticate user and redirect based on role"""
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
                # Redirect based on role
                role_redirect = {
                    "hospital": "claims:hospital_claim_dashboard",
                    "agent": "accounts:agent_dashboard",
                }
                return redirect(role_redirect.get(user.role, "accounts:dashboard"))
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "registration/login.html")


@login_required(login_url="accounts:login")
def logout_view(request):
    logout(request)
    messages.info(request, "You have logged out successfully.")
    return redirect("accounts:login")


# ==============================
# 🧭 DASHBOARD
# ==============================
@login_required(login_url="accounts:login")
def dashboard(request):
    """Admin / finance dashboard"""
    user = request.user

    # Redirect agents to their dashboard
    if user.role == "agent":
        return redirect("accounts:agent_dashboard")

    role = getattr(user, "role", "guest")

    # === Stats Cards ===
    total_clients = Client.objects.count()
    active_policies = Policy.objects.filter(is_active=True).count()
    total_claims = Claim.objects.count()
    total_hospitals = Hospital.objects.count()
    total_revenue = Claim.objects.filter(status__in=["approved", "reimbursed"]).aggregate(
        total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0)
    )["total"]

    cards = [
        {"label": "Clients", "value": total_clients, "color": "blue"},
        {"label": "Active Policies", "value": active_policies, "color": "green"},
        {"label": "Claims", "value": total_claims, "color": "yellow"},
        {"label": "Hospitals", "value": total_hospitals, "color": "red"},
        {"label": "Revenue Collected", "value": f"${total_revenue:,.2f}", "color": "teal"},
    ]

    # === Quick Actions ===
    shortcuts = []
    if role in ["admin", "finance_officer"] or user.is_superuser:
        shortcuts = [
            {"name": "👥 Manage Users", "url": "/accounts/users/", "color": "blue"},
            {"name": "➕ Add Client", "url": "/clients/add/", "color": "green"},
            {"name": "📑 Add Policy", "url": "/policies/add/", "color": "yellow"},
            {"name": "💰 Manage Claims", "url": "/claims/", "color": "purple"},
            {"name": "🏥 Manage Hospitals", "url": "/hospitals/", "color": "red"},
            {"name": "➕ Add Agent", "url": "/accounts/agents/register/", "color": "green"},
        ]

    # === Charts ===
    # Policy Distribution
    policies_labels = list(Policy.objects.values_list("policy_type", flat=True).distinct())
    policies_data = [Policy.objects.filter(policy_type=t).count() for t in policies_labels]

    # Claims Overview
    claims_pending_count = Claim.objects.filter(status="pending").count()
    claims_approved_count = Claim.objects.filter(status="approved").count()
    claims_rejected_count = Claim.objects.filter(status="rejected").count()

    # Hospital Verification
    hospitals_labels = ["Verified", "Unverified"]
    hospitals_data = [
        Hospital.objects.filter(verified=True).count(),
        Hospital.objects.filter(verified=False).count(),
    ]

    context = {
        "dashboard_title": "Admin Dashboard | HealthInsure",
        "user": user,
        "role": role,
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
    """Agent-only dashboard"""
    user = request.user
    if user.role != "agent":
        return redirect("accounts:dashboard")

    cards = [
        {"label": "My Clients", "value": Client.objects.filter(agent=user).count(), "color": "blue"},
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
    return render(request, "dashboard/agent_dashboard.html", context)


# ==============================
# 👥 USER MANAGEMENT
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


# ==============================
# ➕ AGENT MANAGEMENT
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
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AgentRegistrationForm()

    return render(request, "accounts/register_agent.html", {"form": form, "dashboard_title": "Register New Agent"})


@login_required(login_url="accounts:login")
@roles_required("admin")
def agent_list(request):
    agents = User.objects.filter(role="agent").order_by("id")
    return render(request, "accounts/agent_list.html", {"agents": agents})
