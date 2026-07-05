from django.contrib import admin
from .models import ForumCategory, ForumThread, ForumReply, AuditLog


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order', 'is_active']
    list_filter = ['is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'is_moderated', 'is_pinned', 'reply_count', 'created_at']
    list_filter = ['is_moderated', 'is_pinned', 'is_closed', 'category']
    search_fields = ['title', 'body', 'author__username']
    readonly_fields = ['id', 'reply_count', 'view_count', 'created_at', 'updated_at']
    actions = ['moderate_threads', 'unmoderate_threads']

    @admin.action(description='Mark selected threads as moderated (hidden)')
    def moderate_threads(self, request, queryset):
        queryset.update(is_moderated=True)

    @admin.action(description='Unmoderate selected threads (show)')
    def unmoderate_threads(self, request, queryset):
        queryset.update(is_moderated=False)


@admin.register(ForumReply)
class ForumReplyAdmin(admin.ModelAdmin):
    list_display = ['thread', 'author', 'is_moderated', 'created_at']
    list_filter = ['is_moderated']
    search_fields = ['body', 'author__username']
    readonly_fields = ['id', 'created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'actor', 'target_model', 'target_id', 'ip_address', 'created_at']
    list_filter = ['action', 'target_model']
    search_fields = ['actor__username', 'target_id']
    readonly_fields = list_display + ['metadata']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
