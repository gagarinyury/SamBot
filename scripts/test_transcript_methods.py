#!/usr/bin/env python3
"""
Test different methods for extracting YouTube transcripts.

Compares:
1. yt-dlp direct URL download (current method)
2. youtube-transcript-api library
"""

import sys
import requests
import json


def test_ytdlp_method(url: str):
    """Test yt-dlp method (current implementation)."""
    print("\n" + "="*70)
    print("🧪 METHOD 1: yt-dlp with manual URL download")
    print("="*70 + "\n")

    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("📥 Extracting video info...")
            info = ydl.extract_info(url, download=False)

            has_subs = bool(info.get('subtitles'))
            has_auto = bool(info.get('automatic_captions'))

            print(f"  Manual subtitles:    {'✅ Yes' if has_subs else '❌ No'}")
            print(f"  Auto-generated:      {'✅ Yes' if has_auto else '❌ No'}")

            if not (has_subs or has_auto):
                print("\n❌ No subtitles available")
                return False

            source = info.get('subtitles') or info.get('automatic_captions')

            # Try English
            lang = 'en' if 'en' in source else list(source.keys())[0]
            print(f"\n📝 Selected language: {lang}")
            print(f"  Available: {', '.join(list(source.keys())[:5])}...")

            # Get transcript URL
            for sub in source[lang]:
                if 'json3' in sub.get('ext', ''):
                    transcript_url = sub['url']
                    print(f"\n🔗 Transcript URL: {transcript_url[:80]}...")

                    # Try to download
                    print("\n📥 Downloading transcript from URL...")
                    try:
                        response = requests.get(transcript_url, timeout=30)
                        response.raise_for_status()

                        print(f"  Status: {response.status_code}")
                        print(f"  Content-Type: {response.headers.get('Content-Type')}")
                        print(f"  Size: {len(response.content)} bytes")

                        # Try to parse JSON
                        data = response.json()

                        # Extract text
                        texts = []
                        for event in data.get('events', []):
                            if 'segs' in event:
                                for seg in event['segs']:
                                    if 'utf8' in seg:
                                        texts.append(seg['utf8'])

                        full_text = ' '.join(texts)

                        print(f"\n✅ SUCCESS!")
                        print(f"  Events: {len(data.get('events', []))}")
                        print(f"  Text length: {len(full_text)} chars")
                        print(f"  Preview: {full_text[:200]}...")

                        return True

                    except requests.exceptions.RequestException as e:
                        print(f"\n❌ DOWNLOAD ERROR: {e}")
                        return False
                    except json.JSONDecodeError as e:
                        print(f"\n❌ JSON PARSE ERROR: {e}")
                        print(f"  Response preview: {response.text[:200]}")
                        return False

            print("\n❌ No json3 subtitle found")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_transcript_api_method(url: str):
    """Test youtube-transcript-api library."""
    print("\n" + "="*70)
    print("🧪 METHOD 2: youtube-transcript-api library")
    print("="*70 + "\n")

    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        # Extract video ID
        if 'watch?v=' in url:
            video_id = url.split('watch?v=')[1].split('&')[0]
        else:
            print("❌ Cannot extract video ID")
            return False

        print(f"📹 Video ID: {video_id}")
        print("\n📥 Fetching transcript...")

        # Get transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

        # Extract text
        texts = [entry['text'] for entry in transcript_list]
        full_text = ' '.join(texts)

        print(f"\n✅ SUCCESS!")
        print(f"  Entries: {len(transcript_list)}")
        print(f"  Text length: {len(full_text)} chars")
        print(f"  Preview: {full_text[:200]}...")

        # Show timing info
        if transcript_list:
            first = transcript_list[0]
            print(f"\n📍 First entry:")
            print(f"  Start: {first.get('start')}s")
            print(f"  Duration: {first.get('duration')}s")
            print(f"  Text: {first['text']}")

        return True

    except ImportError:
        print("❌ youtube-transcript-api not installed")
        print("   Install: pip install youtube-transcript-api")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def main():
    """Main test function."""
    print("\n" + "="*70)
    print("🧪 YOUTUBE TRANSCRIPT EXTRACTION - METHOD COMPARISON")
    print("="*70)

    # Get URL from command line or use default
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        print(f"\n💡 Using default URL: {url}")
        print("   (You can provide your own: python test_transcript_methods.py URL)")

    print(f"\n🎯 Testing URL: {url}")

    # Test both methods
    method1_result = test_ytdlp_method(url)
    method2_result = test_transcript_api_method(url)

    # Summary
    print("\n" + "="*70)
    print("📊 RESULTS SUMMARY")
    print("="*70 + "\n")

    print(f"  Method 1 (yt-dlp + manual download): {'✅ WORKS' if method1_result else '❌ FAILED'}")
    print(f"  Method 2 (youtube-transcript-api):  {'✅ WORKS' if method2_result else '❌ FAILED'}")

    print("\n💡 RECOMMENDATION:")
    if method2_result:
        print("  ✅ Use youtube-transcript-api - simpler and more reliable")
    elif method1_result:
        print("  ⚠️  Use yt-dlp method - works but more complex")
    else:
        print("  ❌ Both methods failed - video may not have transcripts")

    print("\n" + "="*70)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)