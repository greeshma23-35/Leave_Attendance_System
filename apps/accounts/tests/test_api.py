from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User


class AuthAPITests(APITestCase):
    def setUp(self):
        self.password = 'StrongPass123'
        self.employee = User.objects.create_user(
            email='emp@example.com', password=self.password,
            employee_id='EMP100', first_name='Em', last_name='Ployee',
        )

    def test_login_returns_access_and_refresh_tokens(self):
        url = reverse('token_obtain_pair')
        response = self.client.post(url, {'email': self.employee.email, 'password': self.password})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], self.employee.email)

    def test_login_fails_with_wrong_password(self):
        url = reverse('token_obtain_pair')
        response = self.client.post(url, {'email': self.employee.email, 'password': 'wrong'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserManagementAPITests(APITestCase):
    def setUp(self):
        self.password = 'StrongPass123'
        self.admin = User.objects.create_superuser(
            email='admin@example.com', password=self.password,
            employee_id='ADM100', first_name='Ad', last_name='Min',
        )
        self.manager = User.objects.create_user(
            email='mgr@example.com', password=self.password,
            employee_id='MGR100', first_name='Man', last_name='Ager', role=User.Role.MANAGER,
        )
        self.employee = User.objects.create_user(
            email='emp@example.com', password=self.password,
            employee_id='EMP100', first_name='Em', last_name='Ployee', manager=self.manager,
        )
        self.other_employee = User.objects.create_user(
            email='emp2@example.com', password=self.password,
            employee_id='EMP101', first_name='Em2', last_name='Ployee2',
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_employee_cannot_create_user(self):
        self.authenticate(self.employee)
        url = reverse('user-list')
        payload = {
            'employee_id': 'EMP999', 'email': 'new@example.com', 'password': 'StrongPass123',
            'first_name': 'New', 'last_name': 'Guy',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_user(self):
        self.authenticate(self.admin)
        url = reverse('user-list')
        payload = {
            'employee_id': 'EMP999', 'email': 'new@example.com', 'password': 'StrongPass123',
            'first_name': 'New', 'last_name': 'Guy',
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_manager_sees_only_self_and_direct_reports(self):
        self.authenticate(self.manager)
        url = reverse('user-list')
        response = self.client.get(url)
        emails = {item['email'] for item in response.data['results']}
        self.assertIn(self.manager.email, emails)
        self.assertIn(self.employee.email, emails)
        self.assertNotIn(self.other_employee.email, emails)

    def test_employee_sees_only_self(self):
        self.authenticate(self.employee)
        url = reverse('user-list')
        response = self.client.get(url)
        emails = {item['email'] for item in response.data['results']}
        self.assertEqual(emails, {self.employee.email})

    def test_my_profile_returns_current_user(self):
        self.authenticate(self.employee)
        url = reverse('my_profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.employee.email)

    def test_employee_cannot_escalate_own_role_via_profile(self):
        self.authenticate(self.employee)
        url = reverse('my_profile')
        response = self.client.patch(url, {'role': 'ADMIN'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.role, User.Role.EMPLOYEE)

    def test_change_password(self):
        self.authenticate(self.employee)
        url = reverse('change_password')
        response = self.client.post(url, {'old_password': self.password, 'new_password': 'NewStrongPass456'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password('NewStrongPass456'))

    def test_unauthenticated_request_is_rejected(self):
        url = reverse('user-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
