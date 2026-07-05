from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ForumCategoryViewSet, ForumThreadViewSet

app_name = 'circle'

router = DefaultRouter()
router.register('categories', ForumCategoryViewSet, basename='category')
router.register('threads', ForumThreadViewSet, basename='thread')

urlpatterns = [
    path('', include(router.urls)),
]
