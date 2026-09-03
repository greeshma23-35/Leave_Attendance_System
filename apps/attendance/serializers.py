from django.utils import timezone
from rest_framework import serializers

from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='user.get_full_name', read_only=True)
    employee_id = serializers.CharField(source='user.employee_id', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'user', 'employee_id', 'employee_name', 'date', 'check_in',
            'check_out', 'status', 'remarks', 'marked_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'marked_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        check_in = attrs.get('check_in', getattr(self.instance, 'check_in', None))
        check_out = attrs.get('check_out', getattr(self.instance, 'check_out', None))
        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError('Check-out time must be after check-in time.')
        return attrs


class CheckInSerializer(serializers.Serializer):
    """No input needed - the server stamps the current date/time."""

    def create(self, validated_data):
        user = self.context['request'].user
        today = timezone.localdate()
        attendance, _ = Attendance.objects.get_or_create(
            user=user, date=today, defaults={'status': Attendance.Status.PRESENT},
        )
        if attendance.check_in:
            raise serializers.ValidationError('You have already checked in today.')
        attendance.check_in = timezone.localtime().time()
        attendance.status = Attendance.Status.PRESENT
        attendance.save()
        return attendance


class CheckOutSerializer(serializers.Serializer):
    def create(self, validated_data):
        user = self.context['request'].user
        today = timezone.localdate()
        try:
            attendance = Attendance.objects.get(user=user, date=today)
        except Attendance.DoesNotExist:
            raise serializers.ValidationError('You have not checked in today.')
        if not attendance.check_in:
            raise serializers.ValidationError('You have not checked in today.')
        if attendance.check_out:
            raise serializers.ValidationError('You have already checked out today.')

        now = timezone.localtime().time()
        if now <= attendance.check_in:
            raise serializers.ValidationError('Check-out time must be after check-in time.')

        attendance.check_out = now
        attendance.save()
        return attendance
