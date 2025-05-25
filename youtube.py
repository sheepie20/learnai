from youtube_transcript_api import YouTubeTranscriptApi
import re
import asyncio

def get_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid YouTube URL")

def _fetch_transcript_sync(url):
    """Synchronous function to fetch transcript"""
    try:
        video_id = get_video_id(url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return "\n".join(entry['text'] for entry in transcript)
    except Exception as e:
        raise Exception(f"Error fetching transcript: {e}")

async def fetch_transcript(url):
    """
    Asynchronously download and transcribe audio from a YouTube URL.
    
    Args:
        url: YouTube URL to transcribe
            
    Returns:
        The transcribed text
    """
    return await asyncio.to_thread(_fetch_transcript_sync, url)
