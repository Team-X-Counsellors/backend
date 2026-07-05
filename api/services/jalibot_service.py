from datetime import timedelta
from django.conf import settings
from django.utils import timezone

CRISIS_KEYWORDS = [
    # English
    'suicide', 'kill myself', 'end my life', 'want to die', 'self-harm',
    'hurt myself', 'no reason to live', 'take my life', 'better off dead',
    'cant go on', "can't go on", 'give up on life',
    # Swahili
    'kujiua', 'kujidhuru', 'ninataka kufa',
    # French
    'je veux mourir', 'me suicider', 'me tuer',
    # Hausa
    'kashe kaina',
    # Igbo
    'igbu onwe m',
]

SYSTEM_PROMPT = """You are JaliBot, an AI mental wellness companion for African university students.

Your role is psychoeducation, supportive listening, and triage — NOT clinical counseling or diagnosis.

Core guidelines:
- Be warm, empathetic, non-judgmental, and culturally grounded
- Reference African contexts: Ubuntu philosophy, family systems, academic pressures specific to African universities (ASUU strikes in Nigeria, accommodation shortages, exam pressure, financial stress from exchange rates)
- Respond in the same language the student uses (English, Swahili, French, Hausa, Igbo, Twi supported)
- For exam anxiety, academic stress, loneliness, relationship issues: provide evidence-based coping strategies and psychoeducation
- For persistent low mood or depression symptoms: validate, provide coping tools, strongly encourage professional help
- NEVER diagnose any mental health condition
- NEVER prescribe medication or supplements
- ALWAYS make clear you are an AI and not a human counselor
- When professional help is recommended, mention the university counseling office as the first resource

Crisis response protocol:
If the student expresses thoughts of suicide, self-harm, or harming others:
1. Respond with immediate empathy and validation
2. Clearly recommend they reach out to a trusted person or crisis line right now
3. Provide these African crisis resources:
   - Kenya: Befrienders Kenya — +254 722 178 177
   - Nigeria: SURPIN — +234 806 210 6493
   - Ghana: Mental Health Authority — 0800 111 222
   - South Africa: SADAG — 0800 456 789
   - All: Contact your university counseling center immediately
4. Do NOT continue general conversation — stay focused on safety

Transparency reminders:
- Begin each conversation by noting you are an AI assistant
- End responses with gentle encouragement
- If a question exceeds your scope, say so clearly and direct to a counselor"""


class JalibotService:
    def __init__(self):
        from google import genai
        from google.genai import types
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._types = types
        self._model_name = settings.GEMINI_MODEL

    def detect_crisis(self, message: str) -> tuple:
        lower = message.lower()
        found = [kw for kw in CRISIS_KEYWORDS if kw in lower]
        return bool(found), found

    def _check_rate_limit(self, conversation) -> bool:
        now = timezone.now()
        if now - conversation.hour_window_start > timedelta(hours=1):
            conversation.message_count_this_hour = 0
            conversation.hour_window_start = now
            conversation.save(update_fields=['message_count_this_hour', 'hour_window_start'])
        return conversation.message_count_this_hour < settings.JALIBOT_RATE_LIMIT

    def _get_or_create_conversation(self, user, anonymous_session, language):
        from apps.jalibot.models import JalibotConversation
        if user:
            conversation, _ = JalibotConversation.objects.get_or_create(
                user=user,
                defaults={'language': language},
            )
        else:
            conversation, _ = JalibotConversation.objects.get_or_create(
                anonymous_session_id=anonymous_session.id,
                user=None,
                defaults={'language': language},
            )
        return conversation

    def chat(self, message: str, language: str = 'en', user=None, anonymous_session=None) -> dict:
        conversation = self._get_or_create_conversation(user, anonymous_session, language)

        if not self._check_rate_limit(conversation):
            return {
                'reply': (
                    'You have reached the message limit for this hour. '
                    'Please take a short break — your wellbeing matters. '
                    'If this is urgent, please contact your university counseling center.'
                ),
                'crisis_detected': False,
                'referred_to_counselor': False,
                'conversation_id': str(conversation.id),
            }

        crisis_detected, crisis_keywords = self.detect_crisis(message)

        # Build Gemini conversation history
        history = []
        for msg in conversation.messages:
            role = 'user' if msg['role'] == 'user' else 'model'
            history.append(self._types.Content(
                role=role,
                parts=[self._types.Part(text=msg['content'])],
            ))

        chat = self._client.chats.create(
            model=self._model_name,
            config=self._types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
            history=history,
        )
        try:
            response = chat.send_message(message)
            reply_text = response.text
        except Exception as exc:
            from google.genai.errors import ClientError
            if isinstance(exc, ClientError) and exc.code == 429:
                return {
                    'reply': (
                        'JaliBot is temporarily unavailable due to high demand. '
                        'Please try again in a few minutes. '
                        'If you need immediate support, contact your university counseling centre.'
                    ),
                    'crisis_detected': crisis_detected,
                    'referred_to_counselor': crisis_detected,
                    'conversation_id': str(conversation.id),
                    'error': 'rate_limited',
                }
            raise

        now_iso = timezone.now().isoformat()
        conversation.messages.append({'role': 'user', 'content': message, 'timestamp': now_iso})
        conversation.messages.append({'role': 'model', 'content': reply_text, 'timestamp': now_iso})
        conversation.message_count_this_hour += 1

        referred = False
        if crisis_detected:
            conversation.crisis_detected = True
            conversation.crisis_keywords_found = list(
                set(conversation.crisis_keywords_found + crisis_keywords)
            )
            conversation.referred_to_counselor = True
            referred = True

        conversation.save()

        if anonymous_session and crisis_detected:
            anonymous_session.crisis_flagged = True
            anonymous_session.save(update_fields=['crisis_flagged'])

        return {
            'reply': reply_text,
            'crisis_detected': crisis_detected,
            'referred_to_counselor': referred,
            'conversation_id': str(conversation.id),
        }
