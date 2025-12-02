from django.contrib.auth import get_user_model
from django.db import models
from django.conf import settings
from django.utils import timezone
from clients.models import Client

User = get_user_model()

class Hospital(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='hospital_profile',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255)
    language = models.CharField(max_length=100, default='English')
    owner_first_name = models.CharField(max_length=100)
    owner_last_name = models.CharField(max_length=100)
    email = models.EmailField()
    currency = models.CharField(max_length=10, default='USD')
    mobile = models.CharField(max_length=20, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    country = models.CharField(max_length=50, blank=True, null=True)
    image = models.ImageField(upload_to='hospitals/', blank=True, null=True)
    
    verified = models.BooleanField(default=False)
    
    # ----------------------
    # Shariah Compliance
    # ----------------------
    shariah_approved = models.BooleanField(default=False, help_text="Approved by Shariah board")
    shariah_review_notes = models.TextField(blank=True, null=True)

    # ----------------------
    # Audit fields
    # ----------------------
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_hospitals'
    )

    def __str__(self):
        return self.name

    # ----------------------
    # Shariah Workflow Methods
    # ----------------------
    def approve_shariah(self, reviewer=None, notes=None):
        self.shariah_approved = True
        if notes:
            self.shariah_review_notes = notes
        self.save(update_fields=["shariah_approved", "shariah_review_notes"])

class HospitalAssignment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("claimed", "Claim Submitted"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="hospital_assignments"
    )
    policy = models.ForeignKey(
        "policies.Policy",
        on_delete=models.CASCADE,
        related_name="hospital_assignments"
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE,
        related_name="assigned_clients"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_hospital_tasks"
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField(blank=True, null=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional link to a claim
    claim = models.OneToOneField(
        "claims.Claim",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment"
    )

    # ----------------------
    # Shariah Compliance
    # ----------------------
    shariah_approved = models.BooleanField(default=False, help_text="Approved by Shariah board")
    shariah_review_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.client.full_name} → {self.hospital.name}"

    # ----------------------
    # Workflow Helpers
    # ----------------------
    @property
    def workflow_status(self):
        if not self.shariah_approved:
            return "pending_shariah_approval"
        return self.status

    def approve_shariah(self, reviewer=None, notes=None):
        self.shariah_approved = True
        if notes:
            self.shariah_review_notes = notes
        self.save(update_fields=["shariah_approved", "shariah_review_notes", "updated_at"])

    def mark_completed(self):
        if not self.shariah_approved:
            raise ValueError("Cannot complete assignment without Shariah approval")
        self.status = "completed"
        self.save(update_fields=["status", "updated_at"])
