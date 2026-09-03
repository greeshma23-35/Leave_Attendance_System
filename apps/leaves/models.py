from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class LeaveType(models.Model):
    """A category of leave an organization offers, e.g. Casual, Sick, Earned."""

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    max_days_per_year = models.PositiveIntegerField(default=12)
    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    """How many days of a given leave type a user has left for a given year."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_balances',
    )
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='balances')
    year = models.PositiveIntegerField(default=timezone.now().year)
    allocated_days = models.PositiveIntegerField(default=0)
    used_days = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'leave_type', 'year')
        ordering = ['-year', 'leave_type__name']

    def __str__(self):
        return f'{self.user.employee_id} - {self.leave_type.name} ({self.year})'

    @property
    def remaining_days(self):
        return max(self.allocated_days - self.used_days, 0)


class LeaveRequest(models.Model):
    """A single application for leave, moving through a small approval workflow."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_requests',
    )
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name='requests')
    start_date = models.DateField()
    end_date = models.DateField()
    total_days = models.PositiveIntegerField(editable=False, default=0)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    applied_on = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='leave_reviews',
    )
    reviewed_on = models.DateTimeField(null=True, blank=True)
    review_comment = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-applied_on']
        indexes = [models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f'{self.user.employee_id} - {self.leave_type.name} ({self.start_date} to {self.end_date})'

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError('End date cannot be before start date.')

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.total_days = (self.end_date - self.start_date).days + 1
        super().save(*args, **kwargs)
