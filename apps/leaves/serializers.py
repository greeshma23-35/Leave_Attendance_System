from django.utils import timezone
from rest_framework import serializers

from .models import LeaveBalance, LeaveRequest, LeaveType


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'description', 'max_days_per_year', 'requires_approval', 'is_active']


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='user.get_full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveBalance
        fields = [
            'id', 'user', 'employee_name', 'leave_type', 'leave_type_name',
            'year', 'allocated_days', 'used_days', 'remaining_days',
        ]
        read_only_fields = ['id', 'used_days']


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='user.get_full_name', read_only=True)
    employee_id = serializers.CharField(source='user.employee_id', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'user', 'employee_id', 'employee_name', 'leave_type', 'leave_type_name',
            'start_date', 'end_date', 'total_days', 'reason', 'status', 'applied_on',
            'reviewed_by', 'reviewed_by_name', 'reviewed_on', 'review_comment',
        ]
        read_only_fields = [
            'id', 'user', 'total_days', 'status', 'applied_on',
            'reviewed_by', 'reviewed_on',
        ]

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))

        if start_date and end_date:
            if end_date < start_date:
                raise serializers.ValidationError('End date cannot be before start date.')
            if start_date < timezone.localdate() and self.instance is None:
                raise serializers.ValidationError('Cannot apply for leave in the past.')

        return attrs

    def validate_leave_type(self, leave_type):
        if not leave_type.is_active:
            raise serializers.ValidationError('This leave type is no longer active.')
        return leave_type

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        start_date = validated_data['start_date']
        end_date = validated_data['end_date']
        leave_type = validated_data['leave_type']
        requested_days = (end_date - start_date).days + 1

        balance = LeaveBalance.objects.filter(
            user=user, leave_type=leave_type, year=start_date.year,
        ).first()
        if balance is None:
            raise serializers.ValidationError(
                f'No leave balance found for {leave_type.name} in {start_date.year}.'
            )
        if requested_days > balance.remaining_days:
            raise serializers.ValidationError(
                f'Insufficient leave balance. Remaining: {balance.remaining_days} day(s), '
                f'requested: {requested_days} day(s).'
            )

        overlapping = LeaveRequest.objects.filter(
            user=user,
            status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if overlapping.exists():
            raise serializers.ValidationError('You already have a leave request overlapping these dates.')

        validated_data['user'] = user
        return super().create(validated_data)


class LeaveReviewSerializer(serializers.Serializer):
    """Used for the approve/reject actions."""

    comment = serializers.CharField(required=False, allow_blank=True, max_length=255)
