from django.db import models
from .managers import VideoQuerySet, ChannelQuerySet, TranscriptQuerySet

class Channel(models.Model):
    youtube_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    subscriber_count = models.IntegerField(null=True)
    video_count = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ChannelQuerySet.as_manager()

    def __str__(self):
        return f"{self.title} ({self.youtube_id})"

class Video(models.Model):
    youtube_id = models.CharField(max_length=255, unique=True)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    published_at = models.DateTimeField()
    view_count = models.IntegerField(default=0)
    like_count = models.IntegerField(default=0)
    duration = models.IntegerField(help_text="Duration in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = VideoQuerySet.as_manager()

    def __str__(self):
        return f"{self.title} ({self.youtube_id})"

    class Meta:
        indexes = [
            models.Index(fields=['published_at']),
            models.Index(fields=['view_count']),
            models.Index(fields=['like_count']),
            models.Index(fields=['duration']),
            models.Index(fields=['channel', 'published_at']),
        ]

class VideoMetrics(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='metrics')
    view_count = models.IntegerField()
    like_count = models.IntegerField()
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Video metrics"
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['captured_at']),
        ]

    def __str__(self):
        return f"Metrics for {self.video.title} at {self.captured_at}"

class Transcript(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='transcripts')
    content = models.TextField()
    language = models.CharField(max_length=10)
    is_generated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TranscriptQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=['language']),
            models.Index(fields=['is_generated']),
        ]

    def __str__(self):
        return f"Transcript for {self.video.title} ({self.language})"