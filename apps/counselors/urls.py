from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CounselorViewSet, CounselorProfileManageView

app_name = 'counselors'

router = DefaultRouter()
router.register('', CounselorViewSet, basename='counselor')

urlpatterns = [
    path('me/', CounselorProfileManageView.as_view(), name='counselor_me'),
    path('', include(router.urls)),
]
