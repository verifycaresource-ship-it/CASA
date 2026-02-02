from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, F, Q, FloatField
from django.db.models.functions import Coalesce
from django.db import transaction
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from rest_framework import viewsets, permissions
from accounts.utils import roles_required
from .serializers import ClaimSerializer  # <-- this must exist
from django.core.paginator import Paginator

# ========================
# 🏥 Submit Claim for Hospital Assignment
# ========================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone

from accounts.utils import roles_required
from .models import Claim, ClinicalEvent, RiskScore
from hospitals.models import HospitalAssignment
from policies.models import InsuredPerson
from claims.services.clinical_parser import parse_clinical_file

@login_required
@roles_required("hospital")
def submit_claim_for_assignment(request, assignment_id):
    """
    Hospital submits a claim for an accepted assignment.
    - Creates claim
    - Parses structured clinical file (CSV/XLSX)
    - Auto-links clinical events
    - Auto-generates maternal + neonatal risk scores
    - Assigns claim to selected patient (mother/child)
    """

    hospital = getattr(request.user, "hospital_profile", None)
    if not hospital:
        messages.error(request, "Hospital profile not found.")
        return redirect("accounts:dashboard")

    assignment = get_object_or_404(
        HospitalAssignment,
        pk=assignment_id,
        hospital=hospital,
        status="accepted"
    )

    client = assignment.client
    policy = assignment.policy

    # Get insured persons for this policy (mother + children)
    insured_persons = InsuredPerson.objects.filter(policy=policy)

    # Visit types from ClinicalEvent model
    visit_types = getattr(ClinicalEvent, "VISIT_TYPES", [
        ("ANC", "ANC"), ("DELIVERY", "Delivery"), ("PNC", "PNC"), ("OTHER", "Other")
    ])

    if request.method == "POST":
        # -------------------------
        # Get form data
        # -------------------------
        amount = request.POST.get("amount")
        notes = request.POST.get("notes", "").strip()
        document = request.FILES.get("document")  # optional CSV/XLSX
        patient_id = request.POST.get("patient")
        visit_type = request.POST.get("visit_type", "OTHER")

        # Validate selected patient
        patient = None
        if patient_id:
            try:
                patient = InsuredPerson.objects.get(id=patient_id, policy=policy)
            except InsuredPerson.DoesNotExist:
                messages.error(request, "Selected patient is invalid.")
                return redirect(
                    "claims:submit_claim_for_assignment",
                    assignment_id=assignment_id
                )

        if not amount:
            messages.error(request, "Claim amount is required.")
            return redirect(
                "claims:submit_claim_for_assignment",
                assignment_id=assignment_id
            )

        # Generate claim number
        claim_number = f"CLM-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        with transaction.atomic():
            # -------------------------
            # 1️⃣ Create Claim
            # -------------------------
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

            # -------------------------
            # 2️⃣ Clinical Event + Risk Scores
            # -------------------------
            try:
                if document:
                    # Parse uploaded structured clinical file (CSV/XLSX)
                    results = parse_clinical_file(document, hospital)

                    # Auto-link parsed events to this claim and selected patient
                    ClinicalEvent.objects.filter(
                        hospital=hospital,
                        policy=policy,
                        claim__isnull=True
                    ).update(claim=claim, patient=patient)

                    messages.success(
                        request,
                        f"Clinical data processed: {results.get('created_events', 0)} events, "
                        f"{results.get('created_risks', 0)} risks"
                    )
                else:
                    # Manual fallback event
                    clinical_event = ClinicalEvent.objects.create(
                        claim=claim,
                        client=client,
                        policy=policy,
                        hospital=hospital,
                        patient=patient,
                        visit_type=visit_type.upper(),
                        notes="Initial claim submission (no structured file)",
                        source="manual_entry"
                    )

                    # Default baseline risk scores
                    RiskScore.objects.bulk_create([
                        RiskScore(event=clinical_event, type="maternal", score=0.0, level="LOW"),
                        RiskScore(event=clinical_event, type="neonatal", score=0.0, level="LOW"),
                    ])

            except Exception as e:
                messages.warning(
                    request,
                    f"Claim submitted, but clinical data could not be processed: {str(e)}"
                )

            # -------------------------
            # 3️⃣ Finalize Assignment
            # -------------------------
            assignment.status = "completed"
            assignment.save(update_fields=["status", "updated_at"])

        messages.success(
            request,
            f"Claim {claim_number} submitted for {patient.full_name if patient else client.full_name}."
        )
        return redirect("hospitals:assigned_clients")

    # -------------------------
    # GET: Render form
    # -------------------------
    return render(request, "claims/submit_claim.html", {
        "assignment": assignment,
        "dashboard_title": "Submit Claim",
        "insured_persons": insured_persons,
        "visit_types": visit_types,
    })


# ========================
# 🏥 Hospital Dashboard (Full Intelligence)
# ========================
@login_required
@roles_required("hospital")
def hospital_dashboard(request):
    hospital = getattr(request.user, "hospital_profile", None)
    if not hospital:
        messages.error(request, "Hospital profile not found.")
        return redirect("accounts:dashboard")

    claims = Claim.objects.filter(hospital=hospital).select_related("client", "policy").order_by("-created_at")
    total_claims = claims.count()
    pending_claims = claims.filter(status="pending").count()
    approved_claims = claims.filter(status="approved").count()
    rejected_claims = claims.filter(status="rejected").count()

    revenue_collected = claims.filter(
        status__in=["approved", "reimbursed"]
    ).aggregate(total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0))["total"]

    pending_amount = claims.filter(status="pending").aggregate(
        total=Coalesce(Sum(F("amount"), output_field=FloatField()), 0.0)
    )["total"]

    recent_claims = claims[:5]
    clinical_events = ClinicalEvent.objects.filter(hospital=hospital).select_related("client", "claim").order_by("-event_datetime")[:5]
    risk_scores = RiskScore.objects.filter(event__hospital=hospital).select_related("event", "event__client").order_by("-created_at")[:10]

    high_risk_maternal = RiskScore.objects.filter(event__hospital=hospital, type="maternal", level="HIGH").count()
    high_risk_neonatal = RiskScore.objects.filter(event__hospital=hospital, type="neonatal", level="HIGH").count()

    context = {
        "dashboard_title": f"{hospital.name} Dashboard",
        "hospital": hospital,
        "claims": claims,
        "total_claims": total_claims,
        "pending_claims": pending_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "revenue_collected": revenue_collected,
        "pending_amount": pending_amount,
        "recent_claims": recent_claims,
        "recent_clinical_events": clinical_events,
        "recent_risk_scores": risk_scores,
        "high_risk_maternal": high_risk_maternal,
        "high_risk_neonatal": high_risk_neonatal,
    }
    return render(request, "claims/hospital_dashboard.html", context)


# ========================
# Claim List
# ========================
@login_required
def claim_list(request):
    user = request.user
    role = getattr(user, "role", None)

    if user.is_superuser or role in ["admin", "claim_officer"]:
        claims = Claim.objects.select_related("client", "hospital", "policy").all()
    elif role == "agent":
        claims = Claim.objects.filter(client__agent=user)
    elif role == "hospital":
        hospital = getattr(user, "hospital_profile", None)
        claims = Claim.objects.filter(hospital=hospital) if hospital else Claim.objects.none()
    else:
        claims = Claim.objects.none()

    search_query = request.GET.get("search", "")
    status_filter = request.GET.get("status", "")
    hospital_filter = request.GET.get("hospital", "")
    policy_filter = request.GET.get("policy", "")

    if search_query:
        claims = claims.filter(
            Q(claim_number__icontains=search_query) |
            Q(client__first_name__icontains=search_query) |
            Q(client__last_name__icontains=search_query)
        )
    if status_filter:
        claims = claims.filter(status=status_filter)
    if hospital_filter:
        claims = claims.filter(hospital__id=hospital_filter)
    if policy_filter:
        claims = claims.filter(policy__id=policy_filter)

    paginator = Paginator(claims.order_by("-created_at"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "claims": page_obj,
        "dashboard_title": "Claims",
        "role": role,
        "total_claims": claims.count(),
        "pending_claims": claims.filter(status="pending").count(),
        "approved_claims": claims.filter(status="approved").count(),
        "rejected_claims": claims.filter(status="rejected").count(),
        "reimbursed_claims": claims.filter(status="reimbursed").count(),
        "revenue_collected": claims.filter(status__in=["approved", "reimbursed"]).aggregate(
            total=Coalesce(Sum("amount", output_field=FloatField()), 0.0)
        )["total"],
        "search_query": search_query,
        "status_filter": status_filter,
        "hospital_filter": hospital_filter,
        "policy_filter": policy_filter,
        "hospitals": Claim.objects.values("hospital__id", "hospital__name").distinct(),
        "policies": Claim.objects.values("policy__id", "policy__policy_number").distinct(),
    }
    return render(request, "claims/claim_list.html", context)


# ========================
# Edit, Detail, Approve, Reject, Reimburse
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
    return render(request, "claims/edit_claim.html", {"dashboard_title": f"Edit Claim - {claim.claim_number}", "claim": claim, "role": getattr(request.user, "role", "guest")})

@login_required
def claim_detail(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    user = request.user
    role = getattr(user, "role", None)

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

    clinical_events = claim.clinical_events.select_related("hospital", "client").all()
    risk_scores = RiskScore.objects.filter(event__in=clinical_events)

    return render(request, "claims/claim_detail.html", {
        "claim": claim,
        "clinical_events": clinical_events,
        "risk_scores": risk_scores,
        "dashboard_title": f"Claim Details - {claim.claim_number}",
        "role": role,
    })


@login_required
@roles_required("admin", "claim_officer", "finance")
@require_POST
def approve_claim(request, pk):
    claim = get_object_or_404(Claim, pk=pk)
    try:
        if claim.status != "approved":
            claim.approve_claim(user=request.user)
            messages.success(request, f"Claim {claim.claim_number} approved successfully.")
        else:
            messages.info(request, f"Claim {claim.claim_number} is already approved.")
    except ValidationError as e:
        messages.error(request, e.message)
    return redirect("claims:claim_detail", pk=pk)


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
    
from rest_framework import viewsets
from .models import Claim
from .serializers import ClaimSerializer

class ClaimViewSet(viewsets.ModelViewSet):
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer
