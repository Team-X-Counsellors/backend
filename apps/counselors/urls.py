from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CounselorViewSet, CounselorProfileManageView
from .dashboard import (
    CounselorOverviewView, CounselorStudentsView, AvailabilityView,
    AvailabilityDetailView, BookableTimesView,
)

app_name = 'counselors'

router = DefaultRouter()
router.register('', CounselorViewSet, basename='counselor')

urlpatterns = [
    path('me/', CounselorProfileManageView.as_view(), name='counselor_me'),
    path('dashboard/', CounselorOverviewView.as_view(), name='dashboard'),
    path('students/', CounselorStudentsView.as_view(), name='students'),
    path('me/availability/', AvailabilityView.as_view(), name='availability'),
    path('me/availability/<int:slot_id>/', AvailabilityDetailView.as_view(), name='availability_detail'),
    path('<uuid:counselor_id>/times/', BookableTimesView.as_view(), name='times'),
    path('', include(router.urls)),
]
