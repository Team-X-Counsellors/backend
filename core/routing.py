from django.urls import path

from apps.shadow_chat.consumers import ShadowChatConsumer
from apps.sessions.consumers import CallConsumer

websocket_urlpatterns = [
    path('ws/shadow/<uuid:session_id>/', ShadowChatConsumer.as_asgi()),
    path('ws/call/<uuid:appointment_id>/', CallConsumer.as_asgi()),
]
