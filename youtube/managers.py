from django.db import models
from django.db.models import Q, F, Count
from django.utils import timezone
from datetime import timedelta


class VideoQuerySet(models.QuerySet):
    def with_related(self):
        """Load all commonly needed related data."""
        return self.select_related('channel').prefetch_related('transcripts')
    
    def in_date_range(self, months=None, days=None, start_date=None, end_date=None):
        """Filter videos by date range, either relative or absolute."""
        qs = self
        
        if months is not None:
            cutoff = timezone.now() - timedelta(days=30 * months)
            qs = qs.filter(published_at__gte=cutoff)
        elif days is not None:
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(published_at__gte=cutoff)
        else:
            if start_date:
                qs = qs.filter(published_at__gte=start_date)
            if end_date:
                qs = qs.filter(published_at__lte=end_date)
        
        return qs
    
    def top_by_views(self, limit=10):
        """Get top N videos by view count."""
        return self.order_by('-view_count')[:limit]
    
    def top_by_likes(self, limit=10):
        """Get top N videos by like count."""
        return self.order_by('-like_count')[:limit]
    
    def with_transcript_in_language(self, language):
        """Filter videos that have transcripts in specified language."""
        return self.filter(transcripts__language=language).distinct()
    
    def with_transcript_text_containing(self, search_text):
        """Filter videos whose transcripts contain the given text."""
        return self.filter(transcripts__content__icontains=search_text).distinct()
    
    def longer_than(self, seconds):
        """Filter videos longer than specified duration."""
        return self.filter(duration__gt=seconds)
    
    def shorter_than(self, seconds):
        """Filter videos shorter than specified duration."""
        return self.filter(duration__lt=seconds)
    
    def by_channels(self, channel_ids):
        """Filter videos from specific channels."""
        return self.filter(channel_id__in=channel_ids)


class ChannelQuerySet(models.QuerySet):
    def with_video_counts(self):
        """Annotate channels with their actual video counts."""
        return self.annotate(actual_video_count=Count('videos'))
    
    def with_recent_videos(self, days=30):
        """Annotate channels with count of videos in recent period."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.annotate(
            recent_videos=Count('videos', filter=Q(videos__published_at__gte=cutoff))
        )
    
    def by_min_subscribers(self, count):
        """Filter channels by minimum subscriber count."""
        return self.filter(subscriber_count__gte=count)
    
    def by_min_videos(self, count):
        """Filter channels by minimum video count."""
        return self.filter(video_count__gte=count)


class TranscriptQuerySet(models.QuerySet):
    def in_language(self, language):
        """Filter transcripts by language."""
        return self.filter(language=language)
    
    def auto_generated_only(self):
        """Filter only auto-generated transcripts."""
        return self.filter(is_generated=True)
    
    def manual_only(self):
        """Filter only manual transcripts."""
        return self.filter(is_generated=False)
    
    def search_text(self, query):
        """Search transcript content."""
        return self.filter(content__icontains=query)