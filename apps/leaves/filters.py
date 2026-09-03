import django_filters

from .models import LeaveRequest


class LeaveRequestFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')

    class Meta:
        model = LeaveRequest
        fields = ['user', 'leave_type', 'status', 'date_from', 'date_to']
