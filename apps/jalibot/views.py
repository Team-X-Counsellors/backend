from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shadow_chat.models import AnonymousSession
from .serializers import JalibotMessageSerializer
from .models import JalibotConversation
from api.services.jalibot_service import JalibotService


class JalibotChatView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = JalibotMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user if request.user.is_authenticated else None
        anonymous_session = None

        if not user:
            anon_id = data.get('anonymous_session_id')
            anon_token = data.get('anonymous_token', '')
            if not anon_id or not anon_token:
                return Response(
                    {'error': 'Either JWT authentication or anonymous_session_id + anonymous_token required.'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            try:
                anonymous_session = AnonymousSession.objects.get(id=anon_id, is_active=True)
            except AnonymousSession.DoesNotExist:
                return Response({'error': 'Anonymous session not found.'}, status=status.HTTP_404_NOT_FOUND)

            if anonymous_session.is_expired():
                return Response({'error': 'Anonymous session has expired.'}, status=status.HTTP_403_FORBIDDEN)
            if not anonymous_session.verify_token(anon_token):
                return Response({'error': 'Invalid anonymous token.'}, status=status.HTTP_403_FORBIDDEN)

        service = JalibotService()
        result = service.chat(
            message=data['message'],
            language=data.get('language', 'en'),
            user=user,
            anonymous_session=anonymous_session,
        )
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE if result.get('error') == 'rate_limited' else status.HTTP_200_OK
        return Response(result, status=http_status)


class JalibotHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = JalibotConversation.objects.filter(user=request.user).order_by('-session_started_at')
        data = [
            {
                'id': str(c.id),
                'started_at': c.session_started_at,
                'last_message_at': c.last_message_at,
                'crisis_detected': c.crisis_detected,
                'message_count': len(c.messages),
            }
            for c in conversations
        ]
        return Response(data)
