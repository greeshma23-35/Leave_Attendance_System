from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Employee Leave & Attendance Management System API",
        default_version='v1',
        description="REST API documentation for managing employees, attendance and leave.",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    authentication_classes=[],
)

urlpatterns = [
    path('', include('apps.portal.urls')),
    path('admin/', admin.site.urls),

    # Auth & account endpoints
    path('api/auth/', include('apps.accounts.urls')),

    # Domain endpoints
    path('api/', include('apps.attendance.urls')),
    path('api/', include('apps.leaves.urls')),

    # API documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
