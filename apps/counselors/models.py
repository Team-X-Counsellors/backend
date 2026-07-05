import uuid
from django.db import models
from django.conf import settings


class CounselorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='counselor_profile',
    )
    bio = models.TextField(blank=True)
    specialties = models.JSONField(default=list)
    languages = models.JSONField(default=list)
    years_experience = models.PositiveSmallIntegerField(default=0)
    license_number = models.CharField(max_length=100, blank=True)
    license_verified = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_sessions = models.PositiveIntegerField(default=0)
    accepts_anonymous = models.BooleanField(default=True)
    avatar = models.ImageField(upload_to='counselors/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'counselors_profile'

    def __str__(self):
        return f"Counselor: {self.user.get_full_name()}"


class CounselorAvailabilitySlot(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, 'Monday'
        TUESDAY = 1, 'Tuesday'
        WEDNESDAY = 2, 'Wednesday'
        THURSDAY = 3, 'Thursday'
        FRIDAY = 4, 'Friday'
        SATURDAY = 5, 'Saturday'
        SUNDAY = 6, 'Sunday'

    counselor = models.ForeignKey(
        CounselorProfile,
        on_delete=models.CASCADE,
        related_name='availability_slots',
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'counselors_availability_slot'
        unique_together = ('counselor', 'day_of_week', 'start_time')
