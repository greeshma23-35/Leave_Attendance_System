from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Attendance(models.Model):
    """One row per employee per calendar day.

    `check_in` / `check_out` are populated by the employee themselves via
    the check-in/check-out actions; `status` can additionally be set or
    corrected by a manager/admin (e.g. marking someone ABSENT or HALF_DAY).
    """

    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        HALF_DAY = 'HALF_DAY', 'Half Day'
        ON_LEAVE = 'ON_LEAVE', 'On Leave'
        HOLIDAY = 'HOLIDAY', 'Holiday'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance_records',
    )
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    remarks = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attendance_marked', help_text='Set when a manager/admin manually corrects a record.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ('user', 'date')
        indexes = [models.Index(fields=['user', 'date'])]

    def __str__(self):
        return f'{self.user.employee_id} - {self.date} - {self.status}'

    def clean(self):
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError('Check-out time must be after check-in time.')
