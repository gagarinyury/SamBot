#!/usr/bin/env python3
"""
Universal content extraction test script
Automatically detects best extraction strategy:
- YouTube → metadata + transcript (if available) or fallback to audio
- Other platforms → audio download
"""

import sys
import json
import yt_dlp
from pathlib import Path


def extract_content(url: str):
    """
    Universal content extraction with automatic fallback.

    Strategy:
    1. Extract metadata (always)
    2. Try transcript (YouTube only)
    3. Fallback to audio if no transcript
    """
    print(f"\n{'='*70}")
    print(f"🎯 EXTRACTING: {url}")
    print(f"{'='*70}\n")

    # Step 1: Extract metadata
    print("📥 Step 1: Extracting metadata...")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'socket_timeout': 30,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info:
                print("❌ Failed to extract metadata")
                return None

            # Print metadata
            print("\n✅ METADATA:")
            print(f"  Title:       {info.get('title', 'N/A')}")
            print(f"  Channel:     {info.get('uploader', 'N/A')}")
            print(f"  Duration:    {info.get('duration', 0)} seconds ({info.get('duration', 0) // 60} min)")
            print(f"  Platform:    {info.get('extractor', 'N/A')}")
            print(f"  Language:    {info.get('language', 'N/A')}")

            # Description (truncated)
            description = info.get('description', '')
            if description:
                desc_preview = description[:200] + '...' if len(description) > 200 else description
                print(f"  Description: {desc_preview}")

            # Step 2: Check for transcript (YouTube only)
            is_youtube = 'youtube' in info.get('extractor', '').lower()

            if is_youtube:
                print("\n📝 Step 2: Checking for transcript...")

                has_subs = bool(info.get('subtitles'))
                has_auto = bool(info.get('automatic_captions'))

                print(f"  Manual subtitles:    {'✅ Yes' if has_subs else '❌ No'}")
                print(f"  Auto-generated:      {'✅ Yes' if has_auto else '❌ No'}")

                if has_subs or has_auto:
                    # We have transcript!
                    source = info.get('subtitles') or info.get('automatic_captions')

                    # Try to get Russian first, then English, then any
                    lang = None
                    for preferred in ['ru', 'en']:
                        if preferred in source:
                            lang = preferred
                            break
                    if not lang:
                        lang = list(source.keys())[0]

                    print(f"\n✅ TRANSCRIPT FOUND (language: {lang})")
                    print(f"  Available languages: {', '.join(list(source.keys()))}")

                    # Get transcript URL
                    for sub in source[lang]:
                        if sub.get('url'):
                            print(f"  Format: {sub.get('ext', 'unknown')}")
                            print(f"  URL: {sub['url'][:70]}...")

                            print(f"\n{'='*70}")
                            print("✅ SUCCESS: Metadata + Transcript extracted")
                            print(f"{'='*70}")
                            return {
                                'strategy': 'transcript',
                                'metadata': {
                                    'title': info.get('title'),
                                    'channel': info.get('uploader'),
                                    'duration': info.get('duration'),
                                    'description': info.get('description'),
                                    'language': info.get('language'),
                                    'platform': info.get('extractor'),
                                },
                                'transcript': {
                                    'language': lang,
                                    'url': sub['url'],
                                    'format': sub.get('ext'),
                                }
                            }
                else:
                    print("\n⚠️  No transcript available")

            # Step 3: Fallback to audio
            print(f"\n🎵 Step 3: Checking audio availability...")

            has_audio = any(f.get('acodec') != 'none' for f in info.get('formats', []))

            if has_audio:
                print(f"  Audio available:     ✅ Yes")

                # Find best audio format
                audio_formats = [f for f in info.get('formats', [])
                               if f.get('acodec') != 'none' and f.get('vcodec') == 'none']

                if audio_formats:
                    best_audio = max(audio_formats, key=lambda f: f.get('abr', 0))
                    print(f"  Best audio quality:  {best_audio.get('format_note', 'N/A')} ({best_audio.get('abr', 0)} kbps)")

                print(f"\n💡 STRATEGY: Audio download (no transcript available)")
                print(f"{'='*70}")
                print("✅ SUCCESS: Metadata extracted, audio available")
                print(f"{'='*70}")

                return {
                    'strategy': 'audio',
                    'metadata': {
                        'title': info.get('title'),
                        'channel': info.get('uploader'),
                        'duration': info.get('duration'),
                        'description': info.get('description'),
                        'language': info.get('language'),
                        'platform': info.get('extractor'),
                    },
                    'audio': {
                        'available': True,
                        'best_quality': best_audio.get('abr', 0) if audio_formats else None,
                    }
                }
            else:
                print(f"  Audio available:     ❌ No")
                print(f"\n❌ ERROR: No transcript and no audio available")
                print(f"{'='*70}")
                return None

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print(f"{'='*70}")
        return None


def download_audio(url: str, output_dir: str = "./test_audio"):
    """Download audio from URL."""
    print(f"\n{'='*70}")
    print(f"🎵 DOWNLOADING AUDIO")
    print(f"{'='*70}\n")

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path / '%(title)s.%(ext)s'),
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
            info = ydl.extract_info(url, download=True)

            print(f"\n✅ DOWNLOAD COMPLETE")
            print(f"  Title: {info.get('title', 'N/A')}")
            print(f"  Duration: {info.get('duration', 0)} seconds")
            print(f"  Saved to: {output_path}")
            print(f"{'='*70}")

            return True

    except Exception as e:
        print(f"\n❌ DOWNLOAD FAILED: {e}")
        print(f"{'='*70}")
        return False


def main():
    """Main function."""
    print("\n" + "="*70)
    print("🧪 UNIVERSAL CONTENT EXTRACTION TEST")
    print("="*70)
    print("\nAutomatically determines best extraction strategy:")
    print("  • YouTube with transcript → metadata + transcript")
    print("  • YouTube without transcript → metadata + audio download")
    print("  • Other platforms → metadata + audio download")

    # Get URL from command line or prompt
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        print("\n" + "="*70)
        url = input("👉 Enter URL to extract: ").strip()

        if not url:
            print("❌ No URL provided")
            return

    # Extract content
    result = extract_content(url)

    if not result:
        print("\n❌ Extraction failed")
        return

    # If audio strategy, ask if user wants to download
    if result['strategy'] == 'audio':
        print("\n" + "="*70)
        download = input("💾 Download audio file? (y/n): ").strip().lower()

        if download == 'y':
            download_audio(url)

    # Print summary
    print("\n" + "="*70)
    print("📊 EXTRACTION SUMMARY")
    print("="*70)
    print(f"\nStrategy: {result['strategy'].upper()}")
    print(f"\nMetadata:")
    for key, value in result['metadata'].items():
        if value and key == 'description':
            # Truncate description
            value = value[:100] + '...' if len(value) > 100 else value
        print(f"  {key}: {value}")

    if result['strategy'] == 'transcript':
        print(f"\nTranscript:")
        print(f"  language: {result['transcript']['language']}")
        print(f"  format: {result['transcript']['format']}")

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