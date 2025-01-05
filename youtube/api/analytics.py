from rest_framework import viewsets, status
from rest_framework.decorators import action 
from rest_framework.response import Response
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate, Extract
from ..models import Channel, Video, VideoMetrics
from .analytics_serializers import ChannelAnalyticsSerializer, VideoAnalyticsSerializer


class ChannelAnalyticsViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.all()
    serializer_class = ChannelAnalyticsSerializer
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        try:
            channel = self.get_object()
            
            data = {
                'youtube_id': channel.youtube_id,
                'title': channel.title,
                'video_count': channel.videos.count(),
                'publishing_dates': list(
                    channel.videos.annotate(
                        date=TruncDate('published_at')
                    ).values('date').annotate(
                        count=Count('id')
                    ).order_by('date')
                ),
                'top_videos': list(
                    channel.videos.order_by('-view_count')[:5].values(
                        'youtube_id',
                        'title', 
                        'view_count', 
                        'like_count', 
                        'published_at'
                    )
                ),
                'created_at': channel.created_at,
                'updated_at': channel.updated_at
            }
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)
            
        except Channel.DoesNotExist:
            return Response(
                {'error': 'Channel not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class VideoAnalyticsViewSet(viewsets.ModelViewSet):
    queryset = Video.objects.all()
    serializer_class = VideoAnalyticsSerializer
    
    @action(detail=True, methods=['get'])
    def metrics(self, request, pk=None):
        try:
            video = self.get_object()
            
            metrics_history = video.metrics.annotate(
                date=TruncDate('captured_at')
            ).values('date').annotate(
                view_count=Avg('view_count'),
                like_count=Avg('like_count')
            ).order_by('date')
            
            data = {
                'youtube_id': video.youtube_id,
                'title': video.title,
                'channel': video.channel.id,
                'published_at': video.published_at,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'created_at': video.created_at,
                'updated_at': video.updated_at
            }
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)
            
        except Video.DoesNotExist:
            return Response(
                {'error': 'Video not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )