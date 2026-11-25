from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsCounselor
from .models import AnonymousSession, AnonymousMessage
from .serializers import ShadowMessageSerializer
from .services import post_message, close_session, serialize_message, maybe_cover_with_ai, ai_should_cover, CRISIS_RESOURCES


def _authenticate_shadow(request, session_id):
    raw_token = request.headers.get('X-Shadow-Token', '')
    try:
        session = AnonymousSession.objects.get(id=session_id, is_active=True)
    except AnonymousSession.DoesNotExist:
        raise NotFound('Session not found.')
    if session.is_expired():
        raise PermissionDenied('Session has expired.')
    if not session.verify_token(raw_token):
        raise PermissionDenied('Invalid token.')
    return session


class ShadowStartView(APIView):
    """Student side: open an anonymous chat that a human counsellor will pick up."""
    permission_classes = [AllowAny]
    throttle_scope = 'shadow_start'

    def post(self, request):
        topic = request.data.get('topic', AnonymousSession.Topic.GENERAL)
        if topic not in AnonymousSession.Topic.values:
            topic = AnonymousSession.Topic.GENERAL
        session, raw_token = AnonymousSession.create_session(
            ttl_hours=settings.SHADOW_SESSION_TTL_HOURS
        )
        session.topic = topic
        session.crisis_flagged = topic == AnonymousSession.Topic.URGENT
        session.save(update_fields=['topic', 'crisis_flagged'])
        return Response({
            'session_id': str(session.id),
            'pseudonym': session.pseudonym,
            'token': raw_token,
            'expires_at': session.expires_at,
            'status': session.status,
            'crisis_resources': CRISIS_RESOURCES,
        }, status=status.HTTP_201_CREATED)


class ShadowSessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        session = _authenticate_shadow(request, session_id)
        after = request.query_params.get('after')
        qs = session.messages.order_by('id')
        if after and after.isdigit():
            qs = qs.filter(id__gt=int(after))
        return Response({
            'pseudonym': session.pseudonym,
            'status': session.status,
            'expires_at': session.expires_at,
            'crisis_flagged': session.crisis_flagged,
            'counselor_joined': session.assigned_counselor_id is not None,
            'ai_covering': ai_should_cover(session),
            'messages': [serialize_message(m) for m in qs],
            'crisis_resources': CRISIS_RESOURCES if session.crisis_flagged else None,
        })

    def delete(self, request, session_id):
        """Student ends the chat and wipes it. Nothing is retained."""
        session = _authenticate_shadow(request, session_id)
        close_session(session, wipe=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShadowMessageView(APIView):
    """Student -> counsellor. AI only covers critical chats that no counsellor has taken."""
    permission_classes = [AllowAny]
    throttle_scope = 'shadow_message'

    def post(self, request, session_id):
        session = _authenticate_shadow(request, session_id)
        serializer = ShadowMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        msg = post_message(session, AnonymousMessage.Sender.USER, serializer.validated_data['content'])
        session.refresh_from_db()
        maybe_cover_with_ai(session)  # only ever acts on critical chats no counsellor has taken
        return Response(serialize_message(msg), status=status.HTTP_201_CREATED)


# ---- Counsellor side ------------------------------------------------------------------

def _queue_item(s, mine=False):
    last = s.messages.order_by('-id').first()
    return {
        'session_id': str(s.id),
        'pseudonym': s.pseudonym,
        'topic': s.topic,
        'topic_label': s.get_topic_display(),
        'status': s.status,
        'crisis_flagged': s.crisis_flagged,
        'created_at': s.created_at,
        'claimed_by_me': mine,
        'preview': (last.content[:80] if last else ''),
    }


class CounselorQueueView(APIView):
    """Waiting chats (crisis first, then oldest) plus the chats I've already claimed."""
    permission_classes = [IsCounselor]

    def get(self, request):
        profile = request.user.counselor_profile
        live = AnonymousSession.objects.filter(is_active=True, expires_at__gt=timezone.now())
        waiting = live.filter(status=AnonymousSession.Status.WAITING).order_by('-crisis_flagged', 'created_at')
        mine = live.filter(
            status=AnonymousSession.Status.ACTIVE, assigned_counselor_id=profile.id
        ).order_by('-claimed_at')
        return Response({
            'waiting': [_queue_item(s) for s in waiting],
            'mine': [_queue_item(s, mine=True) for s in mine],
        })


class CounselorClaimView(APIView):
    permission_classes = [IsCounselor]

    def post(self, request, session_id):
        profile = request.user.counselor_profile
        updated = AnonymousSession.objects.filter(
            id=session_id, is_active=True, status=AnonymousSession.Status.WAITING,
            expires_at__gt=timezone.now(),
        ).update(
            status=AnonymousSession.Status.ACTIVE,
            assigned_counselor_id=profile.id,
            claimed_at=timezone.now(),
        )  # single UPDATE ... WHERE status='waiting' => only one counsellor can win the claim
        if not updated:
            return Response(
                {'error': 'Another counsellor already picked this chat up.'},
                status=status.HTTP_409_CONFLICT,
            )
        session = AnonymousSession.objects.get(id=session_id)
        post_message(
            session, AnonymousMessage.Sender.COUNSELOR,
            f"Hi {session.pseudonym}, I'm a counsellor here. I'm glad you reached out. What's on your mind?",
        )
        return Response(_queue_item(session, mine=True))


def _my_session(request, session_id):
    profile = request.user.counselor_profile
    try:
        return AnonymousSession.objects.get(
            id=session_id, is_active=True, assigned_counselor_id=profile.id
        )
    except AnonymousSession.DoesNotExist:
        raise NotFound('Chat not found.')


class CounselorSessionView(APIView):
    permission_classes = [IsCounselor]

    def get(self, request, session_id):
        session = _my_session(request, session_id)
        after = request.query_params.get('after')
        qs = session.messages.order_by('id')
        if after and after.isdigit():
            qs = qs.filter(id__gt=int(after))
        return Response({
            'pseudonym': session.pseudonym, 'topic_label': session.get_topic_display(),
            'status': session.status, 'crisis_flagged': session.crisis_flagged,
            'messages': [serialize_message(m) for m in qs],
        })

    def post(self, request, session_id):
        session = _my_session(request, session_id)
        serializer = ShadowMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        msg = post_message(session, AnonymousMessage.Sender.COUNSELOR, serializer.validated_data['content'])
        return Response(serialize_message(msg), status=status.HTTP_201_CREATED)

    def delete(self, request, session_id):
        session = _my_session(request, session_id)
        close_session(session, wipe=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
