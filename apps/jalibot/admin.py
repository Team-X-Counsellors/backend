from django.contrib import admin
from .models import JalibotConversation


@admin.register(JalibotConversation)
class JalibotConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'crisis_detected', 'referred_to_counselor', 'session_started_at', 'language']
    list_filter = ['crisis_detected', 'referred_to_counselor', 'language']
    search_fields = ['user__username']
    readonly_fields = ['id', 'session_started_at', 'last_message_at', 'messages']
    ordering = ['-session_started_at']
