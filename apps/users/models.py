from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        COUNSELOR = 'counselor', 'Counselor'
        ADMIN = 'admin', 'Admin'
        SUPER_ADMIN = 'superadmin', 'Super Admin'

    role = models.CharField(max_length=12, choices=Role.choices, default=Role.STUDENT)
    university = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    preferred_language = models.CharField(max_length=10, default='en')
    consent_given = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    is_anonymous_allowed = models.BooleanField(default=True)
    profile_photo = models.ImageField(upload_to='profiles/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users_customuser'

    def is_student(self):
        return self.role == self.Role.STUDENT

    def is_counselor(self):
        return self.role == self.Role.COUNSELOR

    def is_admin(self):
        return self.role in (self.Role.ADMIN, self.Role.SUPER_ADMIN)

    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN
