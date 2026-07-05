from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdmin, IsSuperAdmin
from apps.users.models import CustomUser
from apps.users.serializers import UserProfileSerializer
from apps.sessions.models import Appointment
from apps.jalibot.models import JalibotConversation
from apps.shadow_chat.models import AnonymousSession
from apps.circle.models import AuditLog
from apps.circle.serializers import AuditLogSerializer


class UtilizationReportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        data = {
            'total_users': CustomUser.objects.count(),
            'active_students': CustomUser.objects.filter(role='student', is_active=True).count(),
            'active_counselors': CustomUser.objects.filter(role='counselor', is_active=True).count(),
            'total_appointments': Appointment.objects.count(),
            'completed_sessions': Appointment.objects.filter(status='completed').count(),
            'pending_sessions': Appointment.objects.filter(status='pending').count(),
            'jalibot_conversations': JalibotConversation.objects.count(),
            'crisis_flagged_conversations': JalibotConversation.objects.filter(crisis_detected=True).count(),
            'anonymous_sessions_active': AnonymousSession.objects.filter(is_active=True).count(),
            'anonymous_sessions_today': AnonymousSession.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'crisis_flagged_anonymous': AnonymousSession.objects.filter(crisis_flagged=True).count(),
        }
        return Response(data)


class AdminUserListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = UserProfileSerializer
    queryset = CustomUser.objects.all().order_by('-date_joined')
    filterset_fields = ['role', 'is_active', 'university']
    search_fields = ['username', 'email', 'first_name', 'last_name']


class AdminUserDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdmin]
    serializer_class = UserProfileSerializer
    queryset = CustomUser.objects.all()


class AdminDeactivateUserView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        if user.role == 'superadmin' and not request.user.is_super_admin():
            return Response(
                {'error': 'Only super admins can deactivate super admin accounts.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        user.is_active = False
        user.save()
        AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.USER_DEACTIVATED,
            target_model='CustomUser',
            target_id=str(pk),
            metadata={'username': user.username, 'role': user.role},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response({'status': 'deactivated', 'username': user.username})


class AdminActivateUserView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        user.is_active = True
        user.save()
        AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.USER_ACTIVATED,
            target_model='CustomUser',
            target_id=str(pk),
            metadata={'username': user.username},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response({'status': 'activated', 'username': user.username})


class AdminChangeRoleView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        user = get_object_or_404(CustomUser, pk=pk)
        new_role = request.data.get('role')
        if new_role not in dict(CustomUser.Role.choices):
            return Response({'error': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)
        old_role = user.role
        user.role = new_role
        user.save()
        AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.ROLE_CHANGED,
            target_model='CustomUser',
            target_id=str(pk),
            metadata={'from': old_role, 'to': new_role, 'username': user.username},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response({'status': 'role_updated', 'new_role': new_role})


class AuditLogView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.all().select_related('actor')
    filterset_fields = ['action']
    search_fields = ['actor__username', 'target_model', 'target_id']
