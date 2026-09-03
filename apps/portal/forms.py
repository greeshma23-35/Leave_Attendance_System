from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from apps.accounts.models import User
from apps.leaves.models import LeaveRequest, LeaveType


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'you@company.com', 'autocomplete': 'email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Your password', 'autocomplete': 'current-password'}))


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), min_length=8)
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}), min_length=8)

    class Meta:
        model = User
        fields = [
            'employee_id', 'email', 'first_name', 'last_name', 'phone_number',
            'role', 'department', 'designation', 'manager', 'date_of_joining',
        ]
        widgets = {'date_of_joining': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, creator=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.creator = creator
        if creator and creator.role == User.Role.MANAGER:
            self.fields['role'].choices = [(User.Role.EMPLOYEE, 'Employee')]
            self.fields['manager'].queryset = User.objects.filter(pk=creator.pk)
            self.fields['manager'].initial = creator.pk
            self.fields['manager'].disabled = True
        else:
            self.fields['role'].choices = [(User.Role.EMPLOYEE, 'Employee'), (User.Role.MANAGER, 'Manager')]
            self.fields['manager'].queryset = User.objects.filter(role=User.Role.MANAGER, is_active=True).order_by('first_name', 'last_name')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('password_confirm'):
            self.add_error('password_confirm', 'Passwords do not match.')
        password = cleaned.get('password')
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as exc:
                self.add_error('password', exc)
        if self.creator and self.creator.role == User.Role.MANAGER:
            cleaned['role'] = User.Role.EMPLOYEE
            cleaned['manager'] = self.creator
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if self.creator and self.creator.role == User.Role.MANAGER:
            user.role = User.Role.EMPLOYEE
            user.manager = self.creator
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Reason for leave'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['leave_type'].queryset = LeaveType.objects.filter(is_active=True).order_by('name')

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get('start_date'), cleaned.get('end_date')
        leave_type = cleaned.get('leave_type')
        if start and end:
            if end < start:
                self.add_error('end_date', 'End date cannot be before start date.')
            if start < timezone.localdate():
                self.add_error('start_date', 'Leave cannot start in the past.')
            if leave_type and self.user:
                from apps.leaves.models import LeaveBalance
                balance = LeaveBalance.objects.filter(user=self.user, leave_type=leave_type, year=start.year).first()
                days = (end - start).days + 1
                if not balance:
                    self.add_error('leave_type', f'No {leave_type.name} balance exists for {start.year}.')
                elif days > balance.remaining_days:
                    self.add_error('end_date', f'Only {balance.remaining_days} day(s) remain for {leave_type.name}.')
                if LeaveRequest.objects.filter(user=self.user, status__in=['PENDING', 'APPROVED'], start_date__lte=end, end_date__gte=start).exists():
                    self.add_error('start_date', 'These dates overlap an existing leave request.')
        return cleaned
