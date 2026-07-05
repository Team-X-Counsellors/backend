from django.contrib import admin
from .models import CounselorProfile, CounselorAvailabilitySlot


class AvailabilitySlotInline(admin.TabularInline):
    model = CounselorAvailabilitySlot
    extra = 0


@admin.register(CounselorProfile)
class CounselorProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_available', 'rating', 'total_sessions', 'license_verified', 'accepts_anonymous']
    list_filter = ['is_available', 'license_verified', 'accepts_anonymous']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    inlines = [AvailabilitySlotInline]
    readonly_fields = ['rating', 'total_sessions']
