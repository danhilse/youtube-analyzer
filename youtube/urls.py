from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import views
from .api.analytics import ChannelAnalyticsViewSet, VideoAnalyticsViewSet  # Import from the correct location

router = DefaultRouter()
router.register(r'channels', views.ChannelViewSet)
router.register(r'videos', views.VideoViewSet)
router.register(r'transcripts', views.TranscriptViewSet)
router.register(r'playlists', views.PlaylistViewSet, basename='playlist')
router.register(r'channel-analytics', ChannelAnalyticsViewSet, basename='channel-analytics')
router.register(r'video-analytics', VideoAnalyticsViewSet, basename='video-analytics')

urlpatterns = [
    path('channels/add_by_url/<str:identifier>/', 
         views.ChannelViewSet.as_view({'post': 'add_by_identifier'})),
    path('playlists/<str:playlist_id>/', 
         views.PlaylistViewSet.as_view({'post': 'process_playlist'})),
    path('', include(router.urls)),
]

# # serializers.py
# from rest_framework import serializers
# from .models import Channel, Video, Transcript

# class TranscriptSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Transcript
#         fields = ['id', 'video', 'content', 'language', 'is_generated', 'created_at']
#         read_only_fields = ['created_at']