# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'channels', views.ChannelViewSet)
router.register(r'videos', views.VideoViewSet)
router.register(r'transcripts', views.TranscriptViewSet)  # Add transcript endpoint

urlpatterns = [
    path('channels/add_by_url/<str:identifier>/', views.ChannelViewSet.as_view({'post': 'add_by_identifier'})),
    path('', include(router.urls)),
]

# serializers.py
from rest_framework import serializers
from .models import Channel, Video, Transcript

class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ['id', 'video', 'content', 'language', 'is_generated', 'created_at']
        read_only_fields = ['created_at']