from datetime import time

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.attendance.models import Attendance


class AttendanceAPITests(APITestCase):
    def setUp(self):
        self.password = 'StrongPass123'
        self.manager = User.objects.create_user(
            email='mgr@example.com', password=self.password,
            employee_id='MGR200', first_name='Man', last_name='Ager', role=User.Role.MANAGER,
        )
        self.employee = User.objects.create_user(
            email='emp@example.com', password=self.password,
            employee_id='EMP200', first_name='Em', last_name='Ployee', manager=self.manager,
        )
        self.other_employee = User.objects.create_user(
            email='emp2@example.com', password=self.password,
            employee_id='EMP201', first_name='Em2', last_name='Ployee2',
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_employee_check_in_creates_record(self):
        self.authenticate(self.employee)
        url = reverse('attendance-check-in')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['check_in'])

        record = Attendance.objects.get(user=self.employee, date=timezone.localdate())
        self.assertIsNotNone(record.check_in)

    def test_double_check_in_is_rejected(self):
        self.authenticate(self.employee)
        url = reverse('attendance-check-in')
        self.client.post(url)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_out_before_check_in_is_rejected(self):
        self.authenticate(self.employee)
        url = reverse('attendance-check-out')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_check_in_then_check_out_flow(self):
        self.authenticate(self.employee)
        self.client.post(reverse('attendance-check-in'))
        response = self.client.post(reverse('attendance-check-out'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['check_out'])

    def test_employee_cannot_view_other_employee_attendance(self):
        Attendance.objects.create(
            user=self.other_employee, date=timezone.localdate(),
            check_in=time(9, 0), status=Attendance.Status.PRESENT,
        )
        self.authenticate(self.employee)
        url = reverse('attendance-list')
        response = self.client.get(url)
        ids = {item['id'] for item in response.data['results']}
        other_record = Attendance.objects.get(user=self.other_employee)
        self.assertNotIn(other_record.id, ids)

    def test_manager_can_view_team_attendance(self):
        Attendance.objects.create(
            user=self.employee, date=timezone.localdate(),
            check_in=time(9, 0), status=Attendance.Status.PRESENT,
        )
        self.authenticate(self.manager)
        url = reverse('attendance-list')
        response = self.client.get(url)
        emp_ids = {item['employee_id'] for item in response.data['results']}
        self.assertIn(self.employee.employee_id, emp_ids)

    def test_employee_cannot_manually_correct_attendance(self):
        record = Attendance.objects.create(
            user=self.employee, date=timezone.localdate(), status=Attendance.Status.PRESENT,
        )
        self.authenticate(self.employee)
        url = reverse('attendance-detail', args=[record.id])
        response = self.client.patch(url, {'status': 'ABSENT'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_correct_team_attendance(self):
        record = Attendance.objects.create(
            user=self.employee, date=timezone.localdate(), status=Attendance.Status.PRESENT,
        )
        self.authenticate(self.manager)
        url = reverse('attendance-detail', args=[record.id])
        response = self.client.patch(url, {'status': 'HALF_DAY'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertEqual(record.status, 'HALF_DAY')
