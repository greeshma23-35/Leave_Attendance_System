from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveBalance, LeaveRequest, LeaveType


class LeaveRequestWorkflowTests(APITestCase):
    def setUp(self):
        self.password = 'StrongPass123'
        self.leave_type = LeaveType.objects.create(name='Casual Leave', max_days_per_year=12)

        self.manager = User.objects.create_user(
            email='mgr@example.com', password=self.password,
            employee_id='MGR300', first_name='Man', last_name='Ager', role=User.Role.MANAGER,
        )
        self.employee = User.objects.create_user(
            email='emp@example.com', password=self.password,
            employee_id='EMP300', first_name='Em', last_name='Ployee', manager=self.manager,
        )
        self.other_manager = User.objects.create_user(
            email='mgr2@example.com', password=self.password,
            employee_id='MGR301', first_name='Man2', last_name='Ager2', role=User.Role.MANAGER,
        )

        # The signal auto-creates a balance; make sure it's what we expect.
        self.balance = LeaveBalance.objects.get(
            user=self.employee, leave_type=self.leave_type, year=timezone.now().year,
        )
        self.balance.allocated_days = 10
        self.balance.save()

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def _apply_for_leave(self, days=2, start_offset=1):
        start = timezone.localdate() + timedelta(days=start_offset)
        end = start + timedelta(days=days - 1)
        url = reverse('leave-request-list')
        payload = {
            'leave_type': self.leave_type.id,
            'start_date': str(start),
            'end_date': str(end),
            'reason': 'Personal work',
        }
        return self.client.post(url, payload)

    def test_employee_can_apply_for_leave(self):
        self.authenticate(self.employee)
        response = self._apply_for_leave(days=2)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'PENDING')
        self.assertEqual(response.data['total_days'], 2)

    def test_cannot_apply_beyond_remaining_balance(self):
        self.authenticate(self.employee)
        response = self._apply_for_leave(days=99)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_apply_for_overlapping_dates(self):
        self.authenticate(self.employee)
        self._apply_for_leave(days=3, start_offset=5)
        response = self._apply_for_leave(days=2, start_offset=6)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_can_approve_team_request_and_balance_updates(self):
        self.authenticate(self.employee)
        create_response = self._apply_for_leave(days=3)
        request_id = create_response.data['id']

        self.authenticate(self.manager)
        url = reverse('leave-request-approve', args=[request_id])
        response = self.client.post(url, {'comment': 'Approved, enjoy!'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'APPROVED')

        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, 3)

        leave_request = LeaveRequest.objects.get(id=request_id)
        attendance_days = Attendance.objects.filter(
            user=self.employee, date__range=(leave_request.start_date, leave_request.end_date),
        )
        self.assertEqual(attendance_days.count(), 3)
        self.assertTrue(all(a.status == 'ON_LEAVE' for a in attendance_days))

    def test_manager_cannot_approve_request_outside_their_team(self):
        self.authenticate(self.employee)
        create_response = self._apply_for_leave(days=2)
        request_id = create_response.data['id']

        self.authenticate(self.other_manager)
        url = reverse('leave-request-approve', args=[request_id])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_reject_team_request(self):
        self.authenticate(self.employee)
        create_response = self._apply_for_leave(days=2)
        request_id = create_response.data['id']

        self.authenticate(self.manager)
        url = reverse('leave-request-reject', args=[request_id])
        response = self.client.post(url, {'comment': 'Not enough coverage that week'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'REJECTED')

        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, 0)

    def test_employee_can_cancel_own_pending_request(self):
        self.authenticate(self.employee)
        create_response = self._apply_for_leave(days=2)
        request_id = create_response.data['id']

        url = reverse('leave-request-cancel', args=[request_id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'CANCELLED')

    def test_employee_cannot_cancel_another_employees_request(self):
        self.authenticate(self.employee)
        create_response = self._apply_for_leave(days=2)
        request_id = create_response.data['id']

        intruder = User.objects.create_user(
            email='intruder@example.com', password=self.password,
            employee_id='EMP301', first_name='In', last_name='Truder',
        )
        self.authenticate(intruder)
        url = reverse('leave-request-cancel', args=[request_id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_only_sees_own_leave_requests(self):
        self.authenticate(self.employee)
        self._apply_for_leave(days=1)

        other_employee = User.objects.create_user(
            email='other@example.com', password=self.password,
            employee_id='EMP302', first_name='Ot', last_name='Her',
        )
        self.authenticate(other_employee)
        response = self.client.get(reverse('leave-request-list'))
        self.assertEqual(response.data['count'], 0)
