from rest_framework import serializers


class ShadowStartResponseSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    pseudonym = serializers.CharField()
    token = serializers.CharField()
    expires_at = serializers.DateTimeField()


class ShadowMessageSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=2000, trim_whitespace=True)

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError('Message content cannot be empty.')
        return value


class ShadowMessageResponseSerializer(serializers.Serializer):
    sender = serializers.CharField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField()


class ShadowSessionDetailSerializer(serializers.Serializer):
    pseudonym = serializers.CharField()
    messages = ShadowMessageResponseSerializer(many=True)
    expires_at = serializers.DateTimeField()
    crisis_flagged = serializers.BooleanField()
