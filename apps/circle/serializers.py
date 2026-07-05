from rest_framework import serializers
from .models import ForumCategory, ForumThread, ForumReply, AuditLog


class ForumCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ForumCategory
        fields = ['id', 'name', 'slug', 'description', 'icon', 'order', 'is_active']


class ForumThreadSerializer(serializers.ModelSerializer):
    author_display = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=ForumCategory.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ForumThread
        fields = [
            'id', 'category', 'category_name', 'author_display',
            'title', 'body', 'is_moderated', 'is_pinned', 'is_closed',
            'reply_count', 'view_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'is_moderated', 'is_pinned', 'reply_count',
            'view_count', 'created_at',
        ]

    def get_author_display(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return obj.anonymous_display_name or 'Anonymous'


class ForumReplySerializer(serializers.ModelSerializer):
    author_display = serializers.SerializerMethodField()

    class Meta:
        model = ForumReply
        fields = [
            'id', 'thread', 'author_display', 'body',
            'parent_reply', 'is_moderated', 'created_at',
        ]
        read_only_fields = ['id', 'is_moderated', 'created_at']

    def get_author_display(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return obj.anonymous_display_name or 'Anonymous'


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'actor_name', 'action', 'target_model',
            'target_id', 'metadata', 'ip_address', 'created_at',
        ]
        read_only_fields = fields
