from django.urls import path
from .views import ResourceDirectoryView, ReferralListCreateView, WhatsAppInfoView

app_name = 'referrals'

urlpatterns = [
    path('resources/', ResourceDirectoryView.as_view(), name='resources'),
    path('whatsapp/', WhatsAppInfoView.as_view(), name='whatsapp'),
    path('', ReferralListCreateView.as_view(), name='referrals'),
]
