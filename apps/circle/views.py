from django.db import models as db_models
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from api.permissions import IsAdminOrAuthor, IsAdmin
from apps.shadow_chat.models import generate_pseudonym
from .models import ForumCategory, ForumThread, ForumReply, AuditLog
from .serializers import (
    ForumCategorySerializer, ForumThreadSerializer,
    ForumReplySerializer, AuditLogSerializer,
)


class ForumCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ForumCategory.objects.filter(is_active=True)
    serializer_class = ForumCategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ForumThreadViewSet(viewsets.ModelViewSet):
    serializer_class = ForumThreadSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['category']
    search_fields = ['title', 'body']

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role in ('admin', 'superadmin'):
            return ForumThread.objects.all().select_related('category', 'author')
        return ForumThread.objects.filter(is_moderated=False).select_related('category', 'author')

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAdminOrAuthor()]
        if self.action == 'replies':
            return [AllowAny()]
        return [IsAuthenticatedOrReadOnly()]

    def perform_create(self, serializer):
        user = self.request.user
        category = serializer.validated_data.get('category')
        if category is None:
            category, _ = ForumCategory.objects.get_or_create(
                slug='general',
                defaults={'name': 'General', 'description': 'General discussions', 'icon': '💬', 'order': 0},
            )
        if user.is_authenticated:
            serializer.save(author=user, category=category)
        else:
            serializer.save(anonymous_display_name=generate_pseudonym(), category=category)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        ForumThread.objects.filter(pk=instance.pk).update(
            view_count=db_models.F('view_count') + 1
        )
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['get', 'post'], url_path='replies')
    def replies(self, request, pk=None):
        thread = self.get_object()
        if request.method == 'GET':
            replies = thread.replies.filter(is_moderated=False).select_related('author')
            return Response(ForumReplySerializer(replies, many=True).data)

        serializer = ForumReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        anon_name = '' if user else generate_pseudonym()
        serializer.save(thread=thread, author=user, anonymous_display_name=anon_name)
        ForumThread.objects.filter(pk=thread.pk).update(
            reply_count=db_models.F('reply_count') + 1
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def moderate(self, request, pk=None):
        thread = self.get_object()
        thread.is_moderated = not thread.is_moderated
        thread.save(update_fields=['is_moderated'])
        AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.THREAD_MODERATED,
            target_model='ForumThread',
            target_id=str(thread.id),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response({'is_moderated': thread.is_moderated})
