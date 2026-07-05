from django.urls import path
from .views import JalibotChatView, JalibotHistoryView

app_name = 'jalibot'

urlpatterns = [
    path('chat/', JalibotChatView.as_view(), name='chat'),
    path('history/', JalibotHistoryView.as_view(), name='history'),
]
