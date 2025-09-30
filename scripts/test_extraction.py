#!/usr/bin/env python3
"""
Test script for yt-dlp extraction capabilities
Tests different platforms and content types
"""

import sys
import yt_dlp
from pathlib import Path

# Test URLs for different platforms
TEST_URLS = {
    'youtube': 'https://www.youtube.com/watch?v=jNQXAC9IVRw',  # First YouTube video
    'youtube_music': 'https://music.youtube.com/watch?v=dQw4w9WgXcQ',
    'soundcloud': 'https://soundcloud.com/example',  # Replace with real URL
    'spotify': 'https://open.spotify.com/track/example',  # Replace with real URL
    'tiktok': 'https://www.tiktok.com/@user/video/123',  # Replace with real URL
}


def test_transcript_extraction(url: str, platform: str):
    """Test transcript extraction for a URL."""
    print(f"\n{'='*60}")
    print(f"🎯 Testing: {platform.upper()}")
    print(f"URL: {url}")
    print(f"{'='*60}\n")

    ydl_opts = {
        'quiet': False,
        'no_warnings': False,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'ru'],
        'socket_timeout': 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("📥 Extracting metadata...")
            info = ydl.extract_info(url, download=False)

            if not info:
                print("❌ Failed to extract info")
                return

            # Print metadata
            print("\n✅ METADATA:")
            print(f"  Title: {info.get('title', 'N/A')}")
            print(f"  Channel: {info.get('uploader', 'N/A')}")
            print(f"  Duration: {info.get('duration', 0)} seconds")
            print(f"  Platform: {info.get('extractor', 'N/A')}")

            # Check for subtitles
            has_subs = bool(info.get('subtitles'))
            has_auto = bool(info.get('automatic_captions'))

            print(f"\n📝 SUBTITLES:")
            print(f"  Manual subtitles: {'✅ Yes' if has_subs else '❌ No'}")
            print(f"  Auto-generated: {'✅ Yes' if has_auto else '❌ No'}")

            if has_subs:
                print(f"  Available languages: {list(info['subtitles'].keys())}")
            if has_auto:
                print(f"  Auto-caption languages: {list(info['automatic_captions'].keys())}")

            # Try to get transcript
            if has_subs or has_auto:
                source = info.get('subtitles') or info.get('automatic_captions')
                lang = 'en' if 'en' in source else list(source.keys())[0]

                for sub in source[lang]:
                    if sub.get('ext') == 'vtt' and sub.get('url'):
                        print(f"\n✅ Found VTT transcript in '{lang}'")
                        print(f"  URL: {sub['url'][:80]}...")
                        break
            else:
                print("  ⚠️ No transcripts available")

            # Check if audio is available
            has_audio = any(f.get('acodec') != 'none' for f in info.get('formats', []))
            print(f"\n🎵 AUDIO:")
            print(f"  Audio available: {'✅ Yes' if has_audio else '❌ No'}")

            if has_audio:
                # Find best audio format
                audio_formats = [f for f in info.get('formats', [])
                               if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
                if audio_formats:
                    best_audio = max(audio_formats, key=lambda f: f.get('abr', 0))
                    print(f"  Best audio: {best_audio.get('format_note', 'N/A')} "
                          f"({best_audio.get('abr', 0)} kbps)")

            print(f"\n{'='*60}")
            print("✅ EXTRACTION SUCCESS")
            print(f"{'='*60}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print(f"{'='*60}")


def test_audio_download(url: str, platform: str):
    """Test audio download for a URL."""
    print(f"\n{'='*60}")
    print(f"🎵 Testing AUDIO DOWNLOAD: {platform.upper()}")
    print(f"URL: {url}")
    print(f"{'='*60}\n")

    output_dir = Path("./test_audio")
    output_dir.mkdir(exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_dir / f'{platform}_%(id)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("📥 Downloading audio...")
            info = ydl.extract_info(url, download=True)

            print(f"\n✅ DOWNLOAD SUCCESS")
            print(f"  Title: {info.get('title', 'N/A')}")
            print(f"  Duration: {info.get('duration', 0)} seconds")
            print(f"  Saved to: {output_dir}")
            print(f"{'='*60}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print(f"{'='*60}")


def print_supported_extractors():
    """Print list of supported extractors."""
    print("\n" + "="*60)
    print("🌐 SUPPORTED PLATFORMS (yt-dlp)")
    print("="*60 + "\n")

    extractors = yt_dlp.extractor.gen_extractors()

    # Popular platforms we care about
    popular = [
        'youtube', 'tiktok', 'instagram', 'twitter', 'facebook',
        'soundcloud', 'spotify', 'reddit', 'vimeo', 'twitch',
        'dailymotion', 'bandcamp', 'mixcloud', 'audiomack'
    ]

    found = []
    for extractor in extractors:
        name = extractor.IE_NAME.lower() if hasattr(extractor, 'IE_NAME') else ''
        for p in popular:
            if p in name and p not in found:
                found.append(p)
                break

    for platform in sorted(found):
        print(f"  ✅ {platform.capitalize()}")

    print(f"\n  Total extractors available: {len(list(extractors))}")
    print("="*60)


def main():
    """Main test function."""
    print("\n" + "="*60)
    print("🧪 YT-DLP EXTRACTION TEST SUITE")
    print("="*60)

    # Show supported platforms
    print_supported_extractors()

    # Ask user what to test
    print("\n📋 What would you like to test?\n")
    print("  1. YouTube video (transcript)")
    print("  2. YouTube video (audio download)")
    print("  3. Custom URL (provide your own)")
    print("  4. Show all capabilities")
    print("  0. Exit")

    choice = input("\n👉 Enter choice (0-4): ").strip()

    if choice == '0':
        print("\n👋 Goodbye!")
        return

    elif choice == '1':
        # Test YouTube transcript
        url = TEST_URLS['youtube']
        print(f"\n🎬 Using test URL: {url}")
        confirm = input("Press Enter to continue or paste your own URL: ").strip()
        if confirm:
            url = confirm
        test_transcript_extraction(url, 'youtube')

    elif choice == '2':
        # Test audio download
        url = TEST_URLS['youtube']
        print(f"\n🎬 Using test URL: {url}")
        confirm = input("Press Enter to continue or paste your own URL: ").strip()
        if confirm:
            url = confirm

        print("\n⚠️  WARNING: This will download audio file!")
        confirm_download = input("Continue? (y/n): ").strip().lower()
        if confirm_download == 'y':
            test_audio_download(url, 'youtube')
        else:
            print("❌ Cancelled")

    elif choice == '3':
        # Custom URL
        url = input("\n👉 Enter URL to test: ").strip()
        if not url:
            print("❌ No URL provided")
            return

        print("\n📋 Test type:")
        print("  1. Transcript extraction")
        print("  2. Audio download")
        test_type = input("👉 Choose (1 or 2): ").strip()

        if test_type == '1':
            test_transcript_extraction(url, 'custom')
        elif test_type == '2':
            print("\n⚠️  WARNING: This will download audio file!")
            confirm_download = input("Continue? (y/n): ").strip().lower()
            if confirm_download == 'y':
                test_audio_download(url, 'custom')
            else:
                print("❌ Cancelled")
        else:
            print("❌ Invalid choice")

    elif choice == '4':
        # Show all capabilities
        print_supported_extractors()

        print("\n📝 Testing YouTube transcript extraction...")
        test_transcript_extraction(TEST_URLS['youtube'], 'youtube')

    else:
        print("❌ Invalid choice")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)