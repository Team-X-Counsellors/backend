from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AnonymousSession, AnonymousMessage
from .serializers import ShadowMessageSerializer
from api.services.jalibot_service import JalibotService


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
    permission_classes = [AllowAny]

    def post(self, request):
        session, raw_token = AnonymousSession.create_session(
            ttl_hours=settings.SHADOW_SESSION_TTL_HOURS
        )
        return Response({
            'session_id': str(session.id),
            'pseudonym': session.pseudonym,
            'token': raw_token,
            'expires_at': session.expires_at,
        }, status=status.HTTP_201_CREATED)


class ShadowSessionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        session = _authenticate_shadow(request, session_id)
        messages = list(
            session.messages.values('sender', 'content', 'created_at')
            .order_by('created_at')
        )
        return Response({
            'pseudonym': session.pseudonym,
            'expires_at': session.expires_at,
            'crisis_flagged': session.crisis_flagged,
            'messages': messages,
        })

    def delete(self, request, session_id):
        session = _authenticate_shadow(request, session_id)
        session.messages.all().delete()
        session.is_active = False
        session.ended_at = timezone.now()
        session.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShadowMessageView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        session = _authenticate_shadow(request, session_id)

        serializer = ShadowMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data['content']

        # Store the user's message
        AnonymousMessage.objects.create(
            session=session,
            sender=AnonymousMessage.Sender.USER,
            content=content,
        )

        # Get JaliBot response
        service = JalibotService()
        result = service.chat(
            message=content,
            language='en',
            user=None,
            anonymous_session=session,
        )

        # Store JaliBot's reply
        bot_msg = AnonymousMessage.objects.create(
            session=session,
            sender=AnonymousMessage.Sender.BOT,
            content=result['reply'],
        )

        return Response({
            'reply': result['reply'],
            'crisis_detected': result['crisis_detected'],
            'referred_to_counselor': result['referred_to_counselor'],
            'pseudonym': session.pseudonym,
        }, status=status.HTTP_200_OK)
