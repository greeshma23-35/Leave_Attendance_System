from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.attendance.models import Attendance
from common.exceptions import ApplicationError
from common.permissions import IsManagerOrAdmin, ReadOnlyOrAdmin

from .filters import LeaveRequestFilter
from .models import LeaveBalance, LeaveRequest, LeaveType
from .serializers import (
    LeaveBalanceSerializer,
    LeaveRequestSerializer,
    LeaveReviewSerializer,
    LeaveTypeSerializer,
)


class LeaveTypeViewSet(viewsets.ModelViewSet):
    """Everyone authenticated can view leave types; only admins manage them."""

    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated, ReadOnlyOrAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']


class LeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only. Employees see their own; managers see their team's; admins see all."""

    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'leave_type', 'year']
    ordering_fields = ['year']

    def get_queryset(self):
        user = self.request.user
        qs = LeaveBalance.objects.select_related('user', 'leave_type')
        if user.is_superuser or user.role == User.Role.ADMIN:
            return qs.all()
        if user.role == User.Role.MANAGER:
            return qs.filter(Q(user=user) | Q(user__manager=user))
        return qs.filter(user=user)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    Employees: create/list/retrieve their own requests; cancel a pending one.
    Managers: view + approve/reject requests from their direct reports.
    Admins: full visibility and control over every request.
    """

    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LeaveRequestFilter
    search_fields = ['user__first_name', 'user__last_name', 'user__employee_id', 'reason']
    ordering_fields = ['applied_on', 'start_date']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        user = self.request.user
        qs = LeaveRequest.objects.select_related('user', 'leave_type', 'reviewed_by')
        if user.is_superuser or user.role == User.Role.ADMIN:
            return qs.all()
        if user.role == User.Role.MANAGER:
            return qs.filter(Q(user=user) | Q(user__manager=user))
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """An employee can withdraw their own request while it's still pending."""
        leave_request = self.get_object()
        if leave_request.user != request.user:
            raise ApplicationError('You can only cancel your own leave request.', code='forbidden', status_code=status.HTTP_403_FORBIDDEN)
        if leave_request.status != LeaveRequest.Status.PENDING:
            raise ApplicationError('Only pending requests can be cancelled.', code='invalid_state')

        leave_request.status = LeaveRequest.Status.CANCELLED
        leave_request.reviewed_on = timezone.now()
        leave_request.save()
        return Response(LeaveRequestSerializer(leave_request).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsManagerOrAdmin])
    def approve(self, request, pk=None):
        leave_request = self._get_reviewable_request(request, pk)
        review_serializer = LeaveReviewSerializer(data=request.data)
        review_serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            balance = LeaveBalance.objects.select_for_update().get(
                user=leave_request.user, leave_type=leave_request.leave_type, year=leave_request.start_date.year,
            )
            if leave_request.total_days > balance.remaining_days:
                raise ApplicationError('Employee no longer has sufficient leave balance for this request.')

            balance.used_days += leave_request.total_days
            balance.save()

            leave_request.status = LeaveRequest.Status.APPROVED
            leave_request.reviewed_by = request.user
            leave_request.reviewed_on = timezone.now()
            leave_request.review_comment = review_serializer.validated_data.get('comment', '')
            leave_request.save()

            self._mark_attendance_on_leave(leave_request)

        return Response(LeaveRequestSerializer(leave_request).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsManagerOrAdmin])
    def reject(self, request, pk=None):
        leave_request = self._get_reviewable_request(request, pk)
        review_serializer = LeaveReviewSerializer(data=request.data)
        review_serializer.is_valid(raise_exception=True)

        leave_request.status = LeaveRequest.Status.REJECTED
        leave_request.reviewed_by = request.user
        leave_request.reviewed_on = timezone.now()
        leave_request.review_comment = review_serializer.validated_data.get('comment', '')
        leave_request.save()
        return Response(LeaveRequestSerializer(leave_request).data)

    def _get_reviewable_request(self, request, pk):
        leave_request = self.get_object()
        if leave_request.status != LeaveRequest.Status.PENDING:
            raise ApplicationError('Only pending requests can be reviewed.', code='invalid_state')

        reviewer = request.user
        is_admin = reviewer.is_superuser or reviewer.role == User.Role.ADMIN
        is_their_manager = leave_request.user.manager_id == reviewer.id
        if not (is_admin or is_their_manager):
            raise ApplicationError(
                'You can only review leave requests from your direct reports.',
                code='forbidden', status_code=status.HTTP_403_FORBIDDEN,
            )
        return leave_request

    @staticmethod
    def _mark_attendance_on_leave(leave_request):
        """Auto-create ON_LEAVE attendance rows for every day of an approved leave."""
        current = leave_request.start_date
        while current <= leave_request.end_date:
            Attendance.objects.update_or_create(
                user=leave_request.user, date=current,
                defaults={'status': Attendance.Status.ON_LEAVE},
            )
            current += timedelta(days=1)
