"""
WebRTC signalling for counselling calls (video or voice), one room per appointment.

    ws/call/<appointment_id>/?jwt=<access token>

The server only relays the handshake (offer / answer / ICE candidates) between the two
participants. Audio and video flow peer-to-peer and never touch this server.
Only the appointment's own student and counsellor may join, and only inside the join window.
"""
import json
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from .models import Appointment

RELAYED = {'offer', 'answer', 'candidate', 'hangup', 'media-state', 'chat'}


@database_sync_to_async
def _authorize(appointment_id, jwt):
    from rest_framework_simplejwt.tokens import AccessToken
    from apps.users.models import CustomUser
    try:
        user = CustomUser.objects.get(id=AccessToken(jwt)['user_id'], is_active=True)
        appt = Appointment.objects.select_related('student', 'counselor__user').get(id=appointment_id)
    except Exception:
        return None
    is_student = appt.student_id == user.id
    is_counselor = appt.counselor_id is not None and appt.counselor.user_id == user.id
    if not (is_student or is_counselor):
        return None
    if appt.status not in (Appointment.Status.CONFIRMED, Appointment.Status.IN_PROGRESS):
        return None
    now = timezone.now()
    early = timedelta(minutes=settings.CALL_JOIN_EARLY_MINUTES)
    late = timedelta(minutes=appt.duration_minutes + settings.CALL_JOIN_LATE_MINUTES)
    if not (appt.scheduled_at - early <= now <= appt.scheduled_at + late):
        return 'outside_window'
    name = user.first_name or user.username
    return {'role': 'counselor' if is_counselor else 'student', 'name': name, 'type': appt.session_type}


class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from urllib.parse import parse_qs
        qs = parse_qs(self.scope['query_string'].decode())
        info = await _authorize(self.scope['url_route']['kwargs']['appointment_id'], (qs.get('jwt') or [''])[0])
        if info is None:
            await self.close(code=4403)
            return
        await self.accept()
        if info == 'outside_window':
            await self.send(text_data=json.dumps({'type': 'error', 'code': 'outside_window'}))
            await self.close(code=4408)
            return
        self.info = info
        self.group = 'call_' + str(self.scope['url_route']['kwargs']['appointment_id']).replace('-', '')
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.send(text_data=json.dumps({
            'type': 'joined', 'role': info['role'], 'session_type': info['type'],
            'ice_servers': settings.CALL_ICE_SERVERS,
        }))
        # Tell whoever is already here; they will create the offer.
        await self.channel_layer.group_send(self.group, {
            'type': 'relay', 'origin': self.channel_name,
            'payload': {'type': 'peer-joined', 'role': info['role'], 'name': info['name']},
        })

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_send(self.group, {
                'type': 'relay', 'origin': self.channel_name, 'payload': {'type': 'peer-left'},
            })
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except ValueError:
            return
        if data.get('type') in RELAYED:
            await self.channel_layer.group_send(self.group, {
                'type': 'relay', 'origin': self.channel_name, 'payload': data,
            })

    async def relay(self, event):
        if event['origin'] != self.channel_name:
            await self.send(text_data=json.dumps(event['payload']))
