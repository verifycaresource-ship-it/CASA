from django.contrib.auth import get_user_model
from django.db import models
from django.conf import settings  # ✅ Add this line
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


# hospitals/models.py

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
        "hospitals.Hospital",
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

    # 🧾 NEW: track assignment’s overall progress
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    notes = models.TextField(blank=True, null=True)
    assigned_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # 🆕 NEW: link to Claim (optional, but very helpful)
    claim = models.OneToOneField(
        "claims.Claim",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment"
    )

    def __str__(self):
        return f"{self.client.full_name} → {self.hospital.name}"

