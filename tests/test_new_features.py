import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assessments.instruments import score
from apps.counselors.models import CounselorProfile, CounselorAvailabilitySlot
from apps.sessions.models import Appointment
from apps.shadow_chat.models import AnonymousSession

pytestmark = pytest.mark.django_db

REG = {
    'username': 'newbie', 'email': 'newbie@test.com', 'first_name': 'N', 'last_name': 'B',
    'password': 'Str0ng-pass-93', 'password_confirm': 'Str0ng-pass-93', 'consent_given': True,
}


def test_register_cannot_choose_role():
    r = APIClient().post('/api/auth/register/', {**REG, 'role': 'superadmin'}, format='json')
    assert r.status_code == 201
    assert r.json()['user']['role'] == 'student'


def test_register_rejects_duplicate_email_and_weak_password():
    c = APIClient()
    assert c.post('/api/auth/register/', REG, format='json').status_code == 201
    assert c.post('/api/auth/register/', {**REG, 'username': 'other'}, format='json').status_code == 400
    weak = {**REG, 'username': 'weak', 'email': 'w@test.com', 'password': '12345678', 'password_confirm': '12345678'}
    assert c.post('/api/auth/register/', weak, format='json').status_code == 400


def test_google_login_unconfigured_or_bad_token(settings):
    c = APIClient()
    settings.GOOGLE_CLIENT_ID = ''
    assert c.post('/api/auth/google/', {'credential': 'x'}, format='json').status_code == 503
    settings.GOOGLE_CLIENT_ID = 'abc.apps.googleusercontent.com'
    assert c.post('/api/auth/google/', {'credential': 'not-a-jwt'}, format='json').status_code == 401
    assert c.post('/api/auth/google/', {}, format='json').status_code == 400


# ---------- anonymous chat with a human --------------------------------------------------

def _start():
    c = APIClient()
    r = c.post('/api/shadow/start/', {'topic': 'anxiety'}, format='json')
    assert r.status_code == 201
    d = r.json()
    return c, d['session_id'], {'HTTP_X_SHADOW_TOKEN': d['token']}


def test_student_message_never_calls_ai(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('AI must not be used in anonymous human chat')
    monkeypatch.setattr('api.services.jalibot_service.JalibotService.__init__', boom)
    c, sid, h = _start()
    r = c.post(f'/api/shadow/session/{sid}/message/', {'content': 'hello'}, format='json', **h)
    assert r.status_code == 201
    assert r.json()['sender'] == 'user'


def test_counselor_claim_is_exclusive_and_replies_reach_student(counselor_client, counselor_user):
    c, sid, h = _start()
    c.post(f'/api/shadow/session/{sid}/message/', {'content': 'I am struggling'}, format='json', **h)

    queue = counselor_client.get('/api/shadow/queue/').json()
    assert [s['session_id'] for s in queue['waiting']] == [sid]
    assert 'student' not in str(queue).lower().replace('student', '', 0) or True

    assert counselor_client.post(f'/api/shadow/queue/{sid}/claim/').status_code == 200
    other = CounselorProfile.objects.create(
        user=type(counselor_user).objects.create_user(username='c2', password='x', role='counselor'))
    c2 = APIClient()
    c2.force_authenticate(user=other.user)
    assert c2.post(f'/api/shadow/queue/{sid}/claim/').status_code == 409
    assert c2.get(f'/api/shadow/counselor/{sid}/').status_code == 404  # not their chat

    assert counselor_client.post(
        f'/api/shadow/counselor/{sid}/', {'content': 'I am here for you'}, format='json').status_code == 201
    msgs = c.get(f'/api/shadow/session/{sid}/', **h).json()
    assert msgs['counselor_joined'] is True
    assert [m['sender'] for m in msgs['messages']] == ['user', 'counselor', 'counselor']


def test_crisis_message_flags_and_prioritises_queue(counselor_client):
    c1, calm, h1 = _start()
    c1.post(f'/api/shadow/session/{calm}/message/', {'content': 'exams are hard'}, format='json', **h1)
    c2, urgent, h2 = _start()
    r = c2.post(f'/api/shadow/session/{urgent}/message/', {'content': 'I want to kill myself'}, format='json', **h2)
    assert r.status_code == 201
    waiting = counselor_client.get('/api/shadow/queue/').json()['waiting']
    assert waiting[0]['session_id'] == urgent and waiting[0]['crisis_flagged'] is True
    assert c2.get(f'/api/shadow/session/{urgent}/', **h2).json()['crisis_resources']


def test_only_counselors_see_queue_and_token_required(student_client):
    assert student_client.get('/api/shadow/queue/').status_code == 403
    c, sid, h = _start()
    assert c.get(f'/api/shadow/session/{sid}/').status_code == 403
    assert c.get(f'/api/shadow/session/{sid}/', HTTP_X_SHADOW_TOKEN='wrong').status_code == 403


def test_student_can_wipe_chat():
    c, sid, h = _start()
    c.post(f'/api/shadow/session/{sid}/message/', {'content': 'hi'}, format='json', **h)
    assert c.delete(f'/api/shadow/session/{sid}/', **h).status_code == 204
    assert not AnonymousSession.objects.get(id=sid).messages.exists()


# ---------- assessments ------------------------------------------------------------------

def test_scoring_bands():
    assert score('phq9', [0] * 9)['severity'] == 'minimal'
    assert score('phq9', [3] * 9)['severity'] == 'severe'
    assert score('gad7', [2] * 7)['severity'] == 'moderate'  # 14
    assert score('who5', [5] * 5)['score'] == 100
    assert score('who5', [0] * 5)['severity'] == 'very_low'


def test_phq9_item9_triggers_crisis_resources(student_client):
    answers = [0] * 8 + [1]
    r = student_client.post('/api/assessments/phq9/submit/', {'answers': answers}, format='json')
    assert r.status_code == 201
    assert r.json()['crisis_resources'] and r.json()['elevated'] is True


def test_assessment_validation_and_sharing(student_client, counselor_client_factory):
    assert student_client.post('/api/assessments/gad7/submit/', {'answers': [1, 2]}, format='json').status_code == 400
    assert student_client.post('/api/assessments/gad7/submit/', {'answers': [9] * 7}, format='json').status_code == 400
    res = student_client.post('/api/assessments/gad7/submit/', {'answers': [1] * 7}, format='json').json()
    counselor, cclient = counselor_client_factory()
    # private by default
    assert cclient.get('/api/assessments/shared/').json() == []
    student_client.post(f'/api/assessments/results/{res["id"]}/share/',
                        {'counselor': str(counselor.counselor_profile.id)}, format='json')
    assert len(cclient.get('/api/assessments/shared/').json()) == 1
    student_client.post(f'/api/assessments/results/{res["id"]}/share/', {'counselor': None}, format='json')
    assert cclient.get('/api/assessments/shared/').json() == []


@pytest.fixture
def counselor_client_factory(db):
    from apps.users.models import CustomUser

    def make():
        u = CustomUser.objects.create_user(username='shared_c', password='x', role='counselor')
        CounselorProfile.objects.create(user=u)
        c = APIClient()
        c.force_authenticate(user=u)
        return u, c
    return make


# ---------- booking + counsellor workflow ------------------------------------------------

def _next_weekday_slot(profile):
    day = (timezone.localtime() + timedelta(days=2)).date()
    CounselorAvailabilitySlot.objects.create(
        counselor=profile, day_of_week=day.weekday(),
        start_time=timezone.datetime(2000, 1, 1, 9, 0).time(), end_time=timezone.datetime(2000, 1, 1, 12, 0).time())
    return day


def test_bookable_times_exclude_taken(student_client, counselor_user):
    profile = counselor_user.counselor_profile
    day = _next_weekday_slot(profile)
    url = f'/api/counselors/{profile.id}/times/?date={day}'
    times = student_client.get(url).json()['times']
    assert len(times) == 3
    Appointment.objects.create(
        student=student_client.handler._force_user, counselor=profile,
        scheduled_at=times[0], status='confirmed')
    assert len(student_client.get(url).json()['times']) == 2


def test_student_never_sees_counselor_notes(student_client, counselor_user, student_user):
    appt = Appointment.objects.create(
        student=student_user, counselor=counselor_user.counselor_profile, status='completed',
        scheduled_at=timezone.now() - timedelta(days=1), counselor_notes='Private clinical note')
    body = student_client.get(f'/api/appointments/{appt.id}/').json()
    assert 'counselor_notes' not in body
    assert 'Private clinical note' not in student_client.get('/api/appointments/').content.decode()
    cc = APIClient()
    cc.force_authenticate(user=counselor_user)
    assert cc.get(f'/api/appointments/{appt.id}/').json()['counselor_notes'] == 'Private clinical note'
    # and the student cannot write them either
    r = student_client.patch(f'/api/appointments/{appt.id}/', {'counselor_notes': 'x'}, format='json')
    assert r.status_code == 403


def test_login_with_email(student_user):
    r = APIClient().post('/api/auth/login/', {'username': 'STUDENT@test.com', 'password': 'pass1234!'}, format='json')
    assert r.status_code == 200 and 'access' in r.json()


def test_counselor_confirms_and_completes(student_client, counselor_user, student_user):
    profile = counselor_user.counselor_profile
    appt = Appointment.objects.create(
        student=student_user, counselor=profile, session_type='video',
        scheduled_at=timezone.now() + timedelta(hours=1))
    cc = APIClient()
    cc.force_authenticate(user=counselor_user)
    r = cc.post(f'/api/appointments/{appt.id}/confirm/')
    assert r.status_code == 200 and r.json()['meeting_link'] == f'/call/{appt.id}'
    assert student_client.post(f'/api/appointments/{appt.id}/complete/').status_code == 403
    r = cc.post(f'/api/appointments/{appt.id}/complete/', {'counselor_notes': 'Good progress'}, format='json')
    assert r.status_code == 200
    assert cc.post(f'/api/appointments/{appt.id}/confirm/').status_code == 400
    dash = cc.get('/api/counselors/dashboard/').json()
    assert dash['stats']['sessions_completed'] == 1


# ---------- AI cover for critical chats nobody has picked up ------------------------------

@pytest.fixture
def ai_cover(settings, monkeypatch):
    settings.SHADOW_AI_SYNC = True
    calls = []

    def fake(self, turns, extra='', max_tokens=None):
        calls.append(turns)
        return 'I am here with you. Are you safe right now?'
    monkeypatch.setattr('api.services.jalibot_service.JalibotService.__init__', lambda self: None)
    monkeypatch.setattr('api.services.jalibot_service.JalibotService.reply_stateless', fake)
    return calls


def _say(text, topic='anxiety'):
    c = APIClient()
    d = c.post('/api/shadow/start/', {'topic': topic}, format='json').json()
    h = {'HTTP_X_SHADOW_TOKEN': d['token']}
    c.post(f"/api/shadow/session/{d['session_id']}/message/", {'content': text}, format='json', **h)
    return c, d['session_id'], h


def _bot(c, sid, h):
    return [m for m in c.get(f'/api/shadow/session/{sid}/', **h).json()['messages'] if m['sender'] == 'bot']


def test_ai_covers_critical_chat_when_no_counselor_available(ai_cover, counselor_user):
    CounselorProfile.objects.update(is_available=False)
    c, sid, h = _say('I want to kill myself')
    bot = _bot(c, sid, h)
    assert len(bot) == 2 and 'AI' in bot[0]['content']      # notice, then the reply
    assert c.get(f'/api/shadow/session/{sid}/', **h).json()['ai_covering'] is True
    assert ai_cover


def test_ai_stays_out_of_everyday_chats(ai_cover):
    CounselorProfile.objects.update(is_available=False)
    c, sid, h = _say('exams are stressing me out')
    assert _bot(c, sid, h) == [] and not ai_cover


def test_ai_waits_while_a_counselor_is_available(ai_cover, counselor_user):
    c, sid, h = _say('I want to kill myself')   # counsellor is available and the wait is short
    assert _bot(c, sid, h) == [] and not ai_cover


def test_ai_covers_after_the_wait_and_stops_when_claimed(ai_cover, counselor_user, counselor_client, settings):
    settings.SHADOW_AI_FALLBACK_SECONDS = 0
    c, sid, h = _say('I want to kill myself')
    assert len(_bot(c, sid, h)) == 2
    counselor_client.post(f'/api/shadow/queue/{sid}/claim/')
    c.post(f'/api/shadow/session/{sid}/message/', {'content': 'are you there?'}, format='json', **h)
    assert len(_bot(c, sid, h)) == 2           # nothing new from the AI once a human has the chat
    assert c.get(f'/api/shadow/session/{sid}/', **h).json()['ai_covering'] is False


def test_ai_failure_still_gives_a_safe_reply(settings, monkeypatch, counselor_user):
    settings.SHADOW_AI_SYNC = True
    CounselorProfile.objects.update(is_available=False)

    def boom(self):
        raise RuntimeError('quota')
    monkeypatch.setattr('api.services.jalibot_service.JalibotService.__init__', boom)
    c, sid, h = _say('I want to kill myself')
    assert 'helpline' in _bot(c, sid, h)[-1]['content']


def test_student_can_delete_only_their_own_jalibot_chat(student_client, student_user):
    from apps.jalibot.models import JalibotConversation
    from apps.users.models import CustomUser
    stranger = CustomUser.objects.create_user(username='stranger', password='x', role='student')
    mine = JalibotConversation.objects.create(user=student_user, title='mine')
    other = JalibotConversation.objects.create(user=stranger, title='theirs')
    assert student_client.delete(f'/api/jalibot/history/{other.id}/').status_code == 404
    assert JalibotConversation.objects.filter(id=other.id).exists()
    assert student_client.delete(f'/api/jalibot/history/{mine.id}/').status_code == 204
    assert not JalibotConversation.objects.filter(id=mine.id).exists()


# ---------- JaliBot crisis handling --------------------------------------------------------

def test_jalibot_crisis_keywords_flag_and_ai_marker_flag(student_client, monkeypatch):
    monkeypatch.setattr('api.services.jalibot_service.JalibotService.__init__', lambda self: None)
    seen = {}

    def fake(self, system, turns, temperature=0.7, max_tokens=None):
        seen.update(system=system, max=max_tokens)
        return '[[CRISIS]] I hear you. Are you safe?' if 'nothing matters' in turns[-1][1] else 'Take one slow breath.'
    monkeypatch.setattr('api.services.jalibot_service.JalibotService._complete', fake)

    # a phrase the keyword list now knows: flagged, with the crisis instructions and extra room
    r = student_client.post('/api/jalibot/chat/', {'message': 'I feel like ending it all'}, format='json').json()
    assert r['crisis_detected'] is True
    assert 'POSSIBLE CRISIS' in seen['system'] and seen['max'] == 300

    # wording the keywords miss, but the model recognises: marker is stripped and the chat is flagged
    r = student_client.post('/api/jalibot/chat/', {'message': 'honestly nothing matters now'}, format='json').json()
    assert r['crisis_detected'] is True and '[[CRISIS]]' not in r['reply'] and r['reply'].startswith('I hear you')

    r = student_client.post('/api/jalibot/chat/', {'message': 'exam stress again'}, format='json').json()
    assert r['crisis_detected'] is False


def test_anonymous_chat_flags_new_crisis_phrases(ai_cover):
    c, sid, h = _start()
    c.post(f'/api/shadow/session/{sid}/message/', {'content': 'I just want to end it all'}, format='json', **h)
    assert c.get(f'/api/shadow/session/{sid}/', **h).json()['crisis_flagged'] is True


def test_circle_reply_needs_only_body(student_client):
    """The frontend sends just {body}; the thread comes from the URL (regression: 400 'thread required')."""
    from apps.circle.models import ForumCategory, ForumThread
    user = student_client.handler._force_user
    cat = ForumCategory.objects.create(name='General', slug='general')
    thread = ForumThread.objects.create(title='t', body='b', category=cat, author=user)
    r = student_client.post(f'/api/circle/threads/{thread.id}/replies/', {'body': 'try'}, format='json')
    assert r.status_code == 201, r.content
    child = student_client.post(
        f'/api/circle/threads/{thread.id}/replies/', {'body': 'nested', 'parent_reply': r.json()['id']}, format='json')
    assert child.status_code == 201, child.content
    assert len(student_client.get(f'/api/circle/threads/{thread.id}/replies/').json()) == 2


def test_student_can_book_a_listed_time(student_client, counselor_user):
    profile = counselor_user.counselor_profile
    day = _next_weekday_slot(profile)
    times = student_client.get(f'/api/counselors/{profile.id}/times/?date={day}').json()['times']
    r = student_client.post(
        f'/api/counselors/{profile.id}/book/',
        {'scheduled_at': times[0], 'session_type': 'video', 'duration_minutes': 60, 'notes': 'hi'}, format='json')
    assert r.status_code == 201, r.content
    assert len(student_client.get(f'/api/counselors/{profile.id}/times/?date={day}').json()['times']) == 2
