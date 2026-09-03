from django.urls import path
from . import views

app_name = 'portal'

urlpatterns = [
    path('health/', views.health, name='health'),
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('users/', views.users, name='users'),
    path('users/add/', views.create_user, name='create_user'),
    path('attendance/', views.attendance, name='attendance'),
    path('attendance/check-in/', views.check_in, name='check_in'),
    path('attendance/check-out/', views.check_out, name='check_out'),
    path('leaves/', views.leaves, name='leaves'),
    path('leaves/apply/', views.apply_leave, name='apply_leave'),
    path('leaves/<int:pk>/<str:action>/', views.review_leave, name='review_leave'),
    path('leaves/<int:pk>/cancel/', views.cancel_leave, name='cancel_leave'),
]
