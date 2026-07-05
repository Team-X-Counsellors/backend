from rest_framework import serializers
from .models import CounselorProfile, CounselorAvailabilitySlot


class CounselorAvailabilitySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounselorAvailabilitySlot
        fields = ['id', 'day_of_week', 'start_time', 'end_time', 'is_active']


class CounselorProfileSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    availability_slots = CounselorAvailabilitySlotSerializer(many=True, read_only=True)

    class Meta:
        model = CounselorProfile
        fields = [
            'id', 'user_name', 'user_email', 'bio', 'specialties',
            'languages', 'years_experience', 'is_available',
            'rating', 'total_sessions', 'accepts_anonymous', 'avatar',
            'availability_slots',
        ]
        read_only_fields = ['id', 'rating', 'total_sessions']
