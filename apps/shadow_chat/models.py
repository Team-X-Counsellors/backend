import uuid
import secrets
import hashlib
import random
from datetime import timedelta
from django.db import models
from django.utils import timezone

# PRIVACY GUARANTEE: NO ForeignKey to any user table in this file.
# This module must NEVER import settings.AUTH_USER_MODEL.
# Anonymous sessions are cryptographically unlinkable to registered users.

ADJECTIVES = ['Brave', 'Quiet', 'Golden', 'Swift', 'Calm', 'Bold', 'Wise', 'Bright', 'Silent', 'Gentle']
NOUNS = ['Baobab', 'Eagle', 'Savanna', 'River', 'Horizon', 'Mountain', 'Kestrel', 'Harambee', 'Ubuntu', 'Acacia']


def generate_pseudonym():
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    number = random.randint(1000, 9999)
    return f"{adj}{noun}_{number}"


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class AnonymousSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pseudonym = models.CharField(max_length=40, unique=True)
    token_hash = models.CharField(max_length=64)
    # Stored as plain UUID — no FK constraint to counselors table
    referred_counselor_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    crisis_flagged = models.BooleanField(default=False)

    class Meta:
        db_table = 'shadow_anonymous_session'
        indexes = [
            models.Index(fields=['expires_at', 'is_active']),
        ]

    @classmethod
    def create_session(cls, ttl_hours=24):
        raw_token = secrets.token_urlsafe(32)
        session = cls.objects.create(
            pseudonym=generate_pseudonym(),
            token_hash=hash_token(raw_token),
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
        )
        # raw_token returned ONCE to client, never persisted again
        return session, raw_token

    def verify_token(self, raw_token: str) -> bool:
        return secrets.compare_digest(self.token_hash, hash_token(raw_token))

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Shadow:{self.pseudonym}"


class AnonymousMessage(models.Model):
    class Sender(models.TextChoices):
        USER = 'user', 'User'
        BOT = 'bot', 'Bot'
        COUNSELOR = 'counselor', 'Counselor'

    session = models.ForeignKey(
        AnonymousSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.CharField(max_length=10, choices=Sender.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shadow_anonymous_message'
        ordering = ['created_at']
