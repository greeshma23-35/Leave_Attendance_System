from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from common.permissions import IsManagerOrAdmin

from .filters import AttendanceFilter
from .models import Attendance
from .serializers import AttendanceSerializer, CheckInSerializer, CheckOutSerializer


class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Employees: view their own attendance history; cannot edit past records
    directly (they must use /check-in/ and /check-out/).
    Managers: view + correct attendance for their direct reports.
    Admins: full access to every record.
    """

    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AttendanceFilter
    search_fields = ['user__first_name', 'user__last_name', 'user__employee_id']
    ordering_fields = ['date', 'created_at']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsManagerOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == User.Role.ADMIN:
            return Attendance.objects.select_related('user', 'marked_by').all()
        if user.role == User.Role.MANAGER:
            return Attendance.objects.select_related('user', 'marked_by').filter(
                Q(user=user) | Q(user__manager=user)
            )
        return Attendance.objects.select_related('user', 'marked_by').filter(user=user)

    def perform_create(self, serializer):
        serializer.save(marked_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(marked_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='check-in')
    def check_in(self, request):
        serializer = CheckInSerializer(data={}, context={'request': request})
        serializer.is_valid(raise_exception=True)
        attendance = serializer.save()
        return Response(AttendanceSerializer(attendance).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='check-out')
    def check_out(self, request):
        serializer = CheckOutSerializer(data={}, context={'request': request})
        serializer.is_valid(raise_exception=True)
        attendance = serializer.save()
        return Response(AttendanceSerializer(attendance).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='my-summary')
    def my_summary(self, request):
        """Quick present/absent/leave day counts for the current user."""
        qs = Attendance.objects.filter(user=request.user)
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        if year:
            qs = qs.filter(date__year=year)
        if month:
            qs = qs.filter(date__month=month)

        summary = {choice: qs.filter(status=choice).count() for choice, _ in Attendance.Status.choices}
        summary['total_records'] = qs.count()
        return Response(summary)
