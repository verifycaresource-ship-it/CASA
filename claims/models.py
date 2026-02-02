from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, FloatField
from django.db.models.functions import Coalesce

from clients.models import Client
from policies.models import Policy, InsuredPerson
from hospitals.models import Hospital

# =======================
# CLAIM MODEL
# =======================
class Claim(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("reimbursed", "Reimbursed"),
    ]

    claim_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="claims")
    patient = models.ForeignKey(InsuredPerson, on_delete=models.SET_NULL, null=True, blank=True, related_name="claims")
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name="claims")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="claims")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    document = models.FileField(upload_to="claims/documents/", blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    # Shariah Compliance
    shariah_approved = models.BooleanField(default=False)
    shariah_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shariah_approvals"
    )
    shariah_review_notes = models.TextField(blank=True, null=True)

    # Financial Approval
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="financial_approvals"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Auditing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        patient_name = f" ({self.patient.full_name})" if self.patient else ""
        return f"{self.claim_number} - {self.client.full_name}{patient_name}"

    # -----------------------
    # Workflow properties
    # -----------------------
    @property
    def workflow_status(self):
        if not self.shariah_approved:
            return "pending_shariah_approval"
        return self.status

    # -----------------------
    # Workflow methods
    # -----------------------
    def approve_shariah(self, reviewer=None, notes=None):
        self.shariah_approved = True
        if reviewer:
            self.shariah_approved_by = reviewer
        if notes:
            self.shariah_review_notes = notes
        self.save(update_fields=["shariah_approved", "shariah_approved_by", "shariah_review_notes", "updated_at"])

    def approve_claim(self, user=None):
        if not self.shariah_approved:
            raise ValidationError("Claim must be approved by Shariah board first")

        if user and not user.groups.filter(name__in=["admin", "claim_officer", "finance"]).exists():
            raise ValidationError("You do not have permission to approve this claim")

        self.status = "approved"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    def reject_claim(self, notes=None):
        self.status = "rejected"
        if notes:
            self.notes = notes
        self.save(update_fields=["status", "notes", "updated_at"])

    def mark_reimbursed(self):
        if self.status != "approved":
            raise ValidationError("Only approved claims can be reimbursed")
        self.status = "reimbursed"
        self.save(update_fields=["status", "updated_at"])


# =======================
# CLINICAL EVENT
# =======================
class ClinicalEvent(models.Model):
    VISIT_TYPES = [
        ("ANC", "Antenatal Care"),
        ("DELIVERY", "Delivery"),
        ("PNC", "Postnatal Care"),
        ("OTHER", "Other"),
    ]

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="clinical_events")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="clinical_events")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="clinical_events")
    patient = models.ForeignKey(InsuredPerson, on_delete=models.SET_NULL, null=True, blank=True, related_name="clinical_events")

    visit_type = models.CharField(max_length=20, choices=VISIT_TYPES)
    event_datetime = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50, default="manual_entry")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-event_datetime"]

    def __str__(self):
        if self.patient:
            return f"{self.patient.full_name} ({self.patient.relationship}) - {self.visit_type} on {self.event_datetime.date()}"
        return f"{self.client.full_name} - {self.visit_type} on {self.event_datetime.date()}"

    @property
    def maternal_risk(self):
        return self.risk_scores.filter(type="maternal").aggregate(
            total=Coalesce(Sum(F("score"), output_field=FloatField()), 0.0)
        )["total"]

    @property
    def neonatal_risk(self):
        return self.risk_scores.filter(type="neonatal").aggregate(
            total=Coalesce(Sum(F("score"), output_field=FloatField()), 0.0)
        )["total"]


# =======================
# HEALTH METRIC
# =======================
class HealthMetric(models.Model):
    CATEGORY_CHOICES = [
        ("maternal", "Maternal"),
        ("delivery", "Delivery"),
        ("postnatal", "Postnatal"),
        ("facility", "Facility"),
        ("risk", "Risk"),
    ]

    event = models.ForeignKey(ClinicalEvent, on_delete=models.CASCADE, related_name="metrics")
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    unit = models.CharField(max_length=20, blank=True, null=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}: {self.value} {self.unit or ''}"


# =======================
# RISK SCORE
# =======================
class RiskScore(models.Model):
    RISK_TYPES = [
        ("maternal", "Maternal"),
        ("neonatal", "Neonatal"),
    ]

    LEVEL_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    ]

    event = models.ForeignKey(ClinicalEvent, on_delete=models.CASCADE, related_name="risk_scores")
    type = models.CharField(max_length=20, choices=RISK_TYPES)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} Risk: {self.score} ({self.level})"
