from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'check_in', 'check_out', 'status', 'marked_by']
    list_filter = ['status', 'date']
    search_fields = ['user__first_name', 'user__last_name', 'user__employee_id']
    date_hierarchy = 'date'
