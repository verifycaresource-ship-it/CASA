from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.timezone import now
import random

GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
]

class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("agent", "Agent"),
        ("policyholder", "Policyholder"),
        ("claim_officer", "Claim Officer"),
        ("finance_officer", "Finance Officer"),
        ("report_officer", "Report Officer"),
        ("hospital", "Hospital"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="policyholder")
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True, default="profiles/default.png")
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    daamiin = models.CharField(max_length=150, blank=True, null=True)
    is_suspended = models.BooleanField(default=False)

    reset_otp = models.CharField(max_length=6, blank=True, null=True)
    reset_otp_expires = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def suspend(self):
        self.is_suspended = True
        self.save(update_fields=["is_suspended"])

    def activate(self):
        self.is_suspended = False
        self.save(update_fields=["is_suspended"])

    def is_active_for_login(self):
        return self.is_active and not self.is_suspended

    def set_otp(self, otp, expires_at):
        self.reset_otp = otp
        self.reset_otp_expires = expires_at
        self.save(update_fields=["reset_otp", "reset_otp_expires"])

    def clear_otp(self):
        self.reset_otp = None
        self.reset_otp_expires = None
        self.save(update_fields=["reset_otp", "reset_otp_expires"])

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = "admin"
        super().save(*args, **kwargs)


from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import now, timedelta

User = get_user_model()

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def is_valid(self):
        return not self.is_used and self.expires_at > now()

    def __str__(self):
        return f"OTP for {self.user.email} - {self.otp}"


