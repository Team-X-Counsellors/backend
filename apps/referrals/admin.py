from django.contrib import admin
from .models import CampusResource, Referral


@admin.register(CampusResource)
class CampusResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'university', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'university')


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('student', 'resource', 'status', 'created_at')
    list_filter = ('status',)
