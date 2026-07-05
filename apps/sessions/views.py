from django.db import models as db_models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.permissions import IsStudent, IsCounselor, IsAdmin
from .models import Appointment, AppointmentReview
from .serializers import AppointmentCreateSerializer, AppointmentDetailSerializer, AppointmentReviewSerializer


class AppointmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_student():
            return Appointment.objects.filter(student=user).select_related('counselor__user')
        if user.is_counselor():
            return Appointment.objects.filter(counselor=user.counselor_profile).select_related('student')
        if user.is_admin():
            return Appointment.objects.all().select_related('student', 'counselor__user')
        return Appointment.objects.none()

    def get_serializer_class(self):
        if self.action == 'create':
            return AppointmentCreateSerializer
        return AppointmentDetailSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsStudent()]
        return [IsAuthenticated()]

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if user.is_student():
            # Students can only cancel their own appointments
            new_status = serializer.validated_data.get('status')
            if new_status and new_status != Appointment.Status.CANCELLED:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied('Students can only cancel appointments.')
        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def review(self, request, pk=None):
        appointment = self.get_object()
        if appointment.status != Appointment.Status.COMPLETED:
            return Response(
                {'error': 'Can only review completed appointments.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = AppointmentReviewSerializer(data={**request.data, 'appointment': appointment.id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Update counselor rating
        from apps.counselors.models import CounselorProfile
        from django.db.models import Avg
        avg = AppointmentReview.objects.filter(
            appointment__counselor=appointment.counselor
        ).aggregate(avg=Avg('rating'))['avg']
        if avg:
            appointment.counselor.rating = round(avg, 2)
            appointment.counselor.save(update_fields=['rating'])
        return Response(serializer.data, status=status.HTTP_201_CREATED)
