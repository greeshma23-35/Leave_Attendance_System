from django.test import TestCase

from apps.accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_sets_default_role_employee(self):
        user = User.objects.create_user(
            email='employee@example.com', password='StrongPass123',
            employee_id='EMP001', first_name='Jane', last_name='Doe',
        )
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertTrue(user.check_password('StrongPass123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser_sets_admin_role_and_flags(self):
        admin = User.objects.create_superuser(
            email='admin@example.com', password='StrongPass123',
            employee_id='ADM001', first_name='Ada', last_name='Min',
        )
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_str_representation(self):
        user = User.objects.create_user(
            email='jd@example.com', password='StrongPass123',
            employee_id='EMP002', first_name='John', last_name='Doe',
        )
        self.assertIn('John Doe', str(user))
        self.assertIn('EMP002', str(user))

    def test_manager_relationship(self):
        manager = User.objects.create_user(
            email='mgr@example.com', password='StrongPass123',
            employee_id='MGR001', first_name='Mia', last_name='Ger', role=User.Role.MANAGER,
        )
        employee = User.objects.create_user(
            email='rep@example.com', password='StrongPass123',
            employee_id='EMP003', first_name='Rep', last_name='One', manager=manager,
        )
        self.assertEqual(employee.manager, manager)
        self.assertIn(employee, manager.direct_reports.all())
