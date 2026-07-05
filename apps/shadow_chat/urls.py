from django.urls import path
from .views import ShadowStartView, ShadowSessionView, ShadowMessageView

app_name = 'shadow'

urlpatterns = [
    path('start/', ShadowStartView.as_view(), name='start'),
    path('session/<uuid:session_id>/', ShadowSessionView.as_view(), name='session'),
    path('session/<uuid:session_id>/message/', ShadowMessageView.as_view(), name='message'),
]
