from rest_framework import viewsets, generics
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from .models import CounselorProfile
from .serializers import CounselorProfileSerializer
from api.permissions import IsStudent, IsCounselor


class CounselorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CounselorProfile.objects.filter(
        user__is_active=True
    ).select_related('user').prefetch_related('availability_slots')
    serializer_class = CounselorProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['is_available', 'accepts_anonymous']
    search_fields = ['user__first_name', 'user__last_name']

    @action(detail=True, methods=['post'], permission_classes=[IsStudent])
    def book(self, request, pk=None):
        from apps.sessions.serializers import AppointmentCreateSerializer, AppointmentDetailSerializer
        counselor = self.get_object()
        serializer = AppointmentCreateSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save(counselor=counselor)
        return Response(
            AppointmentDetailSerializer(appointment).data,
            status=201,
        )


class CounselorProfileManageView(generics.RetrieveUpdateAPIView):
    serializer_class = CounselorProfileSerializer
    permission_classes = [IsCounselor]

    def get_object(self):
        return self.request.user.counselor_profile
