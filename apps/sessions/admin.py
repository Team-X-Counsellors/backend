from django.contrib import admin
from .models import Appointment, AppointmentReview


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'counselor', 'scheduled_at', 'status', 'session_type']
    list_filter = ['status', 'session_type']
    search_fields = ['student__username', 'counselor__user__username']
    ordering = ['-scheduled_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(AppointmentReview)
class AppointmentReviewAdmin(admin.ModelAdmin):
    list_display = ['appointment', 'rating', 'created_at']
    readonly_fields = ['created_at']
