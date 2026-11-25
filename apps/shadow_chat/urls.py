from django.urls import path
from .views import (
    ShadowStartView, ShadowSessionView, ShadowMessageView,
    CounselorQueueView, CounselorClaimView, CounselorSessionView,
)

app_name = 'shadow'

urlpatterns = [
    path('start/', ShadowStartView.as_view(), name='start'),
    path('session/<uuid:session_id>/', ShadowSessionView.as_view(), name='session'),
    path('session/<uuid:session_id>/message/', ShadowMessageView.as_view(), name='message'),
    # counsellor side
    path('queue/', CounselorQueueView.as_view(), name='queue'),
    path('queue/<uuid:session_id>/claim/', CounselorClaimView.as_view(), name='claim'),
    path('counselor/<uuid:session_id>/', CounselorSessionView.as_view(), name='counselor_session'),
]
