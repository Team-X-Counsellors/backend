from django.urls import path
from .admin_views import (
    UtilizationReportView,
    AdminUserListView,
    AdminUserDetailView,
    AdminDeactivateUserView,
    AdminActivateUserView,
    AdminChangeRoleView,
    AuditLogView,
)

app_name = 'jalimind_admin'

urlpatterns = [
    path('reports/utilization/', UtilizationReportView.as_view(), name='utilization'),
    path('users/', AdminUserListView.as_view(), name='users'),
    path('users/<int:pk>/', AdminUserDetailView.as_view(), name='user_detail'),
    path('users/<int:pk>/deactivate/', AdminDeactivateUserView.as_view(), name='deactivate_user'),
    path('users/<int:pk>/activate/', AdminActivateUserView.as_view(), name='activate_user'),
    path('users/<int:pk>/change-role/', AdminChangeRoleView.as_view(), name='change_role'),
    path('audit-logs/', AuditLogView.as_view(), name='audit_logs'),
]
