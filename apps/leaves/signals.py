import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import LeaveBalance, LeaveType

logger = logging.getLogger('apps')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_leave_balances_for_new_user(sender, instance, created, **kwargs):
    """When a new employee is onboarded, give them a balance row for every
    active leave type for the current year, so they can apply for leave
    immediately without an admin having to set it up manually.
    """
    if not created:
        return

    year = timezone.now().year
    balances = [
        LeaveBalance(user=instance, leave_type=leave_type, year=year, allocated_days=leave_type.max_days_per_year)
        for leave_type in LeaveType.objects.filter(is_active=True)
    ]
    if balances:
        LeaveBalance.objects.bulk_create(balances, ignore_conflicts=True)
        logger.info('Provisioned %s leave balance(s) for new user %s', len(balances), instance.employee_id)


@receiver(post_save, sender=LeaveType)
def backfill_balances_for_new_leave_type(sender, instance, created, **kwargs):
    """When a new leave type is introduced, retroactively grant every
    currently active employee a balance for it this year.
    """
    if not created or not instance.is_active:
        return

    from apps.accounts.models import User  # local import avoids app-loading cycles

    year = timezone.now().year
    balances = [
        LeaveBalance(user=user, leave_type=instance, year=year, allocated_days=instance.max_days_per_year)
        for user in User.objects.filter(is_active=True)
    ]
    if balances:
        LeaveBalance.objects.bulk_create(balances, ignore_conflicts=True)
        logger.info('Backfilled leave balances for new leave type %s', instance.name)
