from django.db import models
from django.conf import settings
from django.utils import timezone
from clients.models import Client
from policies.models import Policy
from hospitals.models import Hospital
from django.core.exceptions import ValidationError

class Claim(models.Model):
    CLAIM_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('reimbursed', 'Reimbursed'),
    ]

    claim_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=CLAIM_STATUS, default='pending')
    document = models.FileField(upload_to='claims/documents/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    # ----------------------
    # Shariah Compliance
    # ----------------------
    shariah_approved = models.BooleanField(default=False, help_text="Approved by Shariah board")
    shariah_review_notes = models.TextField(blank=True, null=True)

    # ----------------------
    # Auditing
    # ----------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.claim_number} - {self.client.full_name}"

    # ----------------------
    # Workflow Properties
    # ----------------------
    @property
    def workflow_status(self):
        """
        Return status considering Shariah approval:
        - Pending Shariah approval
        - Pending claim approval
        - Approved / Rejected / Reimbursed
        """
        if not self.shariah_approved:
            return "pending_shariah_approval"
        return self.status

    # ----------------------
    # Workflow Methods
    # ----------------------
    def approve_shariah(self, reviewer=None, notes=None):
        """Mark claim as approved by Shariah board."""
        self.shariah_approved = True
        if notes:
            self.shariah_review_notes = notes
        self.save(update_fields=["shariah_approved", "shariah_review_notes", "updated_at"])

    def approve_claim(self):
        """Approve claim only if Shariah approved."""
        if not self.shariah_approved:
            raise ValidationError("Claim must be approved by Shariah board first")
        self.status = "approved"
        self.save(update_fields=["status", "updated_at"])

    def reject_claim(self, notes=None):
        """Reject claim, optionally add notes."""
        self.status = "rejected"
        if notes:
            self.notes = notes
        self.save(update_fields=["status", "notes", "updated_at"])

    def mark_reimbursed(self):
        """Mark claim as reimbursed. Only possible if approved."""
        if self.status != "approved":
            raise ValidationError("Only approved claims can be reimbursed")
        self.status = "reimbursed"
        self.save(update_fields=["status", "updated_at"])
