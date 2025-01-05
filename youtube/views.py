from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from .models import Channel, Video
from .serializers import (
    ChannelSerializer, VideoSerializer,
    VideoMetricsSerializer, TranscriptSerializer
)
from rest_framework.decorators import api_view
from .services.youtube import YouTubeService
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Channel, Video, VideoMetrics, Transcript
from .serializers import (
    ChannelSerializer, VideoSerializer,
    VideoMetricsSerializer, TranscriptSerializer
)
from asgiref.sync import async_to_sync

class PlaylistViewSet(viewsets.ViewSet):
    """
    ViewSet for processing YouTube playlists.
    """
    @action(detail=False, methods=['post'], url_path='(?P<playlist_id>[^/.]+)')
    def process_playlist(self, request, playlist_id=None):
        """Process a YouTube playlist and save its videos"""
        try:
            youtube_service = YouTubeService(settings.YOUTUBE_API_KEY)
            videos = youtube_service.save_playlist_videos(playlist_id)
            
            serializer = VideoSerializer(videos, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to process playlist: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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

# class VideoViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = Video.objects.all()
#     serializer_class = VideoSerializer

#     @action(detail=True, methods=['get'])
#     def transcript(self, request, pk=None):
#         """
#         Get the transcript for a specific video
#         """
#         video = self.get_object()
#         try:
#             transcript = Transcript.objects.get(video=video)
#             serializer = TranscriptSerializer(transcript)
#             return Response(serializer.data)
#         except Transcript.DoesNotExist:
#             return Response(
#                 {'detail': 'Transcript not found for this video'},
#                 status=status.HTTP_404_NOT_FOUND
#             )
            
class VideoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing YouTube videos.
    Provides endpoints for listing, retrieving, and fetching individual videos.
    """
    queryset = Video.objects.all()
    serializer_class = VideoSerializer

    @action(detail=False, methods=['post'], url_path='add_by_id/(?P<youtube_id>[^/.]+)')
    def add_by_youtube_id(self, request, youtube_id=None):
        """
        Fetch and save a single video by its YouTube ID.
        
        Args:
            youtube_id (str): The YouTube video ID to fetch
            
        Returns:
            Response with video data and appropriate status code
        """
        if not youtube_id:
            return Response(
                {'error': 'YouTube video ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # First check if video already exists
            existing_video = Video.objects.filter(youtube_id=youtube_id).first()
            if existing_video:
                return Response(
                    self.serializer_class(existing_video).data,
                    status=status.HTTP_200_OK
                )

            youtube_service = YouTubeService(settings.YOUTUBE_API_KEY)
            
            # Get video details from YouTube API
            video_response = youtube_service.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=youtube_id
            ).execute()

            if not video_response.get('items'):
                return Response(
                    {'error': 'Video not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            video_data = video_response['items'][0]
            
            # Get or create channel
            channel_id = video_data['snippet']['channelId']
            channel_data = youtube_service.get_channel_data(channel_id)
            channel, _ = Channel.objects.get_or_create(
                youtube_id=channel_id,
                defaults={
                    'title': channel_data['title'],
                    'description': channel_data['description'],
                    'subscriber_count': channel_data['subscriber_count'],
                    'video_count': channel_data['video_count']
                }
            )

            # Create video object
            video = Video.objects.create(
                youtube_id=youtube_id,
                channel=channel,
                title=video_data['snippet']['title'],
                description=video_data['snippet']['description'],
                published_at=video_data['snippet']['publishedAt'],
                view_count=int(video_data['statistics'].get('viewCount', 0)),
                like_count=int(video_data['statistics'].get('likeCount', 0)),
                duration=youtube_service._parse_duration(video_data['contentDetails']['duration'])
            )

            # Create initial metrics record
            VideoMetrics.objects.create(
                video=video,
                view_count=video.view_count,
                like_count=video.like_count
            )

            # Attempt to fetch transcript asynchronously
            async def fetch_transcript():
                transcript_data = await youtube_service._fetch_transcript(youtube_id)
                if transcript_data:
                    Transcript.objects.create(
                        video=video,
                        **transcript_data
                    )

            async_to_sync(fetch_transcript)()

            return Response(
                self.serializer_class(video).data,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def transcript(self, request, pk=None):
        """
        Get the transcript for a specific video
        
        Args:
            pk (int): The primary key of the video
            
        Returns:
            Response with transcript data or 404 if not found
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
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        """
        Get historical metrics for a specific video
        
        Args:
            pk (int): The primary key of the video
            
        Returns:
            Response with metrics data or 404 if not found
        """
        video = self.get_object()
        try:
            metrics = VideoMetrics.objects.filter(video=video).order_by('-captured_at')
            serializer = VideoMetricsSerializer(metrics, many=True)
            return Response(serializer.data)
        except VideoMetrics.DoesNotExist:
            return Response(
                {'detail': 'No metrics found for this video'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def refresh(self, request, pk=None):
        """
        Refresh video data from YouTube API
        
        Args:
            pk (int): The primary key of the video
            
        Returns:
            Response with updated video data or error
        """
        video = self.get_object()
        try:
            youtube_service = YouTubeService(settings.YOUTUBE_API_KEY)
            
            # Get fresh video data
            video_response = youtube_service.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=video.youtube_id
            ).execute()

            if not video_response.get('items'):
                return Response(
                    {'error': 'Video no longer available on YouTube'},
                    status=status.HTTP_404_NOT_FOUND
                )

            video_data = video_response['items'][0]
            
            # Update video metrics
            video.view_count = int(video_data['statistics'].get('viewCount', 0))
            video.like_count = int(video_data['statistics'].get('likeCount', 0))
            video.save()

            # Create new metrics record
            VideoMetrics.objects.create(
                video=video,
                view_count=video.view_count,
                like_count=video.like_count
            )

            # Try to update/fetch transcript if it doesn't exist
            if not hasattr(video, 'transcript'):
                async def fetch_transcript():
                    transcript_data = await youtube_service._fetch_transcript(video.youtube_id)
                    if transcript_data:
                        Transcript.objects.create(
                            video=video,
                            **transcript_data
                        )

                async_to_sync(fetch_transcript)()

            return Response(
                self.serializer_class(video).data,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {'error': f'Failed to refresh video data: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_queryset(self):
        """
        Get the list of videos with optional filtering
        
        Returns:
            QuerySet of videos, optionally filtered by channel_id
        """
        queryset = Video.objects.all()
        channel_id = self.request.query_params.get('channel_id', None)
        
        if channel_id is not None:
            queryset = queryset.filter(channel__youtube_id=channel_id)
            
        return queryset.order_by('-published_at')