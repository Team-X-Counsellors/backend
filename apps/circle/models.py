import uuid
from django.db import models
from django.conf import settings


class ForumCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'circle_category'
        ordering = ['order']

    def __str__(self):
        return self.name


class ForumThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        ForumCategory,
        on_delete=models.CASCADE,
        related_name='threads',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forum_threads',
    )
    anonymous_display_name = models.CharField(max_length=40, blank=True)
    title = models.CharField(max_length=300)
    body = models.TextField()
    is_moderated = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    reply_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'circle_thread'
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['category', 'is_moderated']),
        ]

    def __str__(self):
        return self.title


class ForumReply(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        ForumThread,
        on_delete=models.CASCADE,
        related_name='replies',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forum_replies',
    )
    anonymous_display_name = models.CharField(max_length=40, blank=True)
    body = models.TextField()
    is_moderated = models.BooleanField(default=False)
    parent_reply = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='child_replies',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'circle_reply'
        ordering = ['created_at']


class AuditLog(models.Model):
    class Action(models.TextChoices):
        USER_DEACTIVATED = 'user_deactivated', 'User Deactivated'
        USER_ACTIVATED = 'user_activated', 'User Activated'
        ROLE_CHANGED = 'role_changed', 'Role Changed'
        RESOURCE_DELETED = 'resource_deleted', 'Resource Deleted'
        THREAD_MODERATED = 'thread_moderated', 'Thread Moderated'
        SESSION_CANCELLED = 'session_cancelled', 'Session Cancelled'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_actions',
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    target_model = models.CharField(max_length=50)
    target_id = models.CharField(max_length=40)
    metadata = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_audit_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} by {self.actor} at {self.created_at}"
