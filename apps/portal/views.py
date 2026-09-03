from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveBalance, LeaveRequest, LeaveType

from .forms import LeaveRequestForm, LoginForm, UserCreateForm


def health(request):
    return JsonResponse({'status': 'ok'})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('portal:dashboard')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request, username=form.cleaned_data['email'], password=form.cleaned_data['password'])
        if user and user.is_active:
            login(request, user)
            return redirect(request.GET.get('next') or 'portal:dashboard')
        form.add_error(None, 'Invalid email or password.')
    return render(request, 'portal/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('portal:login')


def _scope_users(user):
    if user.is_admin:
        return User.objects.all()
    if user.is_manager:
        return User.objects.filter(Q(pk=user.pk) | Q(manager=user))
    return User.objects.filter(pk=user.pk)


@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()
    attendance_today = Attendance.objects.filter(user=user, date=today).first()
    my_pending = LeaveRequest.objects.filter(user=user, status=LeaveRequest.Status.PENDING).count()
    context = {
        'attendance_today': attendance_today,
        'now': timezone.localtime(),
        'my_pending': my_pending,
        'balances': LeaveBalance.objects.filter(user=user, year=today.year).select_related('leave_type'),
    }
    if user.is_admin:
        context.update({
            'employee_count': User.objects.filter(role=User.Role.EMPLOYEE, is_active=True).count(),
            'manager_count': User.objects.filter(role=User.Role.MANAGER, is_active=True).count(),
            'pending_count': LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING).count(),
            'present_today': Attendance.objects.filter(date=today, status=Attendance.Status.PRESENT).count(),
        })
    elif user.is_manager:
        team = User.objects.filter(manager=user, is_active=True)
        context.update({
            'team_count': team.count(),
            'pending_count': LeaveRequest.objects.filter(user__manager=user, status=LeaveRequest.Status.PENDING).count(),
            'present_today': Attendance.objects.filter(user__in=team, date=today, status=Attendance.Status.PRESENT).count(),
        })
    return render(request, 'portal/dashboard.html', context)


@login_required
def users(request):
    if not (request.user.is_admin or request.user.is_manager):
        messages.error(request, 'You do not have permission to manage users.')
        return redirect('portal:dashboard')
    qs = _scope_users(request.user).select_related('manager')
    role = request.GET.get('role')
    search = request.GET.get('q', '').strip()
    if role:
        qs = qs.filter(role=role)
    if search:
        qs = qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(employee_id__icontains=search) | Q(email__icontains=search))
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'portal/users.html', {'page': page, 'search': search, 'role': role})


@login_required
def create_user(request):
    if not (request.user.is_admin or request.user.is_manager):
        messages.error(request, 'You do not have permission to add users.')
        return redirect('portal:dashboard')
    form = UserCreateForm(request.POST or None, creator=request.user)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'{user.get_full_name()} was added successfully.')
        return redirect('portal:users')
    return render(request, 'portal/user_form.html', {'form': form, 'is_manager': request.user.is_manager})


@login_required
def attendance(request):
    qs = Attendance.objects.select_related('user', 'marked_by').filter(user__in=_scope_users(request.user))
    date = request.GET.get('date')
    status = request.GET.get('status')
    if date:
        qs = qs.filter(date=date)
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'portal/attendance.html', {'page': page, 'date': date, 'status': status, 'statuses': Attendance.Status.choices})


@login_required
def check_in(request):
    if request.method == 'POST':
        today = timezone.localdate()
        attendance, _ = Attendance.objects.get_or_create(user=request.user, date=today, defaults={'status': Attendance.Status.PRESENT})
        if attendance.check_in:
            messages.warning(request, 'You have already checked in today.')
        else:
            attendance.check_in = timezone.localtime().time()
            attendance.status = Attendance.Status.PRESENT
            attendance.save()
            messages.success(request, 'Check-in recorded.')
    return redirect('portal:dashboard')


@login_required
def check_out(request):
    if request.method == 'POST':
        attendance = Attendance.objects.filter(user=request.user, date=timezone.localdate()).first()
        if not attendance or not attendance.check_in:
            messages.error(request, 'Please check in before checking out.')
        elif attendance.check_out:
            messages.warning(request, 'You have already checked out today.')
        else:
            attendance.check_out = timezone.localtime().time()
            attendance.save()
            messages.success(request, 'Check-out recorded.')
    return redirect('portal:dashboard')


@login_required
def leaves(request):
    qs = LeaveRequest.objects.select_related('user', 'leave_type', 'reviewed_by').filter(user__in=_scope_users(request.user))
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'portal/leaves.html', {'page': page, 'status': status, 'statuses': LeaveRequest.Status.choices})


@login_required
def apply_leave(request):
    form = LeaveRequestForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        leave = form.save(commit=False)
        leave.user = request.user
        leave.save()
        messages.success(request, 'Leave request submitted for approval.')
        return redirect('portal:leaves')
    return render(request, 'portal/leave_form.html', {'form': form})


@login_required
def review_leave(request, pk, action):
    if request.method != 'POST':
        messages.info(request, 'Use the action button to review this request.')
        return redirect('portal:leaves')
    if not (request.user.is_admin or request.user.is_manager):
        messages.error(request, 'You do not have permission to review leave.')
        return redirect('portal:leaves')
    leave = get_object_or_404(LeaveRequest.objects.select_related('user', 'leave_type'), pk=pk)
    if not request.user.is_admin and leave.user.manager_id != request.user.id:
        messages.error(request, 'You can only review your direct reports.')
        return redirect('portal:leaves')
    if leave.status != LeaveRequest.Status.PENDING:
        messages.warning(request, 'This request has already been reviewed.')
        return redirect('portal:leaves')
    if action == 'approve':
        balance = LeaveBalance.objects.filter(user=leave.user, leave_type=leave.leave_type, year=leave.start_date.year).first()
        if not balance or leave.total_days > balance.remaining_days:
            messages.error(request, 'Insufficient leave balance for this request.')
            return redirect('portal:leaves')
        balance.used_days += leave.total_days
        balance.save()
        leave.status = LeaveRequest.Status.APPROVED
        current = leave.start_date
        while current <= leave.end_date:
            Attendance.objects.update_or_create(user=leave.user, date=current, defaults={'status': Attendance.Status.ON_LEAVE})
            current += timedelta(days=1)
        messages.success(request, 'Leave approved.')
    else:
        leave.status = LeaveRequest.Status.REJECTED
        messages.success(request, 'Leave rejected.')
    leave.reviewed_by = request.user
    leave.reviewed_on = timezone.now()
    leave.save()
    return redirect('portal:leaves')


@login_required
def cancel_leave(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk, user=request.user)
    if request.method == 'POST' and leave.status == LeaveRequest.Status.PENDING:
        leave.status = LeaveRequest.Status.CANCELLED
        leave.reviewed_on = timezone.now()
        leave.save()
        messages.success(request, 'Leave request cancelled.')
    return redirect('portal:leaves')
