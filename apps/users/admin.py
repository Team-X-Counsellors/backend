from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'university', 'is_active', 'consent_given', 'date_joined']
    list_filter = ['role', 'is_active', 'consent_given', 'university']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'university']
    ordering = ['-date_joined']
    fieldsets = UserAdmin.fieldsets + (
        ('JaliMind Profile', {
            'fields': ('role', 'university', 'phone_number', 'preferred_language',
                       'consent_given', 'consent_given_at', 'is_anonymous_allowed', 'profile_photo'),
        }),
    )
