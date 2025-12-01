from django.db import models
from django.conf import settings
from django.utils import timezone

class Task(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_OVERDUE = 'overdue'

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_OVERDUE, 'Overdue'),
    ]

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High")
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    due_date = models.DateField(null=True, blank=True)
    week = models.PositiveIntegerField(default=1)

    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['week', 'due_date', 'status']
        verbose_name = "Task"
        verbose_name_plural = "Tasks"

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return self.status == self.STATUS_OVERDUE

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.save()

    def save(self, *args, **kwargs):
        if (
            self.due_date
            and self.status != self.STATUS_COMPLETED
            and self.due_date < timezone.now().date()
        ):
            self.status = self.STATUS_OVERDUE

        super().save(*args, **kwargs)
