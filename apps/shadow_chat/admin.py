from django.contrib import admin
from .models import AnonymousSession, AnonymousMessage


class AnonymousMessageInline(admin.TabularInline):
    model = AnonymousMessage
    extra = 0
    readonly_fields = ['sender', 'content', 'created_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AnonymousSession)
class AnonymousSessionAdmin(admin.ModelAdmin):
    list_display = ['pseudonym', 'created_at', 'expires_at', 'is_active', 'crisis_flagged']
    list_filter = ['is_active', 'crisis_flagged']
    readonly_fields = ['id', 'pseudonym', 'token_hash', 'created_at', 'expires_at']
    search_fields = ['pseudonym']
    inlines = [AnonymousMessageInline]
