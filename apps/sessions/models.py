import uuid
from django.db import models
from django.conf import settings


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        NO_SHOW = 'no_show', 'No Show'

    class SessionType(models.TextChoices):
        VIDEO = 'video', 'Video'
        TEXT = 'text', 'Text Chat'
        ANONYMOUS = 'anonymous', 'Anonymous Text'
        VOICE = 'voice', 'Voice'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='student_appointments',
    )
    counselor = models.ForeignKey(
        'counselors.CounselorProfile',
        on_delete=models.SET_NULL,
        null=True,
        related_name='counselor_appointments',
    )
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    session_type = models.CharField(max_length=12, choices=SessionType.choices, default=SessionType.TEXT)
    notes = models.TextField(blank=True)
    counselor_notes = models.TextField(blank=True)
    cancellation_reason = models.CharField(max_length=300, blank=True)
    meeting_link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sessions_appointment'
        ordering = ['-scheduled_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['counselor', 'scheduled_at']),
        ]

    def __str__(self):
        return f"Appointment {self.id} — {self.status}"


class AppointmentReview(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='review',
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sessions_review'
