from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import FloatField
from django.db.models.functions import Coalesce
from django.db.models import Sum, F

from clients.models import Client
from policies.models import Policy
from hospitals.models import Hospital


# =======================
# CLAIM MODEL
# =======================
class Claim(models.Model):
    CLAIM_STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("reimbursed", "Reimbursed"),
    ]

    claim_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=CLAIM_STATUS, default="pending")
    document = models.FileField(upload_to="claims/documents/", blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Shariah Compliance
    shariah_approved = models.BooleanField(default=False, help_text="Approved by Shariah board")
    shariah_review_notes = models.TextField(blank=True, null=True)

    # Auditing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.claim_number} - {self.client.full_name}"

    # Workflow Property
    @property
    def workflow_status(self):
        if not self.shariah_approved:
            return "pending_shariah_approval"
        return self.status

    # Workflow Methods
    def approve_shariah(self, reviewer=None, notes=None):
        self.shariah_approved = True
        if notes:
            self.shariah_review_notes = notes
        self.save(update_fields=["shariah_approved", "shariah_review_notes", "updated_at"])

    def approve_claim(self):
        if not self.shariah_approved:
            raise ValidationError("Claim must be approved by Shariah board first")
        self.status = "approved"
        self.save(update_fields=["status", "updated_at"])

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
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    visit_type = models.CharField(max_length=20, choices=VISIT_TYPES)
    event_datetime = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50, default="manual_entry")  # e.g., claim_submission
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-event_datetime"]

    def __str__(self):
        return f"{self.client.full_name} - {self.visit_type} on {self.event_datetime.date()}"

    # Convenience: total risk score per event
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
