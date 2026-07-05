from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ResourceViewSet

app_name = 'library'

router = DefaultRouter()
router.register('', ResourceViewSet, basename='resource')

urlpatterns = [
    path('', include(router.urls)),
]
