import uuid
from django.conf import settings
from django.db import models


class CampusResource(models.Model):
    """A real office a student can be referred to (managed by admins in the Django admin)."""

    class Category(models.TextChoices):
        GUIDANCE = 'guidance', 'Guidance & counselling office'
        ACADEMIC = 'academic', 'Academic advisor'
        CAREER = 'career', 'Career services'
        FINANCE = 'finance', 'Student finance / bursary'
        HEALTH = 'health', 'Campus clinic'
        SECURITY = 'security', 'Campus security / safety'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    university = models.CharField(max_length=200, help_text='Blank = available to every university')
    category = models.CharField(max_length=12, choices=Category.choices)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(max_length=20, blank=True, help_text='Digits only, with country code')
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'referrals_campus_resource'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.university or "all"})'


class Referral(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        CONTACTED = 'contacted', 'Contacted'
        DONE = 'done', 'Done'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referrals')
    resource = models.ForeignKey(CampusResource, on_delete=models.PROTECT, related_name='referrals')
    # Set when a counsellor refers on the student's behalf.
    referred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals_made',
    )
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'referrals_referral'
        ordering = ['-created_at']
