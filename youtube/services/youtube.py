import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from googleapiclient.discovery import build
from django.conf import settings
from youtube_transcript_api import YouTubeTranscriptApi
from ..models import Channel, Video, Transcript, VideoMetrics

class YouTubeService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def _fetch_video_details_batch(self, session: aiohttp.ClientSession, video_ids: List[str]) -> List[Dict]:
        """Fetch video details for a batch of videos concurrently"""
        url = f"{self.base_url}/videos"
        params = {
            'key': self.api_key,
            'part': 'statistics,contentDetails',
            'id': ','.join(video_ids)
        }
        
        async with session.get(url, params=params) as response:
            data = await response.json()
            return data.get('items', [])

    async def _fetch_transcript(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Fetch transcript for a video asynchronously"""
        try:
            # Run transcript fetching in a thread pool since youtube_transcript_api is synchronous
            loop = asyncio.get_event_loop()
            transcript_list = await loop.run_in_executor(
                None, YouTubeTranscriptApi.get_transcript, video_id
            )
            
            if not transcript_list:
                return None

            full_text = " ".join(entry['text'] for entry in transcript_list)
            
            # Get transcript info
            transcript_info = await loop.run_in_executor(
                None, YouTubeTranscriptApi.list_transcripts, video_id
            )
            language = transcript_info.find_generated_transcript(['en']).language_code
            is_generated = transcript_info.find_generated_transcript(['en']).is_generated

            print(f"  ✓ Transcript acquired ({language})")
            return {
                'content': full_text,
                'language': language,
                'is_generated': is_generated
            }

        except Exception as e:
            if "Subtitles are disabled for this video" in str(e):
                print(f"  × Subtitles are disabled for video {video_id}")
            elif "No transcript available" in str(e):
                print(f"  × No transcript available for video {video_id}")
            else:
                print(f"  × Error fetching transcript for video {video_id}: {str(e)}")
            return None

    async def _process_video_batch(
        self,
        session: aiohttp.ClientSession,
        videos_batch: List[Dict],
        channel: Channel,
        processed_count: int
    ) -> List[Dict]:
        """Process a batch of videos concurrently"""
        # Get video IDs for this batch
        video_ids = [item['contentDetails']['videoId'] for item in videos_batch]
        
        # Fetch video details
        video_details = await self._fetch_video_details_batch(session, video_ids)
        details_map = {v['id']: v for v in video_details}
        
        # Process videos concurrently
        async def process_video(item):
            video_id = item['contentDetails']['videoId']
            details = details_map.get(video_id, {})
            
            print(f"Processing video {video_id} - '{item['snippet']['title']}'")
            print(f"  Attempting to fetch transcript...")
            
            # Fetch transcript
            transcript_data = await self._fetch_transcript(video_id)
            
            return {
                'youtube_id': video_id,
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'published_at': item['contentDetails']['videoPublishedAt'],
                'view_count': int(details.get('statistics', {}).get('viewCount', 0)),
                'like_count': int(details.get('statistics', {}).get('likeCount', 0)),
                'duration': self._parse_duration(details.get('contentDetails', {}).get('duration', 'PT0S')),
                'transcript': transcript_data
            }
        
        # Process all videos in this batch concurrently
        results = await asyncio.gather(*[
            process_video(item) for item in videos_batch
        ])
        
        # Save to database
        for video_data in results:
            transcript_data = video_data.pop('transcript', None)
            youtube_id = video_data.pop('youtube_id')
            
            # Split into dynamic and static fields
            dynamic_fields = {
                'view_count': video_data.pop('view_count'),
                'like_count': video_data.pop('like_count')
            }
            
            defaults_dict = {
                'channel': channel,
                **dynamic_fields,
            }
            
            # Run update_or_create, ignoring video_data in the defaults for now
            video, created = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: Video.objects.update_or_create(
                    youtube_id=youtube_id,
                    defaults=defaults_dict
                )
            )

            # If newly created, set those fields explicitly and save
            if created:
                for key, val in video_data.items():
                    setattr(video, key, val)
                video.save()
            
            # Create metrics record
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: VideoMetrics.objects.create(
                    video=video,
                    **dynamic_fields
                )
            )
            
            # Create transcript if available and doesn't exist
            if transcript_data:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: Transcript.objects.get_or_create(
                        video=video,
                        defaults=transcript_data
                    )
                )
        
        new_count = processed_count + len(results)
        print(f"Processed {new_count} videos so far...")
        return results

    async def _get_channel_videos_async(self, channel_id: str, channel: Channel, max_results: int = None) -> List[Dict]:
        """Fetch all videos for a channel asynchronously"""
        print(f"Starting video collection for channel {channel_id}")
        
        # Get uploads playlist ID
        playlist_id = (await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.youtube.channels().list(
                part="contentDetails",
                id=channel_id
            ).execute()
        ))['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        videos = []
        next_page_token = None
        processed_count = 0
        
        async with aiohttp.ClientSession() as session:
            while True:
                # Get playlist items
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.youtube.playlistItems().list(
                        part="snippet,contentDetails",
                        playlistId=playlist_id,
                        maxResults=50,
                        pageToken=next_page_token
                    ).execute()
                )
                
                if not response.get('items'):
                    break
                
                print(f"Fetching details for batch of {len(response['items'])} videos...")
                batch_results = await self._process_video_batch(
                    session,
                    response['items'],
                    channel,
                    processed_count
                )
                videos.extend(batch_results)
                processed_count += len(batch_results)
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token or (max_results and len(videos) >= max_results):
                    break
        
        print(f"Completed video collection. Processed {len(videos)} videos total.")
        return videos[:max_results] if max_results else videos

    def save_channel_with_videos(self, identifier: str) -> Channel:
        """Save or update a channel and all its videos including transcripts"""
        from asgiref.sync import async_to_sync
        
        # Get channel data
        channel_data = self.get_channel_data(identifier)
        
        # Update or create channel
        channel, _ = Channel.objects.update_or_create(
            youtube_id=channel_data['youtube_id'],
            defaults={
                'title': channel_data['title'],
                'description': channel_data['description'],
                'subscriber_count': channel_data['subscriber_count'],
                'video_count': channel_data['video_count']
            }
        )
        
        # Run async video collection using async_to_sync
        async_to_sync(self._get_channel_videos_async)(channel_data['youtube_id'], channel)
        
        return channel

    # Other methods remain the same
    def get_channel_data(self, identifier: str) -> Dict[str, Any]:
        """Get channel data directly using channel ID or handle"""
        request = self.youtube.channels().list(
            part="snippet,statistics",
            **({'forHandle': identifier[1:]} if identifier.startswith('@') else {'id': identifier})
        )
        response = request.execute()

        if not response['items']:
            raise ValueError(f"No channel found for: {identifier}")
        
        channel_data = response['items'][0]
        return {
            'youtube_id': channel_data['id'],
            'title': channel_data['snippet']['title'],
            'description': channel_data['snippet']['description'],
            'subscriber_count': int(channel_data['statistics'].get('subscriberCount', 0)),
            'video_count': int(channel_data['statistics'].get('videoCount', 0))
        }

    def _parse_duration(self, duration: str) -> int:
        """Parse YouTube duration format (ISO 8601) to seconds"""
        import re
        from datetime import timedelta

        duration = duration[2:]
        hours = minutes = seconds = 0
        
        if 'H' in duration:
            hours, duration = duration.split('H')
            hours = int(hours)
        
        if 'M' in duration:
            minutes, duration = duration.split('M')
            minutes = int(minutes)
        
        if 'S' in duration:
            seconds = int(duration.rstrip('S'))
        
        return timedelta(
            hours=hours,
            minutes=minutes,
            seconds=seconds
        ).total_seconds()