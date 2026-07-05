from django.utils import timezone
from rest_framework import serializers
from .models import Appointment, AppointmentReview


class AppointmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = ['counselor', 'scheduled_at', 'duration_minutes', 'session_type', 'notes']

    def validate_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('Appointment must be scheduled in the future.')
        return value

    def create(self, validated_data):
        validated_data['student'] = self.context['request'].user
        validated_data['status'] = Appointment.Status.PENDING
        return super().create(validated_data)


class AppointmentDetailSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    counselor_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'student_name', 'counselor', 'counselor_name',
            'scheduled_at', 'duration_minutes', 'status', 'session_type',
            'notes', 'meeting_link', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'student_name', 'counselor_name', 'created_at']

    def get_counselor_name(self, obj):
        if obj.counselor:
            return obj.counselor.user.get_full_name()
        return None


class AppointmentReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentReview
        fields = ['id', 'appointment', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value
