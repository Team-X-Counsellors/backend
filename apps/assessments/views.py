from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsCounselor, IsStudent
from apps.counselors.models import CounselorProfile
from apps.shadow_chat.services import CRISIS_RESOURCES
from .instruments import INSTRUMENTS, public_view, score
from .models import AssessmentResult


def _result_dict(r):
    inst = INSTRUMENTS.get(r.instrument, {})
    return {
        'id': str(r.id), 'instrument': r.instrument, 'title': inst.get('title', r.instrument),
        'score': r.score, 'max_score': inst.get('max_score'), 'severity': r.severity,
        'severity_label': r.severity_label, 'higher_is_better': inst.get('higher_is_better', False),
        'shared': r.shared_with_id is not None, 'created_at': r.created_at,
    }


class InstrumentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([public_view(i) for i in INSTRUMENTS.values()])


class SubmitView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, key):
        inst = INSTRUMENTS.get(key)
        if not inst:
            raise NotFound('Unknown assessment.')
        answers = request.data.get('answers')
        max_option = max(o['value'] for o in inst['options'])
        if (not isinstance(answers, list) or len(answers) != len(inst['questions'])
                or not all(isinstance(a, int) and not isinstance(a, bool) and 0 <= a <= max_option for a in answers)):
            raise ValidationError({'answers': 'Please answer every question.'})
        result = score(key, answers)
        saved = AssessmentResult.objects.create(
            user=request.user, instrument=key, answers=answers, score=result['score'],
            severity=result['severity'], severity_label=result['severity_label'], risk_flag=result['risk_flag'],
        )
        return Response({
            **_result_dict(saved), 'advice': result['advice'], 'elevated': result['elevated'],
            'crisis_resources': CRISIS_RESOURCES if result['risk_flag'] else None,
        }, status=status.HTTP_201_CREATED)


class ResultListView(APIView):
    """Progress over time: newest first; ?instrument=phq9 to filter."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = AssessmentResult.objects.filter(user=request.user)
        if request.query_params.get('instrument'):
            qs = qs.filter(instrument=request.query_params['instrument'])
        return Response([_result_dict(r) for r in qs[:100]])


class ShareView(APIView):
    """Student chooses to share one result with one counsellor. Revoke with counselor=null."""
    permission_classes = [IsStudent]

    def post(self, request, result_id):
        try:
            result = AssessmentResult.objects.get(id=result_id, user=request.user)
        except AssessmentResult.DoesNotExist:
            raise NotFound('Result not found.')
        cid = request.data.get('counselor')
        if cid is None:
            result.shared_with, result.shared_at = None, None
        else:
            try:
                result.shared_with = CounselorProfile.objects.get(id=cid)
            except (CounselorProfile.DoesNotExist, ValueError):
                raise ValidationError({'counselor': 'Counsellor not found.'})
            result.shared_at = timezone.now()
        result.save(update_fields=['shared_with', 'shared_at'])
        return Response(_result_dict(result))


class SharedWithMeView(APIView):
    permission_classes = [IsCounselor]

    def get(self, request):
        qs = AssessmentResult.objects.filter(shared_with=request.user.counselor_profile).select_related('user')
        return Response([
            {**_result_dict(r), 'student_name': r.user.get_full_name() or r.user.username,
             'risk_flag': r.risk_flag, 'shared_at': r.shared_at}
            for r in qs[:100]
        ])
