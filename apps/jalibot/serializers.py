from rest_framework import serializers

from .models import JalibotMemory


class JalibotMessageSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, trim_whitespace=True)
    language = serializers.ChoiceField(
        choices=['en', 'sw', 'fr', 'ha', 'ig', 'tw'],
        default='en',
    )
    # For anonymous sessions — client provides these instead of JWT
    anonymous_session_id = serializers.UUIDField(required=False, allow_null=True)
    anonymous_token = serializers.CharField(required=False, allow_blank=True)
    conversation_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError('Message cannot be empty.')
        return value


class JalibotResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    crisis_detected = serializers.BooleanField()
    referred_to_counselor = serializers.BooleanField()
    conversation_id = serializers.UUIDField()


class JalibotMemorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JalibotMemory
        fields = ['id', 'content', 'category', 'created_at', 'source_conversation']
        read_only_fields = fields
