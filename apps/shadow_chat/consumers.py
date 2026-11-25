"""
Live updates for anonymous chat.

Students connect with their shadow token:   ws/shadow/<session_id>/?token=<raw token>
Counsellors connect with their JWT:         ws/shadow/<session_id>/?jwt=<access token>

This socket is receive-mostly: messages are POSTed over REST (so they are validated, stored and
crisis-checked in one place) and fanned out here. The only client->server event is `typing`.
No user table is touched for students: they are identified solely by the session token.
"""
import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import AnonymousSession
from .services import room_group


@database_sync_to_async
def _authorize(session_id, token, jwt):
    try:
        session = AnonymousSession.objects.get(id=session_id, is_active=True)
    except (AnonymousSession.DoesNotExist, ValueError):
        return None
    if session.expires_at <= timezone.now():
        return None
    if token:
        return ('student', session) if session.verify_token(token) else None
    if jwt:
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.users.models import CustomUser
        try:
            user = CustomUser.objects.get(id=AccessToken(jwt)['user_id'], is_active=True)
            profile = user.counselor_profile
        except Exception:
            return None
        if user.role == 'counselor' and session.assigned_counselor_id == profile.id:
            return ('counselor', session)
    return None


class ShadowChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from urllib.parse import parse_qs
        qs = parse_qs(self.scope['query_string'].decode())
        result = await _authorize(
            self.scope['url_route']['kwargs']['session_id'],
            (qs.get('token') or [''])[0], (qs.get('jwt') or [''])[0],
        )
        if not result:
            await self.close(code=4403)
            return
        self.role, session = result
        self.group = room_group(session.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except ValueError:
            return
        if data.get('type') == 'typing':
            await self.channel_layer.group_send(self.group, {
                'type': 'chat.event',
                'payload': {'event': 'typing', 'from': self.role},
                'origin': self.channel_name,
            })

    async def chat_event(self, event):
        if event.get('origin') == self.channel_name:
            return
        await self.send(text_data=json.dumps(event['payload']))
