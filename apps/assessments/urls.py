from django.urls import path
from .views import InstrumentListView, SubmitView, ResultListView, ShareView, SharedWithMeView

app_name = 'assessments'

urlpatterns = [
    path('', InstrumentListView.as_view(), name='list'),
    path('results/', ResultListView.as_view(), name='results'),
    path('results/<uuid:result_id>/share/', ShareView.as_view(), name='share'),
    path('shared/', SharedWithMeView.as_view(), name='shared'),
    path('<str:key>/submit/', SubmitView.as_view(), name='submit'),
]
