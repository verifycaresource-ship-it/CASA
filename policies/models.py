from datetime import date
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
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

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="policies"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_policies"
    )

    policy_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )
    policy_type = models.CharField(
        max_length=20,
        choices=POLICY_TYPE,
        db_index=True
    )
    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        default="annual"
    )
    coverage_level = models.CharField(
        max_length=20,
        choices=COVERAGE_LEVEL_CHOICES,
        default="bronze"
    )

    nric_or_passport = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    coverage_details = models.TextField(
        blank=True,
        null=True
    )

    premium = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    start_date = models.DateField(db_index=True)
    expiry_date = models.DateField(db_index=True)

    max_claim_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    waiting_period_days = models.PositiveIntegerField(default=0)
    deductible = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["policy_number"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["is_active", "is_archived"]),
        ]

    def __str__(self):
        return self.policy_number

    # ---------------------------
    # STATUS HELPERS
    # ---------------------------
    @property
    def days_left(self):
        return (self.expiry_date - timezone.now().date()).days

    @property
    def is_expired(self):
        return self.expiry_date < timezone.now().date()

    @property
    def status(self):
        if self.is_archived:
            return "archived"
        if self.is_expired:
            return "expired"
        if self.is_active:
            return "active"
        return "inactive"

    # ---------------------------
    # VALIDATION & AUTO-ARCHIVE
    # ---------------------------
    def clean(self):
        """
        Ensures correct business rules.
        Django guarantees proper field types here.
        """

        if self.expiry_date and self.start_date:
            if self.expiry_date < self.start_date:
                raise ValidationError({
                    "expiry_date": "Expiry date cannot be earlier than start date."
                })

        # Auto-archive expired policies
        if self.expiry_date and self.expiry_date < timezone.now().date():
            self.is_active = False
            self.is_archived = True

    def save(self, *args, **kwargs):
        # Ensures clean() runs for forms, admin, APIs, and direct saves
        self.full_clean()
        super().save(*args, **kwargs)

    # ---------------------------
    # RENEWAL METHOD
    # ---------------------------
    def renew(self, new_expiry_date, new_premium=None, user=None):
        """
        Renew this policy:
        1. Archive the current policy
        2. Create a new policy with updated expiry
        3. Copy insured persons
        """

        # Archive current policy
        self.is_active = False
        self.is_archived = True
        self.save()

        # Create renewed policy
        renewed_policy = Policy.objects.create(
            client=self.client,
            created_by=user or self.created_by,
            policy_number=f"{self.policy_number}-R{timezone.now().strftime('%Y%m%d%H%M%S')}",
            policy_type=self.policy_type,
            payment_mode=self.payment_mode,
            coverage_level=self.coverage_level,
            nric_or_passport=self.nric_or_passport,
            coverage_details=self.coverage_details,
            premium=new_premium if new_premium is not None else self.premium,
            start_date=timezone.now().date(),
            expiry_date=new_expiry_date,
            max_claim_limit=self.max_claim_limit,
            waiting_period_days=self.waiting_period_days,
            deductible=self.deductible,
            is_active=True,
            is_archived=False
        )

        # Copy insured persons
        for person in self.insured_persons.all():
            person.pk = None
            person.policy = renewed_policy
            person.save()

        # Audit log
        PolicyAudit.objects.create(
            policy=self,
            action="renewed",
            performed_by=user
        )

        return renewed_policy


# ---------------------------
# INSURED PERSON MODEL
# ---------------------------
class InsuredPerson(models.Model):

    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name="insured_persons"
    )

    full_name = models.CharField(max_length=255)
    dob = models.DateField()
    relationship = models.CharField(max_length=50)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    photo = models.ImageField(
        upload_to="insured/photos/",
        blank=True,
        null=True
    )

    fingerprint_data = models.BinaryField(
        blank=True,
        null=True
    )
    fingerprint_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.relationship})"

    @property
    def age(self):
        today = timezone.now().date()
        return (
            today.year
            - self.dob.year
            - ((today.month, today.day) < (self.dob.month, self.dob.day))
        )

    @property
    def is_adult(self):
        return self.age >= 18


# ---------------------------
# POLICY AUDIT MODEL
# ---------------------------
class PolicyAudit(models.Model):

    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name="audits"
    )

    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.policy.policy_number} - {self.action}"

