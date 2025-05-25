from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import re
import asyncio
from typing import Optional
import time

def get_video_id(url: str) -> str:
    """
    Extract video ID from various YouTube URL formats.
    
    Supported formats:
    - Standard: https://www.youtube.com/watch?v=VIDEO_ID
    - Short: https://youtu.be/VIDEO_ID
    - Embed: https://www.youtube.com/embed/VIDEO_ID
    - Mobile: https://m.youtube.com/watch?v=VIDEO_ID
    - With timestamp: https://www.youtube.com/watch?v=VIDEO_ID&t=123
    - With playlist: https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID
    """
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)',  # Standard and embed URLs
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',         # Short URLs
        r'(?:embed\/)([0-9A-Za-z_-]{11})',             # Embed URLs
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})'            # Watch URLs
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Could not extract video ID from URL. Please ensure it's a valid YouTube URL.")

def _fetch_transcript_sync(url: str, max_retries: int = 3, languages: list = ['en']) -> Optional[str]:
    """
    Synchronous function to fetch transcript with retries and multiple language support.
    
    Args:
        url: YouTube URL to transcribe
        max_retries: Maximum number of retry attempts
        languages: List of language codes to try, in order of preference
        
    Returns:
        Transcript text if successful, None if no transcript is available
    """
    video_id = get_video_id(url)
    
    for attempt in range(max_retries):
        try:
            # Try each language in order
            for lang in languages:
                try:
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                    # Process transcript entries to create a readable text
                    transcript_text = ""
                    for entry in transcript_list:
                        # Add the text with proper spacing
                        transcript_text += entry['text'] + " "
                    return transcript_text.strip()
                except Exception as lang_error:
                    print(f"Failed to get transcript in {lang}: {str(lang_error)}")
                    continue
            
            # If we get here, try without language specification
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            transcript_text = ""
            for entry in transcript_list:
                transcript_text += entry['text'] + " "
            return transcript_text.strip()
            
        except Exception as e:
            if "No transcript found" in str(e):
                print(f"No transcript available for video {video_id}")
                return None
            elif attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed, retrying... Error: {str(e)}")
                time.sleep(1)  # Use time.sleep instead of asyncio.sleep in sync function
                continue
            else:
                raise Exception(f"Failed to fetch transcript after {max_retries} attempts: {str(e)}")
    
    return None

async def fetch_transcript(url: str) -> str:
    """
    Asynchronously download and transcribe audio from a YouTube URL.
    
    Args:
        url: YouTube URL to transcribe
            
    Returns:
        The transcribed text
        
    Raises:
        Exception: If transcript cannot be fetched or processed
    """
    transcript = await asyncio.to_thread(_fetch_transcript_sync, url)
    if transcript is None:
        raise Exception("No transcript available for this video. Please check if captions are enabled.")
    return transcript
