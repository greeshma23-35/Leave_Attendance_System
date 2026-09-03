from django.contrib import admin

from .models import LeaveBalance, LeaveRequest, LeaveType


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_days_per_year', 'requires_approval', 'is_active']
    search_fields = ['name']


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'leave_type', 'year', 'allocated_days', 'used_days', 'remaining_days']
    list_filter = ['leave_type', 'year']
    search_fields = ['user__first_name', 'user__last_name', 'user__employee_id']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'leave_type', 'start_date', 'end_date', 'total_days', 'status', 'reviewed_by']
    list_filter = ['status', 'leave_type']
    search_fields = ['user__first_name', 'user__last_name', 'user__employee_id']
    date_hierarchy = 'start_date'
