from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsCounselor
from apps.sessions.models import Appointment
from apps.shadow_chat.models import AnonymousSession
from .models import CounselorProfile, CounselorAvailabilitySlot
from .serializers import CounselorAvailabilitySlotSerializer

ACTIVE = (Appointment.Status.PENDING, Appointment.Status.CONFIRMED, Appointment.Status.IN_PROGRESS)


def _appt(a):
    return {
        'id': str(a.id), 'student_id': a.student_id,
        'student_name': (a.student.get_full_name() or a.student.username) if a.student else 'Former student',
        'scheduled_at': a.scheduled_at, 'duration_minutes': a.duration_minutes,
        'status': a.status, 'session_type': a.session_type, 'notes': a.notes,
        'counselor_notes': a.counselor_notes,
    }


class CounselorOverviewView(APIView):
    permission_classes = [IsCounselor]

    def get(self, request):
        profile = request.user.counselor_profile
        now = timezone.now()
        mine = Appointment.objects.filter(counselor=profile).select_related('student')
        today_end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        live = AnonymousSession.objects.filter(is_active=True, expires_at__gt=now)
        return Response({
            'name': request.user.first_name or request.user.username,
            'is_available': profile.is_available,
            'pending_requests': [_appt(a) for a in mine.filter(status=Appointment.Status.PENDING).order_by('scheduled_at')[:20]],
            'upcoming': [_appt(a) for a in mine.filter(
                status__in=(Appointment.Status.CONFIRMED, Appointment.Status.IN_PROGRESS),
                scheduled_at__gte=now - timedelta(hours=2),
            ).order_by('scheduled_at')[:20]],
            'stats': {
                'sessions_completed': mine.filter(status=Appointment.Status.COMPLETED).count(),
                'today': mine.filter(status__in=ACTIVE, scheduled_at__gte=now, scheduled_at__lt=today_end).count(),
                'rating': float(profile.rating),
                'waiting_chats': live.filter(status=AnonymousSession.Status.WAITING).count(),
                'urgent_chats': live.filter(status=AnonymousSession.Status.WAITING, crisis_flagged=True).count(),
                'my_open_chats': live.filter(
                    status=AnonymousSession.Status.ACTIVE, assigned_counselor_id=profile.id).count(),
            },
        })

    def patch(self, request):
        """Toggle 'available for new bookings'."""
        profile = request.user.counselor_profile
        if 'is_available' in request.data:
            profile.is_available = bool(request.data['is_available'])
            profile.save(update_fields=['is_available'])
        return Response({'is_available': profile.is_available})


class CounselorStudentsView(APIView):
    """Students I have sessions with, so I can see history and refer them."""
    permission_classes = [IsCounselor]

    def get(self, request):
        profile = request.user.counselor_profile
        rows = (Appointment.objects.filter(counselor=profile, student__isnull=False)
                .values('student_id', 'student__first_name', 'student__last_name', 'student__username', 'student__university')
                .annotate(total=Count('id'), completed=Count('id', filter=Q(status=Appointment.Status.COMPLETED))))
        return Response([{
            'student_id': r['student_id'],
            'name': f"{r['student__first_name']} {r['student__last_name']}".strip() or r['student__username'],
            'university': r['student__university'], 'sessions': r['total'], 'completed': r['completed'],
        } for r in rows])


class AvailabilityView(APIView):
    permission_classes = [IsCounselor]

    def get(self, request):
        slots = request.user.counselor_profile.availability_slots.order_by('day_of_week', 'start_time')
        return Response(CounselorAvailabilitySlotSerializer(slots, many=True).data)

    def post(self, request):
        ser = CounselorAvailabilitySlotSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if ser.validated_data['start_time'] >= ser.validated_data['end_time']:
            raise ValidationError({'end_time': 'End time must be after start time.'})
        try:
            slot = ser.save(counselor=request.user.counselor_profile)
        except Exception:
            raise ValidationError({'start_time': 'You already have a slot starting then.'})
        return Response(CounselorAvailabilitySlotSerializer(slot).data, status=status.HTTP_201_CREATED)


class AvailabilityDetailView(APIView):
    permission_classes = [IsCounselor]

    def delete(self, request, slot_id):
        deleted, _ = CounselorAvailabilitySlot.objects.filter(
            id=slot_id, counselor=request.user.counselor_profile).delete()
        if not deleted:
            raise NotFound('Slot not found.')
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookableTimesView(APIView):
    """Free start times for one counsellor on one date (what the student's booking picker shows)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, counselor_id):
        try:
            profile = CounselorProfile.objects.get(id=counselor_id)
            day = datetime.strptime(request.query_params.get('date', ''), '%Y-%m-%d').date()
        except CounselorProfile.DoesNotExist:
            raise NotFound('Counsellor not found.')
        except ValueError:
            raise ValidationError({'date': 'Use YYYY-MM-DD.'})
        tz = timezone.get_current_timezone()
        now = timezone.now()
        busy = list(Appointment.objects.filter(
            counselor=profile, status__in=ACTIVE,
            scheduled_at__gte=timezone.make_aware(datetime.combine(day, datetime.min.time()), tz),
            scheduled_at__lt=timezone.make_aware(datetime.combine(day + timedelta(days=1), datetime.min.time()), tz),
        ).values_list('scheduled_at', 'duration_minutes'))
        times = []
        for slot in profile.availability_slots.filter(is_active=True, day_of_week=day.weekday()):
            cur = datetime.combine(day, slot.start_time)
            end = datetime.combine(day, slot.end_time)
            while cur + timedelta(minutes=60) <= end:
                start = timezone.make_aware(cur, tz)
                stop = start + timedelta(minutes=60)
                clash = any(start < b + timedelta(minutes=d) and b < stop for b, d in busy)
                if start > now and not clash:
                    times.append(start.isoformat())
                cur += timedelta(minutes=60)
        return Response({'date': str(day), 'times': sorted(times)})
