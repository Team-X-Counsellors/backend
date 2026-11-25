from django.conf import settings
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsCounselor
from apps.users.models import CustomUser
from .models import CampusResource, Referral


def _resource(r):
    wa = r.whatsapp or ''
    return {
        'id': str(r.id), 'university': r.university, 'category': r.category,
        'category_label': r.get_category_display(), 'name': r.name, 'description': r.description,
        'phone': r.phone, 'email': r.email, 'location': r.location,
        'whatsapp_url': f'https://wa.me/{wa}' if wa else '',
    }


def _referral(r):
    return {
        'id': str(r.id), 'status': r.status, 'note': r.note, 'created_at': r.created_at,
        'resource': _resource(r.resource), 'referred_by_counselor': r.referred_by_id is not None,
    }


class ResourceDirectoryView(APIView):
    """Campus offices for the student's university (plus ones open to everyone)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        uni = request.query_params.get('university') or request.user.university
        qs = CampusResource.objects.filter(is_active=True)
        qs = qs.filter(Q(university__iexact=uni) | Q(university='')) if uni else qs.filter(university='')
        if request.query_params.get('category'):
            qs = qs.filter(category=request.query_params['category'])
        return Response([_resource(r) for r in qs])


class ReferralListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Referral.objects.filter(student=request.user).select_related('resource')
        return Response([_referral(r) for r in qs])

    def post(self, request):
        """Student asks to be referred, or a counsellor refers a student (`student` id required)."""
        try:
            resource = CampusResource.objects.get(id=request.data.get('resource'), is_active=True)
        except (CampusResource.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'resource': 'Choose a campus office.'})
        note = str(request.data.get('note', ''))[:500]
        if request.user.role == 'counselor':
            try:
                student = CustomUser.objects.get(id=request.data.get('student'), role='student')
            except (CustomUser.DoesNotExist, ValueError, TypeError):
                raise ValidationError({'student': 'Choose a student.'})
            # A counsellor may only refer students they have an appointment with.
            if not student.student_appointments.filter(counselor=request.user.counselor_profile).exists():
                raise ValidationError({'student': 'You can only refer students you have a session with.'})
            ref = Referral.objects.create(student=student, resource=resource, referred_by=request.user, note=note)
        elif request.user.role == 'student':
            ref = Referral.objects.create(student=request.user, resource=resource, note=note)
        else:
            raise ValidationError('Only students and counsellors can create referrals.')
        return Response(_referral(ref), status=status.HTTP_201_CREATED)


class WhatsAppInfoView(APIView):
    """The platform's click-to-chat WhatsApp number (for the 'chat on WhatsApp' buttons)."""
    permission_classes = []

    def get(self, request):
        n = settings.WHATSAPP_NUMBER
        return Response({
            'enabled': bool(n),
            'url': f'https://wa.me/{n}?text=Hi%20JaliMind%2C%20I%27d%20like%20to%20talk' if n else '',
        })
