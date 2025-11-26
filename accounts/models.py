from django.contrib.auth.models import AbstractUser
from django.db import models

GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
]

class User(AbstractUser):
    """
    Custom User model with role-based access for Health Insurance platform.
    Admins can suspend users, assign roles, and manage access.
    """
    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("agent", "Agent"),
        ("policyholder", "Policyholder"),
        ("claim_officer", "Claim Officer"),
        ("finance_officer", "Finance Officer"),
        ("report_officer", "Report Officer"),
        ("hospital", "Hospital"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="policyholder",
        help_text="Role of the user in the system"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to="profiles/", blank=True, null=True, default="profiles/default.png"
    )
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    daamiin = models.CharField(
        max_length=150, blank=True, null=True, help_text="Responsible person for agent"
    )
    is_suspended = models.BooleanField(default=False, help_text="Designates whether this user is suspended.")

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    # -------------------------
    # Helpers
    # -------------------------
    def suspend(self):
        self.is_suspended = True
        self.save(update_fields=["is_suspended"])

    def activate(self):
        self.is_suspended = False
        self.save(update_fields=["is_suspended"])

    def is_active_for_login(self):
        return self.is_active and not self.is_suspended

    # -------------------------
    # Auto-correct role for superuser
    # -------------------------
    def save(self, *args, **kwargs):
        if self.is_superuser and self.role != "admin":
            self.role = "admin"
        super().save(*args, **kwargs)