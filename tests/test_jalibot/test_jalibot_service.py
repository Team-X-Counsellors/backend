import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestJalibotService:
    @patch('api.services.jalibot_service.JalibotService.__init__', return_value=None)
    def test_crisis_detection_english(self, mock_init):
        from api.services.jalibot_service import JalibotService
        service = JalibotService.__new__(JalibotService)
        detected, keywords = service.detect_crisis('I want to kill myself tonight')
        assert detected is True
        assert 'kill myself' in keywords

    @patch('api.services.jalibot_service.JalibotService.__init__', return_value=None)
    def test_no_crisis_normal_message(self, mock_init):
        from api.services.jalibot_service import JalibotService
        service = JalibotService.__new__(JalibotService)
        detected, keywords = service.detect_crisis('I am stressed about my exams')
        assert detected is False
        assert keywords == []

    @patch('api.services.jalibot_service.JalibotService.__init__', return_value=None)
    def test_crisis_detection_swahili(self, mock_init):
        from api.services.jalibot_service import JalibotService
        service = JalibotService.__new__(JalibotService)
        detected, keywords = service.detect_crisis('ninataka kujiua')
        assert detected is True

    @patch('google.genai.Client')
    def test_normal_chat_response(self, MockClient, db, student_user):
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'I hear you. Exam stress is tough. Here are some strategies...'
        mock_chat.send_message.return_value = mock_response
        MockClient.return_value.chats.create.return_value = mock_chat

        from api.services.jalibot_service import JalibotService
        service = JalibotService()
        result = service.chat(message='I am stressed about exams', user=student_user)

        assert result['crisis_detected'] is False
        assert result['referred_to_counselor'] is False
        assert 'conversation_id' in result
        assert result['reply'] == mock_response.text

    @patch('google.genai.Client')
    def test_crisis_chat_sets_flags(self, MockClient, db, student_user):
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'I am very concerned. Please reach out to Befrienders Kenya now.'
        mock_chat.send_message.return_value = mock_response
        MockClient.return_value.chats.create.return_value = mock_chat

        from api.services.jalibot_service import JalibotService
        service = JalibotService()
        result = service.chat(message='I want to kill myself', user=student_user)

        assert result['crisis_detected'] is True
        assert result['referred_to_counselor'] is True

        from apps.jalibot.models import JalibotConversation
        convo = JalibotConversation.objects.get(user=student_user)
        assert convo.crisis_detected is True

    @patch('google.genai.Client')
    def test_rate_limit_blocks_without_calling_gemini(self, MockClient, db, student_user):
        from apps.jalibot.models import JalibotConversation
        from django.conf import settings

        convo = JalibotConversation.objects.create(
            user=student_user,
            message_count_this_hour=settings.JALIBOT_RATE_LIMIT,
            hour_window_start=timezone.now(),
        )

        from api.services.jalibot_service import JalibotService
        service = JalibotService()
        result = service.chat(message='Another message', user=student_user)

        assert 'limit' in result['reply'].lower()
        # Gemini client should NOT have been called
        MockClient.return_value.chats.create.assert_not_called()
