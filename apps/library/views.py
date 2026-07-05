from django.db import models as db_models
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from api.permissions import IsCounselorOrAdmin
from .models import Resource
from .serializers import ResourceSerializer


class ResourceViewSet(viewsets.ModelViewSet):
    serializer_class = ResourceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['resource_type', 'language', 'is_published']
    search_fields = ['title', 'description']

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.role in ('admin', 'superadmin', 'counselor'):
            return Resource.objects.all()
        return Resource.objects.filter(is_published=True)

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsCounselorOrAdmin()]
        return [IsAuthenticated()]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Resource.objects.filter(pk=instance.pk).update(
            view_count=db_models.F('view_count') + 1
        )
        return super().retrieve(request, *args, **kwargs)
