from django.contrib import admin
from .models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'resource_type', 'language', 'is_published', 'view_count', 'created_at']
    list_filter = ['resource_type', 'language', 'is_published']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'view_count', 'created_at', 'updated_at']
    ordering = ['-created_at']
