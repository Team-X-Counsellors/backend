from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.shadow_chat.models import AnonymousSession
from .serializers import JalibotMessageSerializer, JalibotMemorySerializer
from .models import JalibotConversation, JalibotMemory
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
            conversation_id=data.get('conversation_id'),
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
                'title': c.title,
                'started_at': c.session_started_at,
                'last_message_at': c.last_message_at,
                'crisis_detected': c.crisis_detected,
                'message_count': len(c.messages),
            }
            for c in conversations
        ]
        return Response(data)


class JalibotConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_object_or_404(JalibotConversation, id=conversation_id, user=request.user)
        return Response({
            'id': str(conversation.id),
            'title': conversation.title,
            'started_at': conversation.session_started_at,
            'last_message_at': conversation.last_message_at,
            'crisis_detected': conversation.crisis_detected,
            'messages': conversation.messages,
        })


class JalibotMemoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memories = JalibotMemory.objects.filter(user=request.user)
        return Response(JalibotMemorySerializer(memories, many=True).data)


class JalibotMemoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, memory_id):
        memory = get_object_or_404(JalibotMemory, id=memory_id, user=request.user)
        memory.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
