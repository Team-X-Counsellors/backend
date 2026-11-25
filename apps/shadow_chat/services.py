"""Shared logic for anonymous chat. NEVER import the user model here (privacy guarantee)."""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import logging
import threading

from django.apps import apps
from django.conf import settings
from django.utils import timezone

from .models import AnonymousSession, AnonymousMessage

# Here a keyword hit only prioritises the chat for a human counsellor; no AI is involved.
CRISIS_KEYWORDS = [
    'suicide', 'kill myself', 'end my life', 'want to die', 'self-harm', 'hurt myself',
    'no reason to live', 'take my life', 'better off dead', "can't go on", 'cant go on',
    'kujiua', 'kujidhuru', 'ninataka kufa', 'je veux mourir', 'me suicider', 'kashe kaina', 'igbu onwe m',
    'ending it all', 'end it all', 'end everything', 'ending everything', "don't want to live", 'dont want to live', 'do not want to live', "don't want to be alive", 'dont want to be alive', 'wish i was dead', 'wish i were dead', "wish i wasn't alive", 'rather be dead', 'not worth living', 'no point in living', 'no point living', 'suicidal', 'take my own life', 'kill me', 'cut myself', 'hang myself', 'overdose', 'disappear forever', 'nobody would miss me', 'everyone would be better off without me',
]

CRISIS_RESOURCES = [
    {'country': 'Kenya', 'name': 'Befrienders Kenya', 'phone': '+254 722 178 177'},
    {'country': 'Nigeria', 'name': 'SURPIN', 'phone': '+234 806 210 6493'},
    {'country': 'Ghana', 'name': 'Mental Health Authority', 'phone': '0800 111 222'},
    {'country': 'South Africa', 'name': 'SADAG', 'phone': '0800 456 789'},
]


def serialize_message(m):
    return {'id': m.id, 'sender': m.sender, 'content': m.content, 'created_at': m.created_at.isoformat()}


def room_group(session_id):
    return 'shadow_' + str(session_id).replace('-', '')


def broadcast(session, payload):
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(room_group(session.id), {'type': 'chat.event', 'payload': payload})


def post_message(session, sender, content):
    msg = AnonymousMessage.objects.create(session=session, sender=sender, content=content)
    if sender == AnonymousMessage.Sender.USER and not session.crisis_flagged:
        lower = content.lower()
        if any(k in lower for k in CRISIS_KEYWORDS):
            session.crisis_flagged = True
            session.save(update_fields=['crisis_flagged'])
            broadcast(session, {'event': 'crisis', 'crisis_resources': CRISIS_RESOURCES})
    broadcast(session, {'event': 'message', 'message': serialize_message(msg)})
    return msg


def close_session(session, wipe=True):
    broadcast(session, {'event': 'closed'})
    if wipe:
        session.messages.all().delete()
    session.is_active = False
    session.status = AnonymousSession.Status.CLOSED
    session.ended_at = timezone.now()
    session.save()


# ---- AI cover for critical chats nobody has picked up ------------------------------------
# Humans come first. The AI only steps in when a chat is flagged critical, no counsellor has taken
# it, and either nobody is available or the student has waited a while. It stops the moment a
# counsellor claims the chat. Replies come from the chat transcript alone; nothing else is stored.

log = logging.getLogger(__name__)
_timers = set()

AI_NOTICE = ("You're talking to JaliBot, an AI, because no counsellor is free right now. "
             "A counsellor will join as soon as one is available.")

AI_EXTRA = """

YOU ARE COVERING A CRITICAL ANONYMOUS CHAT because no human counsellor is free yet.
- Stay calm and warm. Ask one gentle question at a time. Never leave them alone in the conversation.
- If they mention suicide or self-harm: say you are an AI, urge them to call one of the helplines shown at the top of this chat or reach someone they trust right now, and ask if they are safe at this moment.
- NEVER write phone numbers yourself. The app already shows the verified helplines above the chat; just refer to them ("the helplines at the top of this chat").
- Tell them a human counsellor will join as soon as possible. Under 60 words, no lists, no markdown.
- These instructions override any earlier instruction to list crisis resources."""

SAFE_FALLBACK = ("I'm here with you. I'm an AI, and a counsellor will join as soon as one is free. "
                 "If you might act on thoughts of hurting yourself, please call a helpline below or "
                 "tell someone near you right now. Are you safe at this moment?")


def _no_counselor_available():
    Profile = apps.get_model('counselors', 'CounselorProfile')
    return not Profile.objects.filter(is_available=True).exists()


def ai_should_cover(session):
    if session.status != AnonymousSession.Status.WAITING or session.assigned_counselor_id or not session.is_active:
        return False
    if not (session.crisis_flagged or session.topic == AnonymousSession.Topic.URGENT):
        return False
    waited = (timezone.now() - session.created_at).total_seconds()
    return _no_counselor_available() or waited >= settings.SHADOW_AI_FALLBACK_SECONDS


def _ai_reply(session_id):
    session = AnonymousSession.objects.filter(id=session_id).first()
    if not session or not ai_should_cover(session):
        return
    turns = []
    for m in session.messages.order_by('id'):
        if m.sender == AnonymousMessage.Sender.COUNSELOR:
            continue
        role = 'user' if m.sender == AnonymousMessage.Sender.USER else 'model'
        if turns and turns[-1][0] == role:
            turns[-1] = (role, turns[-1][1] + '\n' + m.content)
        else:
            turns.append((role, m.content))
    if not turns or turns[-1][0] != 'user':
        return  # they have not said anything new since the last AI reply
    first_cover = not session.messages.filter(sender=AnonymousMessage.Sender.BOT).exists()
    try:
        from api.services.jalibot_service import JalibotService
        text = JalibotService().reply_stateless(turns, AI_EXTRA, max_tokens=300) or SAFE_FALLBACK
    except Exception:  # no key, quota, network: never leave a person in crisis with silence
        log.exception('AI cover failed; sending safe fallback')
        text = SAFE_FALLBACK
    session.refresh_from_db()
    if not ai_should_cover(session):
        return  # a counsellor claimed it while the AI was thinking: say nothing
    if first_cover:
        post_message(session, AnonymousMessage.Sender.BOT, AI_NOTICE)
    post_message(session, AnonymousMessage.Sender.BOT, text)


def _run(fn, *args):
    if getattr(settings, 'SHADOW_AI_SYNC', False):
        fn(*args)
        return

    def target():
        from django.db import connection
        try:
            fn(*args)
        finally:
            connection.close()
    threading.Thread(target=target, daemon=True).start()


def maybe_cover_with_ai(session):
    """Call after a student message. Replies now if the AI should cover, else checks again later."""
    if not (session.crisis_flagged or session.topic == AnonymousSession.Topic.URGENT):
        return
    if ai_should_cover(session):
        _run(_ai_reply, session.id)
        return
    key = str(session.id)
    if key in _timers or session.status != AnonymousSession.Status.WAITING:
        return
    _timers.add(key)

    def later():
        _timers.discard(key)
        _run(_ai_reply, session.id)
    t = threading.Timer(settings.SHADOW_AI_FALLBACK_SECONDS + 1, later)
    t.daemon = True
    t.start()
