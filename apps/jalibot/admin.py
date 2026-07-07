from django.contrib import admin
from .models import JalibotConversation, JalibotMemory


@admin.register(JalibotConversation)
class JalibotConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'title', 'crisis_detected', 'referred_to_counselor', 'session_started_at', 'language']
    list_filter = ['crisis_detected', 'referred_to_counselor', 'language']
    search_fields = ['user__username']
    readonly_fields = ['id', 'session_started_at', 'last_message_at', 'messages']
    ordering = ['-session_started_at']


@admin.register(JalibotMemory)
class JalibotMemoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'category', 'content', 'created_at']
    list_filter = ['category']
    search_fields = ['user__username', 'content']
    readonly_fields = ['id', 'user', 'content', 'category', 'source_conversation', 'created_at']
    ordering = ['-created_at']
