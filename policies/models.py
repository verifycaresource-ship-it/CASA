from django.db import models
from django.conf import settings
from django.utils import timezone
from clients.models import Client


# ---------------------------
# GLOBAL CHOICES
# ---------------------------
GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
]

PAYMENT_MODE_CHOICES = [
    ("annual", "Annual"),
    ("semi_annual", "Semi-Annual"),
    ("monthly", "Monthly"),
]

COVERAGE_LEVEL_CHOICES = [
    ("bronze", "Bronze"),
    ("silver", "Silver"),
    ("gold", "Gold"),
    ("platinum", "Platinum"),
]


# ---------------------------
# POLICY MODEL
# ---------------------------
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

    policy_number = models.CharField(max_length=50, unique=True, db_index=True)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE, db_index=True)

    # New fields
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default="annual")
    coverage_level = models.CharField(max_length=20, choices=COVERAGE_LEVEL_CHOICES, default="bronze")
    nric_or_passport = models.CharField(max_length=50, blank=True, null=True)

    coverage_details = models.TextField(blank=True, null=True)
    premium = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    start_date = models.DateField(db_index=True)
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True, db_index=True)
    max_claim_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    waiting_period_days = models.PositiveIntegerField(default=0)
    deductible = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.policy_number

    # ---------------------------
    # STATUS HELPERS
    # ---------------------------
    @property
    def days_left(self):
        if self.expiry_date:
            return (self.expiry_date - timezone.now().date()).days
        return None

    @property
    def expired_days(self):
        if self.days_left is not None and self.days_left < 0:
            return abs(self.days_left)
        return 0

    @property
    def status(self):
        today = timezone.now().date()
        if self.expiry_date and self.expiry_date < today:
            return "expired"
        if self.is_active:
            return "active"
        return "inactive"


# ---------------------------
# INSURED PERSON MODEL
# ---------------------------
class InsuredPerson(models.Model):
    policy = models.ForeignKey("Policy", on_delete=models.CASCADE, related_name="insured_persons")

    full_name = models.CharField(max_length=255)
    dob = models.DateField()
    relationship = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    photo = models.ImageField(upload_to="insured/photos/", blank=True, null=True)

    fingerprint_data = models.BinaryField(blank=True, null=True)
    fingerprint_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.relationship})"

    @property
    def age(self):
        today = timezone.now().date()
        return (today.year - self.dob.year
                - ((today.month, today.day) < (self.dob.month, self.dob.day)))

    @property
    def is_adult(self):
        return self.age >= 18
    
def save(self, *args, **kwargs):
    if self.expiry_date and self.expiry_date < timezone.now().date():
        self.is_active = False
    super().save(*args, **kwargs)
