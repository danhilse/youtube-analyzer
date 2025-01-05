from rest_framework import serializers
from ..models import Channel, Video, VideoMetrics, Transcript
from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate

class ChannelGrowthSerializer(serializers.ModelSerializer):
    total_videos = serializers.IntegerField()
    total_views = serializers.IntegerField()
    avg_views_per_video = serializers.FloatField()
    publishing_frequency = serializers.ListField()
    top_performing_videos = serializers.ListField()

    class Meta:
        model = Channel
        fields = [
            'id', 
            'title',
            'total_videos',
            'total_views', 
            'avg_views_per_video',
            'publishing_frequency',
            'top_performing_videos'
        ]

class VideoEngagementSerializer(serializers.ModelSerializer):
    metrics_over_time = serializers.ListField()
    latest_metrics = serializers.DictField()

    class Meta:
        model = Video
        fields = [
            'id',
            'title',
            'metrics_over_time',
            'latest_metrics'
        ]
        
# youtube/api/analytics_serializers.py
class ChannelAnalyticsSerializer(serializers.ModelSerializer):
    total_view_count = serializers.SerializerMethodField()
    avg_view_count = serializers.SerializerMethodField()
    publishing_dates = serializers.SerializerMethodField()
    top_videos = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = [
            'youtube_id',
            'title',
            'video_count',
            'total_view_count',
            'avg_view_count',
            'publishing_dates',
            'top_videos',
            'created_at',
            'updated_at'
        ]

    def get_total_view_count(self, obj):
        return obj.videos.aggregate(total_views=Sum('view_count'))['total_views'] or 0

    def get_avg_view_count(self, obj):
        total_views = self.get_total_view_count(obj)
        video_count = obj.videos.count()
        return total_views / video_count if video_count else 0

    def get_publishing_dates(self, obj):
        return list(
            obj.videos.annotate(
                date=TruncDate('published_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date').values('date', 'count')
        )

    def get_top_videos(self, obj):
        return list(
            obj.videos.order_by('-view_count')[:5].values(
                'youtube_id',
                'title', 
                'view_count', 
                'like_count', 
                'published_at'
            )
        )


class VideoAnalyticsSerializer(serializers.Serializer):
    youtube_id = serializers.CharField()
    title = serializers.CharField()
    channel = serializers.PrimaryKeyRelatedField(queryset=Channel.objects.all())
    published_at = serializers.DateTimeField()
    view_count = serializers.IntegerField()
    like_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()