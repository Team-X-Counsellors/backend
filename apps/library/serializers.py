from rest_framework import serializers
from .models import Resource


class ResourceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name', read_only=True
    )

    class Meta:
        model = Resource
        fields = [
            'id', 'title', 'description', 'resource_type', 'tags',
            'language', 'content_url', 'file', 'thumbnail',
            'uploaded_by_name', 'is_published', 'view_count', 'created_at',
        ]
        read_only_fields = ['id', 'view_count', 'created_at', 'uploaded_by_name']

    def create(self, validated_data):
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)
