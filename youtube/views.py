from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from .models import Channel, Video
from .serializers import (
    ChannelSerializer, VideoSerializer,
    VideoMetricsSerializer, TranscriptSerializer
)
from .services.youtube import YouTubeService
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Channel, Video, VideoMetrics, Transcript
from .serializers import (
    ChannelSerializer, VideoSerializer,
    VideoMetricsSerializer, TranscriptSerializer
)

class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer

    @action(detail=False, methods=['post'], url_path='add_by_url/(?P<identifier>[^/.]+)')
    def add_by_identifier(self, request, identifier=None):
        if not identifier:
            return Response(
                {'error': 'Channel identifier is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            youtube_service = YouTubeService(settings.YOUTUBE_API_KEY)
            # Use save_channel_with_videos instead of separate calls
            channel = youtube_service.save_channel_with_videos(identifier)
            
            return Response(
                self.serializer_class(channel).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def videos(self, request, pk=None):
        channel = self.get_object()
        videos = Video.objects.filter(channel=channel)
        serializer = VideoSerializer(videos, many=True)
        return Response(serializer.data)

class TranscriptViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing transcripts.
    """
    queryset = Transcript.objects.all()
    serializer_class = TranscriptSerializer

    def get_queryset(self):
        queryset = Transcript.objects.all()
        video_id = self.request.query_params.get('video_id', None)
        if video_id is not None:
            queryset = queryset.filter(video_id=video_id)
        return queryset

class VideoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer

    @action(detail=True, methods=['get'])
    def transcript(self, request, pk=None):
        """
        Get the transcript for a specific video
        """
        video = self.get_object()
        try:
            transcript = Transcript.objects.get(video=video)
            serializer = TranscriptSerializer(transcript)
            return Response(serializer.data)
        except Transcript.DoesNotExist:
            return Response(
                {'detail': 'Transcript not found for this video'},
                status=status.HTTP_404_NOT_FOUND
            )