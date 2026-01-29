from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, F, FloatField
from django.db.models.functions import Coalesce
from rest_framework import viewsets, permissions
from claims.services.clinical_parser import parse_structured_file

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from claims.models import Claim, ClinicalEvent, RiskScore
from claims.services.clinical_parser import parse_structured_file

from hospitals.models import HospitalAssignment
from accounts.utils import roles_required
from .serializers import ClaimSerializer


# ========================
# 🏥 Submit Claim for Hospital Assignment
# ========================
@login_required
@roles_required("hospital")
def submit_claim_for_assignment(request, assignment_id):
    """
    Hospital submits a claim for an accepted assignment.
    - Creates claim
    - Parses structured clinical file (if uploaded)
    - Auto-links clinical events
    - Auto-generates maternal + neonatal risk scores
    """

    hospital = getattr(request.user, "hospital_profile", None)

    assignment = get_object_or_404(
        HospitalAssignment,
        pk=assignment_id,
        hospital=hospital,
        status="accepted"
    )

    if request.method == "POST":
        client = assignment.client
        policy = assignment.policy
        amount = request.POST.get("amount")
        notes = request.POST.get("notes", "").strip()
        document = request.FILES.get("document")

        if not amount:
            messages.error(request, "Claim amount is required.")
            return redirect("claims:submit_claim_for_assignment", assignment_id=assignment_id)

        claim_number = f"CLM-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        # =====================
        # 1️⃣ Create Claim
        # =====================
        claim = Claim.objects.create(
            claim_number=claim_number,
            hospital=hospital,
            client=client,
            policy=policy,
            amount=amount,
            notes=notes,
            document=document,
            status="pending",
            created_by=request.user,
        )

        # =====================
        # 2️⃣ Clinical Intelligence Pipeline
        # =====================
        try:
            if document:
                # Parse hospital clinical upload
                results = parse_structured_file(document, hospital)

                # Auto-link clinical events to this claim
                ClinicalEvent.objects.filter(
                    hospital=hospital,
                    policy=policy,
                    claim__isnull=True
                ).update(claim=claim)

                messages.success(
                    request,
                    f"Clinical data processed: "
                    f"{results['created_events']} events, "
                    f"{results['created_risks']} risks"
                )
            else:
                # Fallback manual event
                clinical_event = ClinicalEvent.objects.create(
                    claim=claim,
                    client=client,
                    policy=policy,
                    hospital=hospital,
                    visit_type="OTHER",
                    doctor_name="N/A",
                    department="N/A",
                    notes="Initial claim submission (no structured file)",
                    source="manual_entry"
                )

                # Default low-risk baseline
                RiskScore.objects.bulk_create([
                    RiskScore(event=clinical_event, type="maternal", score=0.0, level="LOW"),
                    RiskScore(event=clinical_event, type="neonatal", score=0.0, level="LOW"),
                ])

        except Exception as e:
            messages.warning(
                request,
                f"Claim submitted, but clinical data could not be processed: {str(e)}"
            )

        # =====================
        # 3️⃣ Finalize Assignment
        # =====================
        assignment.status = "completed"
        assignment.save(update_fields=["status", "updated_at"])

        messages.success(request, f"Claim {claim_number} submitted for {client.full_name}.")
        return redirect("hospitals:assigned_clients")

    return render(request, "claims/submit_claim.html", {
        "assignment": assignment,
        "dashboard_title": "Submit Claim",
    })



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Q, FloatField
from django.db.models.functions import Coalesce
from .models import Claim, ClinicalEvent, RiskScore
from accounts.utils import roles_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum, F, FloatField
from django.db.models.functions import Coalesce

from .models import Claim, ClinicalEvent, RiskScore
from accounts.utils import roles_required


# ========================
# 🏥 Hospital Dashboard (Full Intelligence System)
# ========================
@login_required
@roles_required("hospital")
def hospital_dashboard(request):
    """
    National-grade hospital dashboard with:
    - Financial intelligence
    - Clinical monitoring
    - Risk analytics
    """

    hospital = getattr(request.user, "hospital_profile", None)
    if not hospital:
        messages.error(request, "Hospital profile not found.")
        return redirect("accounts:dashboard")

    # ======================
    # Claims Intelligence
    # ======================
    claims = Claim.objects.filter(
        hospital=hospital
    ).select_related("client", "policy").order_by("-created_at")

    total_claims = claims.count()
    pending_claims = claims.filter(status="pending").count()
    approved_claims = claims.filter(status="approved").count()
    rejected_claims = claims.filter(status="rejected").count()

    revenue_collected = claims.filter(
        status__in=["approved", "reimbursed"]
    ).aggregate(
        total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0)
    )["total"]

    pending_amount = claims.filter(
        status="pending"
    ).aggregate(
        total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0)
    )["total"]

    recent_claims = claims[:5]

    # ======================
    # Clinical Intelligence
    # ======================
    clinical_events = ClinicalEvent.objects.filter(
        hospital=hospital
    ).select_related("client", "claim").order_by("-event_datetime")[:5]

    # ======================
    # Risk Intelligence
    # ======================
    risk_scores = RiskScore.objects.filter(
        event__hospital=hospital
    ).select_related("event", "event__client").order_by("-created_at")[:10]

    # ======================
    # High Risk Overview
    # ======================
    high_risk_maternal = RiskScore.objects.filter(
        event__hospital=hospital,
        type="maternal",
        level="HIGH"
    ).count()

    high_risk_neonatal = RiskScore.objects.filter(
        event__hospital=hospital,
        type="neonatal",
        level="HIGH"
    ).count()

    # ======================
    # Context
    # ======================
    context = {
        "dashboard_title": f"{hospital.name} Dashboard",
        "hospital": hospital,

        # Claims
        "claims": claims,
        "total_claims": total_claims,
        "pending_claims": pending_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "revenue_collected": revenue_collected,
        "pending_amount": pending_amount,
        "recent_claims": recent_claims,

        # Clinical
        "recent_clinical_events": clinical_events,

        # Risk
        "recent_risk_scores": risk_scores,
        "high_risk_maternal": high_risk_maternal,
        "high_risk_neonatal": high_risk_neonatal,
    }

    return render(request, "claims/hospital_dashboard.html", context)




# ========================
# 🧩 Claim List (All Roles)
# ========================
@login_required
def claim_list(request):
    user = request.user
    role = getattr(user, "role", None)

    if user.is_superuser or role in ["admin", "claim_officer"]:
        claims = Claim.objects.select_related("client", "hospital", "policy").all()
        title = "All Hospital Claims"
    elif role == "agent":
        claims = Claim.objects.filter(client__agent=user)
        title = "My Clients' Claims"
    elif role == "hospital":
        hospital = getattr(user, "hospital_profile", None)
        claims = Claim.objects.filter(hospital=hospital) if hospital else Claim.objects.none()
        title = "My Hospital Claims"
    else:
        claims = Claim.objects.none()
        title = "Claims"

    return render(request, "claims/claim_list.html", {
        "claims": claims,
        "dashboard_title": title,
        "role": role,
    })


# ========================
# ✏️ Edit Claim (Admin/Claim Officer)
# ========================
@login_required
@roles_required("admin", "claim_officer")
def edit_claim(request, pk):
    claim = get_object_or_404(Claim, pk=pk)

    if request.method == "POST":
        claim.amount = request.POST.get("amount", claim.amount)
        claim.notes = request.POST.get("notes", claim.notes)
        claim.status = request.POST.get("status", claim.status)
        claim.save()
        messages.success(request, f"Claim {claim.claim_number} updated successfully.")
        return redirect("claims:claim_list")

    return render(request, "claims/edit_claim.html", {
        "dashboard_title": f"Edit Claim - {claim.claim_number}",
        "claim": claim,
        "role": getattr(request.user, "role", "guest"),
    })


# ========================
# 🔍 Claim Detail
# ========================
@login_required
def claim_detail(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    user = request.user
    role = getattr(user, "role", None)

    # Role-based access
    if user.is_superuser:
        role = "admin"
    elif role == "hospital":
        hospital = getattr(user, "hospital_profile", None)
        if not hospital or claim.hospital != hospital:
            messages.error(request, "You are not authorized to view this claim.")
            return redirect("claims:claim_list")
    elif role == "agent":
        if claim.client.agent != user:
            messages.error(request, "You are not authorized to view this claim.")
            return redirect("claims:claim_list")
    elif role not in ["admin", "claim_officer"]:
        messages.error(request, "Access denied.")
        return redirect("claims:claim_list")

    # Get clinical events and risk scores
    clinical_events = claim.clinical_events.select_related("hospital", "client").all()
    risk_scores = RiskScore.objects.filter(event__in=clinical_events)

    return render(request, "claims/claim_detail.html", {
        "claim": claim,
        "clinical_events": clinical_events,
        "risk_scores": risk_scores,
        "dashboard_title": f"Claim Details - {claim.claim_number}",
        "role": role,
    })


# ========================
# ✅ Approve Claim
# ========================
@login_required
@roles_required("admin", "claim_officer")
def approve_claim(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    if claim.status != "approved":
        claim.approve_claim()
        messages.success(request, f"Claim {claim.claim_number} approved successfully.")
    else:
        messages.info(request, f"Claim {claim.claim_number} is already approved.")
    return redirect("claims:claim_detail", pk=pk)


# ========================
# ❌ Reject Claim
# ========================
@login_required
@roles_required("admin", "claim_officer")
def reject_claim(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    if claim.status != "rejected":
        claim.reject_claim(notes=request.POST.get("notes", None))
        messages.warning(request, f"Claim {claim.claim_number} rejected.")
    else:
        messages.info(request, f"Claim {claim.claim_number} is already rejected.")
    return redirect("claims:claim_detail", pk=pk)


# ========================
# 💰 Reimburse Claim
# ========================
@login_required
@roles_required("admin")
def reimburse_claim(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    try:
        claim.mark_reimbursed()
        messages.success(request, f"Claim {claim.claim_number} marked as reimbursed.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect("claims:claim_detail", pk=pk)


# ========================
# 🌐 DRF API ViewSet
# ========================
class ClaimViewSet(viewsets.ModelViewSet):
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", "guest")

        if user.is_superuser or role in ["admin", "claim_officer"]:
            return Claim.objects.all()
        elif role == "agent":
            return Claim.objects.filter(client__agent=user)
        elif role == "hospital":
            hospital = getattr(user, "hospital_profile", None)
            return Claim.objects.filter(hospital=hospital) if hospital else Claim.objects.none()
        return Claim.objects.none()
