from datetime import timedelta
from celery import shared_task
from django.utils import timezone


@shared_task(name='shadow_chat.cleanup_expired_sessions')
def cleanup_expired_sessions():
    """
    Hard-deletes expired and manually-closed anonymous sessions.
    CASCADE deletes all AnonymousMessage rows too.
    No user identifiers ever existed in these tables — deletion is complete erasure.
    Runs every 15 minutes via Celery Beat.
    """
    from apps.shadow_chat.models import AnonymousSession

    # Delete sessions past their expiry time
    expired = AnonymousSession.objects.filter(expires_at__lte=timezone.now())
    expired_count = expired.count()
    expired.delete()

    # Delete sessions that were explicitly ended over 1 hour ago
    cutoff = timezone.now() - timedelta(hours=1)
    closed = AnonymousSession.objects.filter(is_active=False, ended_at__lte=cutoff)
    closed_count = closed.count()
    closed.delete()

    return f'Deleted {expired_count} expired + {closed_count} closed anonymous sessions.'
