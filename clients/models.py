from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.core.validators import RegexValidator
import secrets

# ==============================
# Client (Policyholder / Guardian)
# ==============================
class Client(models.Model):
    GENDER_CHOICES = [("male", "Male"), ("female", "Female"), ("other", "Other")]
    STATUS_CHOICES = [("pending", "Pending"), ("verified", "Verified"), ("failed", "Failed")]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(
        max_length=20, blank=True, null=True,
        validators=[RegexValidator(r'^\+?1?\d{9,15}$', "Enter valid phone number")]
    )
    email = models.EmailField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to="clients/photos/", blank=True, null=True)
    fingerprint_data = models.BinaryField(blank=True, null=True, editable=False)
    fingerprint_verified = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    nric_or_passport = models.CharField(max_length=50, blank=True, null=True)
    shariah_verified = models.BooleanField(default=False)
    shariah_review_notes = models.TextField(blank=True, null=True)

    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="registered_clients"
    )
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_clients"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        if self.dob:
            today = timezone.now().date()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None

    @property
    def photo_url(self):
        if self.photo:
            return self.photo.url
        return "/static/images/default-avatar.png"

    @property
    def compliance_status(self):
        if not self.shariah_verified:
            return "pending_shariah_verification"
        return self.status

    def verify_shariah(self, reviewer=None, notes=None):
        self.shariah_verified = True
        if notes:
            self.shariah_review_notes = notes
        self.save(update_fields=["shariah_verified", "shariah_review_notes", "updated_at"])

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def get_absolute_url(self):
        return reverse("clients:client_detail", args=[str(self.id)])


# ==============================
# Patient (Child / Maternal Record)
# ==============================
class Patient(models.Model):
    TYPE_CHOICES = [("child", "Child"), ("maternal", "Maternal")]
    GENDER_CHOICES = [("male", "Male"), ("female", "Female")]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="patients")
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    patient_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="child")
    photo = models.ImageField(upload_to="patients/photos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.patient_type})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        if self.dob:
            today = timezone.now().date()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None

    @property
    def photo_url(self):
        if self.photo:
            return self.photo.url
        return "/static/images/default-patient.png"


# ==============================
# WebAuthn / Fingerprint
# ==============================
class WebAuthnCredential(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name="webauthn_credential")
    credential_id = models.CharField(max_length=255, unique=True)
    public_key = models.TextField()
    sign_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"WebAuthn Credential for {self.client.full_name}"


# ==============================
# Client Verification Token
# ==============================
class ClientVerificationToken(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="verification_tokens")
    token = models.CharField(max_length=32, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(16)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        return timezone.now() < self.expires_at

