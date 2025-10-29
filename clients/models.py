from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse   # ✅ if you ever use get_absolute_url()
from django.core.validators import RegexValidator  # ✅ optional: for phone validation
import json


class Client(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("failed", "Failed"),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', "Enter a valid phone number.")],
    )
    email = models.EmailField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # 🖼️ Client photo
    photo = models.ImageField(upload_to="clients/photos/", blank=True, null=True)

    # 🖐️ Fingerprint data (binary)
    fingerprint_data = models.BinaryField(blank=True, null=True, editable=False)
    fingerprint_verified = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # 👤 Registered and assigned users
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_clients",
        verbose_name="Registered By",
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_clients",
        verbose_name="Assigned Agent",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        """Return the client's full name neatly formatted."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        """Calculate age based on date of birth."""
        if self.dob:
            today = timezone.now().date()
            return today.year - self.dob.year - (
                (today.month, today.day) < (self.dob.month, self.dob.day)
            )
        return None

    @property
    def photo_url(self):
        """Return the photo URL or a default image."""
        if self.photo:
            return self.photo.url
        return "/static/images/default-avatar.png"

    def get_absolute_url(self):
        """Return detail page URL."""
        return reverse("clients:client_detail", args=[str(self.id)])


class WebAuthnCredential(models.Model):
    client = models.OneToOneField(
        "Client",
        on_delete=models.CASCADE,
        related_name="webauthn_credential"
    )
    credential_id = models.CharField(max_length=255, unique=True)
    public_key = models.TextField()
    sign_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"WebAuthn Credential for {self.client.full_name}"
