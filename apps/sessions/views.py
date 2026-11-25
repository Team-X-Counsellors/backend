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
        # Honour the per-action permission_classes set by @action (confirm/decline/complete are
        # counsellor-only). Returning a flat IsAuthenticated here used to override them.
        return [perm() for perm in self.permission_classes]

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_student():
            from rest_framework.exceptions import PermissionDenied
            # Students may only cancel; they cannot reschedule, retype, or edit the call link.
            if set(serializer.validated_data) - {'status'} or \
                    serializer.validated_data.get('status') != Appointment.Status.CANCELLED:
                raise PermissionDenied('Students can only cancel appointments.')
        serializer.save()

    def _transition(self, request, allowed_from, new_status):
        appt = self.get_object()
        if appt.status not in allowed_from:
            return None, Response({'error': f'Cannot do that while the session is {appt.status}.'},
                                  status=status.HTTP_400_BAD_REQUEST)
        appt.status = new_status
        return appt, None

    @action(detail=True, methods=['post'], permission_classes=[IsCounselor])
    def confirm(self, request, pk=None):
        appt, err = self._transition(request, (Appointment.Status.PENDING,), Appointment.Status.CONFIRMED)
        if err:
            return err
        if appt.session_type in (Appointment.SessionType.VIDEO, Appointment.SessionType.VOICE):
            appt.meeting_link = f'/call/{appt.id}'  # in-app call room, no third-party link needed
        appt.save()
        return Response(AppointmentDetailSerializer(appt).data)

    @action(detail=True, methods=['post'], permission_classes=[IsCounselor])
    def decline(self, request, pk=None):
        appt, err = self._transition(
            request, (Appointment.Status.PENDING, Appointment.Status.CONFIRMED), Appointment.Status.CANCELLED)
        if err:
            return err
        appt.cancellation_reason = str(request.data.get('reason', ''))[:300]
        appt.save()
        return Response(AppointmentDetailSerializer(appt).data)

    @action(detail=True, methods=['post'], permission_classes=[IsCounselor])
    def complete(self, request, pk=None):
        appt, err = self._transition(
            request, (Appointment.Status.CONFIRMED, Appointment.Status.IN_PROGRESS), Appointment.Status.COMPLETED)
        if err:
            return err
        appt.counselor_notes = str(request.data.get('counselor_notes', appt.counselor_notes))[:5000]
        appt.save()
        appt.counselor.total_sessions = appt.counselor.counselor_appointments.filter(
            status=Appointment.Status.COMPLETED).count()
        appt.counselor.save(update_fields=['total_sessions'])
        return Response(AppointmentDetailSerializer(appt).data)

    @action(detail=True, methods=['post', 'patch'], permission_classes=[IsCounselor], url_path='notes')
    def notes(self, request, pk=None):
        appt = self.get_object()
        appt.counselor_notes = str(request.data.get('counselor_notes', ''))[:5000]
        appt.save(update_fields=['counselor_notes', 'updated_at'])
        return Response(AppointmentDetailSerializer(appt).data)

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
