from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls', namespace='auth')),
    path('api/shadow/', include('apps.shadow_chat.urls', namespace='shadow')),
    path('api/jalibot/', include('apps.jalibot.urls', namespace='jalibot')),
    path('api/counselors/', include('apps.counselors.urls', namespace='counselors')),
    path('api/appointments/', include('apps.sessions.urls', namespace='sessions')),
    path('api/library/', include('apps.library.urls', namespace='library')),
    path('api/circle/', include('apps.circle.urls', namespace='circle')),
    path('api/admin/', include('api.admin_urls', namespace='jalimind_admin')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
