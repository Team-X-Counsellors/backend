"""Claude as a provider for JaliBot. Kept in its own module: only Anthropic SDK calls live here."""
import anthropic
from django.conf import settings


class ClaudeProvider:
    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY, timeout=30.0, max_retries=1)
        self._model = settings.CLAUDE_MODEL

    def complete(self, system: str, turns: list, max_tokens: int | None = None) -> str:
        """turns = [(role, text)] with role 'user' | 'model'; the last one is the user's.

        Current Claude models take no temperature, always think, and ignore prefill, so brevity is
        steered by the system prompt and low effort. max_tokens includes thinking, hence the headroom.
        """
        messages = [{'role': 'user' if r == 'user' else 'assistant', 'content': t} for r, t in turns]
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max(1024, (max_tokens or 0) * 4),
            system=system,
            messages=messages,
            output_config={'effort': 'low'},
        )
        if response.stop_reason == 'refusal':
            raise RuntimeError('Claude declined this request')
        return ''.join(b.text for b in response.content if b.type == 'text').strip()
