from django.db import models
from django.conf import settings
from django.utils import timezone
from clients.models import Client

class Policy(models.Model):
    POLICY_TYPE = [
        ("individual", "Individual"),
        ("family", "Family"),
        ("employer", "Employer Sponsored"),
        ("ngo", "NGO Supported"),
        ("health", "Health Policy"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="policies")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_policies"
    )
    policy_number = models.CharField(max_length=50, unique=True)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE)
    coverage_details = models.TextField(blank=True, null=True)
    premium = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    start_date = models.DateField()
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)
    max_claim_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    waiting_period_days = models.PositiveIntegerField(default=0)
    deductible = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.policy_number

    @property
    def days_left(self):
        """Returns positive days left or negative if expired."""
        if self.expiry_date:
            return (self.expiry_date - timezone.now().date()).days
        return None

    @property
    def expired_days(self):
        """Returns absolute number of days since expiry, 0 if not expired."""
        if self.days_left is not None and self.days_left < 0:
            return abs(self.days_left)
        return 0

    @property
    def status(self):
        """Return readable status for template: active, expired, or upcoming."""
        if self.expiry_date and self.expiry_date < timezone.now().date():
            return "expired"
        elif self.is_active:
            return "active"
        return "inactive"
