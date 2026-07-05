import uuid
from django.db import models
from django.conf import settings


class Resource(models.Model):
    class ResourceType(models.TextChoices):
        ARTICLE = 'article', 'Article'
        VIDEO = 'video', 'Video'
        AUDIO = 'audio', 'Audio'
        WORKBOOK = 'workbook', 'Workbook'
        INFOGRAPHIC = 'infographic', 'Infographic'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=15, choices=ResourceType.choices)
    tags = models.JSONField(default=list)
    language = models.CharField(max_length=5, default='en')
    content_url = models.URLField(blank=True)
    file = models.FileField(upload_to='library/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='library/thumbs/', null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_resources',
    )
    is_published = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'library_resource'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['resource_type', 'language']),
            models.Index(fields=['is_published']),
        ]

    def __str__(self):
        return self.title
