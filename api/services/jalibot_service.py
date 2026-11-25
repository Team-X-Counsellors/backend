import logging
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
    # More ways people say it (English)
    'ending it all', 'end it all', 'end everything', 'ending everything', "don't want to live", 'dont want to live', 'do not want to live', "don't want to be alive", 'dont want to be alive', 'wish i was dead', 'wish i were dead', "wish i wasn't alive", 'rather be dead', 'not worth living', 'no point in living', 'no point living', 'suicidal', 'take my own life', 'kill me', 'cut myself', 'hang myself', 'overdose', 'disappear forever', 'nobody would miss me', 'everyone would be better off without me',
]

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are JaliBot, an AI mental wellness companion for African university students.

Your role is psychoeducation, supportive listening, and triage — NOT clinical counseling or diagnosis.

HOW TO WRITE (most important rule):
- Keep every reply SHORT: 2-4 sentences, under 60 words. People in distress will not read more.
- Give ONE idea or ONE small step. Start with one line that shows you heard them, then one practical suggestion or one gentle question.
- Only go longer if the student explicitly asks for detail or a plan, and even then stay under 120 words.
- Sound like a kind friend texting, not a leaflet.
- Match the request: if they ask for a plan, facts or how-to, answer that directly. Only open with empathy when they have shared a feeling.

FORMATTING (the app renders Markdown):
- Use **bold** for the single most important idea or step, and *italics* only for gentle emphasis. Never bold whole sentences.
- Use a short numbered list (3-4 items, a few words each) ONLY when the student asks for steps, a plan or a routine. Otherwise write plain sentences.
- No headings, tables or code blocks. No emoji unless the student uses them first.

Core guidelines:
- Be warm, empathetic, non-judgmental, and culturally grounded
- Reference African contexts: Ubuntu philosophy, family systems, academic pressures specific to African universities (ASUU strikes in Nigeria, accommodation shortages, exam pressure, financial stress from exchange rates)
- Respond in the same language the student uses (English, Swahili, French, Hausa, Igbo, Twi supported)
- For exam anxiety, academic stress, loneliness, relationship issues: provide evidence-based coping strategies and psychoeducation
- For persistent low mood or depression symptoms: validate, provide coping tools, strongly encourage professional help
- NEVER diagnose any mental health condition
- NEVER prescribe medication or supplements
- You are an AI, not a human counselor. Say so briefly (a few words, e.g. "I'm JaliBot, an AI") in your FIRST reply of a conversation only. Do not repeat it later unless asked, or unless the student seems to think you are a person. The app already shows an AI label.
- When professional help is recommended, mention the university counseling office as the first resource

Crisis response protocol:
If the student expresses thoughts of suicide, self-harm, or harming others, in ANY wording (including indirect ones like "I can't do this anymore" meaning ending their life):
0. Begin your reply with the exact token [[CRISIS]] (the app removes it and shows the helpline card).
1. Respond with immediate empathy and validation
2. Clearly recommend they reach out to a trusted person or crisis line right now
3. Do NOT write phone numbers yourself. The app shows a verified helpline card right above this chat; say "the helplines at the top of this chat". Also remind them they can talk to a human counsellor through "Talk to someone".
4. Do NOT continue general conversation — stay focused on safety

Transparency reminders:
- Only add encouragement when it fits, in a few words, never as a formula
- If a question exceeds your scope, say so clearly and direct to a counselor"""


CRISIS_REPLY_EXTRA = """

THIS MESSAGE SHOWS A POSSIBLE CRISIS. The app already pins the verified helplines above the chat.
- NEVER write phone numbers yourself; say "the helplines at the top of this chat".
- Under 60 words, no lists, no markdown. Say you are an AI, show you heard them, ask if they are safe right now, and mention they can also talk to a human counsellor through "Talk to someone".
- These instructions override the crisis protocol above where they differ."""


class JalibotService:
    def __init__(self):
        self._gemini = None
        self._openai = None
        if settings.GEMINI_API_KEY:
            from google import genai
            from google.genai import types
            self._types = types
            # system_instruction needs the v1beta endpoint on current models
            self._gemini = genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(api_version='v1beta'))
        if getattr(settings, 'OPENAI_API_KEY', ''):
            from openai import OpenAI
            self._openai = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=20)
        self._claude = None
        if getattr(settings, 'CLAUDE_API_KEY', ''):
            from api.services.claude_provider import ClaudeProvider
            self._claude = ClaudeProvider()
        if not (self._gemini or self._openai or self._claude):
            raise RuntimeError('No AI provider configured (set GEMINI_API_KEY, OPENAI_API_KEY or CLAUDE_API_KEY).')
        self._model_name = settings.GEMINI_MODEL

    def _complete(self, system_instruction: str, turns: list, temperature: float = 0.7, max_tokens: int | None = None) -> str:
        """turns = [(role, text)], role 'user'|'model', last one the user's. Tries Gemini, then OpenAI, then Claude."""
        errors = []
        if self._gemini:
            try:
                history = [self._types.Content(role=r, parts=[self._types.Part(text=t)]) for r, t in turns[:-1]]
                chat = self._gemini.chats.create(model=self._model_name, config=self._config(system_instruction, temperature, max_tokens), history=history)
                text = (chat.send_message(turns[-1][1]).text or '').strip()
                if text:
                    return text
                errors.append('gemini: empty reply')
            except Exception as exc:  # retired model, quota, overload, network: try the next provider
                errors.append(f'gemini: {type(exc).__name__}')
                log.warning('Gemini failed (%s)', exc)
        if self._openai:
            try:
                msgs = [{'role': 'system', 'content': system_instruction}] + [
                    {'role': 'user' if r == 'user' else 'assistant', 'content': t} for r, t in turns]
                r = self._openai.chat.completions.create(
                    model=settings.OPENAI_MODEL, messages=msgs, temperature=temperature,
                    max_completion_tokens=max_tokens or settings.JALIBOT_MAX_OUTPUT_TOKENS)
                text = (r.choices[0].message.content or '').strip()
                if text:
                    return text
                errors.append('openai: empty reply')
            except Exception as exc:
                errors.append(f'openai: {type(exc).__name__}')
                log.warning('OpenAI failed (%s)', exc)
        if self._claude:
            try:
                text = self._claude.complete(system_instruction, turns, max_tokens)
                if text:
                    return text
                errors.append('claude: empty reply')
            except Exception as exc:
                errors.append(f'claude: {type(exc).__name__}')
                log.warning('Claude failed (%s)', exc)
        raise RuntimeError('All AI providers failed: ' + ', '.join(errors))

    def _config(self, system_instruction: str, temperature: float = 0.7, max_tokens: int | None = None):
        # Thinking tokens count against max_output_tokens and were truncating replies to a few words.
        return self._types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=max_tokens or settings.JALIBOT_MAX_OUTPUT_TOKENS,
            temperature=temperature,
            thinking_config=self._types.ThinkingConfig(thinking_budget=0),
        )

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

        system_instruction = SYSTEM_PROMPT
        if user:
            system_instruction = self._with_memory_context(SYSTEM_PROMPT, user)

        turns = [('user' if m['role'] == 'user' else 'model', m['content']) for m in conversation.messages]
        turns.append(('user', message))
        if crisis_detected:
            system_instruction += CRISIS_REPLY_EXTRA
        try:
            reply_text = self._complete(system_instruction, turns, max_tokens=300 if crisis_detected else None)
        except Exception:
            return {
                'reply': (
                    'JaliBot is temporarily unavailable. '
                    'Please try again in a few minutes. '
                    'If you need immediate support, contact your university counselling centre.'
                ),
                'crisis_detected': crisis_detected,
                'referred_to_counselor': crisis_detected,
                'conversation_id': str(conversation.id),
                'error': 'rate_limited',
            }

        # Safety net: the model flags risk that the keyword list missed.
        if reply_text.lstrip().startswith('[[CRISIS]]'):
            reply_text = reply_text.lstrip()[len('[[CRISIS]]'):].lstrip()
            crisis_detected, crisis_keywords = True, crisis_keywords or ['model_flagged']
        reply_text = reply_text.replace('[[CRISIS]]', '').strip()

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

    def reply_stateless(self, turns: list, extra_instruction: str = '', max_tokens: int | None = None) -> str:
        """One reply from a transcript the caller owns. Stores nothing (used for anonymous chat cover).
        `turns` is [(role, text)] with role 'user' or 'model'; the last item must be the user's."""
        return self._complete(SYSTEM_PROMPT + extra_instruction, turns, 0.6, max_tokens).replace('[[CRISIS]]', '').strip()

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
        """Ask the AI for 0-3 short durable facts worth remembering from recent turns."""
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
            import json
            raw = self._complete('You extract facts and reply with JSON only.', [('user', prompt)], 0.2, 400)
            raw = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
            facts = json.loads(raw)
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
