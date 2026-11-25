import uuid
from django.conf import settings
from django.db import models


class AssessmentResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assessment_results')
    instrument = models.CharField(max_length=20)
    answers = models.JSONField(default=list)
    score = models.PositiveSmallIntegerField()
    severity = models.CharField(max_length=30)
    severity_label = models.CharField(max_length=40)
    risk_flag = models.BooleanField(default=False)
    # The student decides whether a counsellor sees a result. Null = private.
    shared_with = models.ForeignKey(
        'counselors.CounselorProfile', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='shared_assessments',
    )
    shared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assessments_result'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'instrument', 'created_at'])]
