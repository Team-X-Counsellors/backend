from django.urls import path
from .views import (
    JalibotChatView,
    JalibotHistoryView,
    JalibotConversationDetailView,
    JalibotMemoryListView,
    JalibotMemoryDetailView,
)

app_name = 'jalibot'

urlpatterns = [
    path('chat/', JalibotChatView.as_view(), name='chat'),
    path('history/', JalibotHistoryView.as_view(), name='history'),
    path('history/<uuid:conversation_id>/', JalibotConversationDetailView.as_view(), name='history-detail'),
    path('memories/', JalibotMemoryListView.as_view(), name='memories'),
    path('memories/<uuid:memory_id>/', JalibotMemoryDetailView.as_view(), name='memory-detail'),
]
