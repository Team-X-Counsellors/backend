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

    def _get_or_create_conversation(self, user, anonymous_session, language, conversation_id=None):
        from apps.jalibot.models import JalibotConversation

        if conversation_id:
            owner_filter = {'user': user} if user else {'anonymous_session_id': anonymous_session.id, 'user': None}
            try:
                conversation = JalibotConversation.objects.get(id=conversation_id, **owner_filter)
                timeout = timedelta(minutes=settings.JALIBOT_CONVERSATION_TIMEOUT_MINUTES)
                if timezone.now() - conversation.last_message_at <= timeout:
                    return conversation
            except JalibotConversation.DoesNotExist:
                pass

        # No conversation_id (or a stale/invalid one): start a fresh conversation.
        # Callers that want to resume an existing conversation must pass its id explicitly.
        if user:
            return JalibotConversation.objects.create(user=user, language=language)
        return JalibotConversation.objects.create(
            anonymous_session_id=anonymous_session.id,
            user=None,
            language=language,
        )

    def chat(self, message: str, language: str = 'en', user=None, anonymous_session=None, conversation_id=None) -> dict:
        conversation = self._get_or_create_conversation(user, anonymous_session, language, conversation_id)

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

        system_instruction = SYSTEM_PROMPT
        if user:
            system_instruction = self._with_memory_context(SYSTEM_PROMPT, user)

        chat = self._client.chats.create(
            model=self._model_name,
            config=self._types.GenerateContentConfig(
                system_instruction=system_instruction,
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

        if not conversation.messages and not conversation.title:
            conversation.title = message[:60] + ('…' if len(message) > 60 else '')

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

        if user and len(conversation.messages) % 10 == 0:
            self._extract_and_store_memories(user, conversation)

        return {
            'reply': reply_text,
            'crisis_detected': crisis_detected,
            'referred_to_counselor': referred,
            'conversation_id': str(conversation.id),
        }

    def _with_memory_context(self, base_prompt: str, user) -> str:
        from apps.jalibot.models import JalibotMemory

        memories = list(
            JalibotMemory.objects.filter(user=user).order_by('-created_at')[:15]
        )
        if not memories:
            return base_prompt
        facts = '\n'.join(f'- {m.content}' for m in memories)
        return f"{base_prompt}\n\nWhat you remember about this student:\n{facts}"

    def extract_facts(self, messages: list[dict]) -> list[dict]:
        """Ask Gemini for 0-3 short durable facts worth remembering from recent turns."""
        transcript = '\n'.join(f"{m['role']}: {m['content']}" for m in messages)
        prompt = (
            "From the conversation excerpt below, extract 0 to 3 short, durable facts worth "
            "remembering about the student for future conversations (e.g. goals, ongoing struggles, "
            "family/academic context). Skip anything trivial or already obvious. "
            "Return a JSON array of objects with 'content' (a short sentence, max 300 chars) and "
            "'category' (one of: academic, emotional, family, career, other). "
            "Return an empty array if nothing durable stands out.\n\n"
            f"Conversation:\n{transcript}"
        )
        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=self._types.GenerateContentConfig(
                    response_mime_type='application/json',
                    max_output_tokens=300,
                ),
            )
            import json
            facts = json.loads(response.text)
            return facts if isinstance(facts, list) else []
        except Exception:
            return []

    def _extract_and_store_memories(self, user, conversation) -> None:
        from apps.jalibot.models import JalibotMemory

        recent_messages = conversation.messages[-10:]
        facts = self.extract_facts(recent_messages)
        if not facts:
            return

        existing = list(
            JalibotMemory.objects.filter(user=user).order_by('-created_at')[:20]
            .values_list('content', flat=True)
        )
        existing_lower = [e.lower() for e in existing]

        new_memories = []
        for fact in facts:
            content = str(fact.get('content', '')).strip()[:300]
            if not content or content.lower() in existing_lower:
                continue
            category = fact.get('category')
            if category not in dict(JalibotMemory.Category.choices):
                category = JalibotMemory.Category.OTHER
            new_memories.append(JalibotMemory(
                user=user,
                content=content,
                category=category,
                source_conversation=conversation,
            ))

        if new_memories:
            JalibotMemory.objects.bulk_create(new_memories)
