import pytest
from datetime import timedelta
from django.utils import timezone
from apps.shadow_chat.models import AnonymousSession, AnonymousMessage


@pytest.mark.django_db
class TestAnonymousSessionPrivacy:
    def test_anonymous_session_has_no_user_fk(self, db):
        from django.db import connection
        vendor = connection.vendor  # 'sqlite' or 'postgresql'
        with connection.cursor() as cursor:
            if vendor == 'sqlite':
                cursor.execute(
                    "SELECT COUNT(*) FROM pragma_foreign_key_list('shadow_anonymous_session') "
                    "WHERE \"table\" = 'users_customuser'"
                )
            else:
                # PostgreSQL: check information_schema for FK from shadow table to users table
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.referential_constraints rc
                        ON tc.constraint_name = rc.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                        ON rc.unique_constraint_name = ccu.constraint_name
                    WHERE tc.table_name = 'shadow_anonymous_session'
                      AND ccu.table_name = 'users_customuser'
                      AND tc.constraint_type = 'FOREIGN KEY'
                """)
            count = cursor.fetchone()[0]
        assert count == 0, 'AnonymousSession MUST NOT have a FK to users_customuser'

    def test_anonymous_session_model_has_no_user_field(self, db):
        session, _ = AnonymousSession.create_session()
        assert not hasattr(session, 'user'), 'AnonymousSession must not have a user field'
        assert not hasattr(session, 'user_id'), 'AnonymousSession must not have a user_id field'

    def test_create_session_returns_raw_token_once(self, db):
        session, raw_token = AnonymousSession.create_session()
        assert raw_token is not None
        assert len(raw_token) > 20
        # Verify token is valid
        assert session.verify_token(raw_token)

    def test_raw_token_not_stored_in_db(self, db):
        session, raw_token = AnonymousSession.create_session()
        # The DB stores only the hash, not the raw token
        assert session.token_hash != raw_token
        assert len(session.token_hash) == 64  # SHA-256 hex digest

    def test_wrong_token_rejected(self, db):
        session, _ = AnonymousSession.create_session()
        assert not session.verify_token('wrongtoken')
        assert not session.verify_token('')
        assert not session.verify_token('a' * 64)

    def test_expired_sessions_deleted_by_task(self, db):
        session, _ = AnonymousSession.create_session(ttl_hours=1)
        # Manually expire it
        session.expires_at = timezone.now() - timedelta(minutes=1)
        session.save()

        from apps.shadow_chat.tasks import cleanup_expired_sessions
        cleanup_expired_sessions()

        assert not AnonymousSession.objects.filter(id=session.id).exists()

    def test_closed_sessions_deleted_by_task(self, db):
        session, _ = AnonymousSession.create_session()
        session.is_active = False
        session.ended_at = timezone.now() - timedelta(hours=2)
        session.save()

        from apps.shadow_chat.tasks import cleanup_expired_sessions
        cleanup_expired_sessions()

        assert not AnonymousSession.objects.filter(id=session.id).exists()

    def test_messages_cascade_deleted_with_session(self, db):
        session, _ = AnonymousSession.create_session()
        msg = AnonymousMessage.objects.create(
            session=session,
            sender=AnonymousMessage.Sender.USER,
            content='Test message',
        )
        session_id = session.id
        msg_id = msg.id

        session.delete()

        assert not AnonymousMessage.objects.filter(id=msg_id).exists()


@pytest.mark.django_db
class TestShadowChatAPI:
    def test_start_shadow_session(self, api_client):
        res = api_client.post('/api/shadow/start/')
        assert res.status_code == 201
        assert 'session_id' in res.data
        assert 'pseudonym' in res.data
        assert 'token' in res.data
        assert 'expires_at' in res.data

    def test_access_session_with_valid_token(self, api_client, db):
        start_res = api_client.post('/api/shadow/start/')
        session_id = start_res.data['session_id']
        token = start_res.data['token']

        res = api_client.get(
            f'/api/shadow/session/{session_id}/',
            HTTP_X_SHADOW_TOKEN=token,
        )
        assert res.status_code == 200
        assert res.data['pseudonym'] == start_res.data['pseudonym']

    def test_access_session_with_invalid_token_rejected(self, api_client, db):
        start_res = api_client.post('/api/shadow/start/')
        session_id = start_res.data['session_id']

        res = api_client.get(
            f'/api/shadow/session/{session_id}/',
            HTTP_X_SHADOW_TOKEN='badtoken',
        )
        assert res.status_code == 403
