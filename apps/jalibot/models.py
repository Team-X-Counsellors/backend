import uuid
from django.db import models
from django.conf import settings


class JalibotConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Nullable — anonymous users have no account
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jalibot_conversations',
    )
    # For anonymous usage: plain UUID reference, no FK constraint
    anonymous_session_id = models.UUIDField(null=True, blank=True)
    messages = models.JSONField(default=list)
    crisis_detected = models.BooleanField(default=False)
    crisis_keywords_found = models.JSONField(default=list)
    referred_to_counselor = models.BooleanField(default=False)
    referred_counselor_id = models.UUIDField(null=True, blank=True)
    session_started_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    message_count_this_hour = models.PositiveSmallIntegerField(default=0)
    hour_window_start = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=5, default='en')

    class Meta:
        db_table = 'jalibot_conversation'
        indexes = [
            models.Index(fields=['user', 'session_started_at']),
            models.Index(fields=['anonymous_session_id']),
        ]

    def __str__(self):
        label = self.user.username if self.user else f"anon:{self.anonymous_session_id}"
        return f"JaliBot:{label}"
