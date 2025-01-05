from rest_framework import serializers
from .models import Channel, Video, VideoMetrics, Transcript

class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

class VideoMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoMetrics
        fields = '__all__'
        read_only_fields = ('captured_at',)

class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = '__all__'
        read_only_fields = ('created_at',)