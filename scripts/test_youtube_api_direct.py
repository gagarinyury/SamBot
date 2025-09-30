#!/usr/bin/env python3
"""
Test direct YouTube API requests - exactly as Docker container does.
Captures real request details and tests locally.
"""

import sys
import asyncio
import aiohttp


async def test_aiohttp_request(url: str):
    """Test aiohttp request (same as in container)."""
    print("="*70)
    print("🧪 TEST: aiohttp request (как в Docker контейнере)")
    print("="*70)
    print(f"\nURL: {url}\n")

    try:
        async with aiohttp.ClientSession() as session:
            print("📥 Sending request...")
            print(f"  Method: GET")
            print(f"  Timeout: 30s")
            print(f"  Headers: (default aiohttp)")

            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                print(f"\n✅ Response:")
                print(f"  Status: {resp.status}")
                print(f"  Content-Type: {resp.headers.get('Content-Type')}")
                print(f"  Content-Length: {resp.headers.get('Content-Length')}")

                content = await resp.text()

                print(f"\n📦 Body:")
                print(f"  Length: {len(content)} bytes")

                if len(content) > 0:
                    print(f"  Preview: {content[:200]}")
                    return True
                else:
                    print(f"  ❌ EMPTY RESPONSE!")
                    return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


async def test_aiohttp_with_headers(url: str):
    """Test aiohttp with browser headers."""
    print("\n" + "="*70)
    print("🧪 TEST: aiohttp + User-Agent header")
    print("="*70)
    print(f"\nURL: {url}\n")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
    }

    try:
        async with aiohttp.ClientSession() as session:
            print("📥 Sending request with headers...")
            for key, value in headers.items():
                print(f"  {key}: {value[:50]}{'...' if len(value) > 50 else ''}")

            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                print(f"\n✅ Response:")
                print(f"  Status: {resp.status}")
                print(f"  Content-Type: {resp.headers.get('Content-Type')}")

                content = await resp.text()

                print(f"\n📦 Body:")
                print(f"  Length: {len(content)} bytes")

                if len(content) > 0:
                    print(f"  Preview: {content[:200]}")
                    return True
                else:
                    print(f"  ❌ EMPTY RESPONSE!")
                    return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_requests_library(url: str):
    """Test with requests library."""
    print("\n" + "="*70)
    print("🧪 TEST: requests library")
    print("="*70)
    print(f"\nURL: {url}\n")

    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    try:
        print("📥 Sending request...")
        resp = requests.get(url, headers=headers, timeout=30)

        print(f"\n✅ Response:")
        print(f"  Status: {resp.status_code}")
        print(f"  Content-Type: {resp.headers.get('Content-Type')}")

        print(f"\n📦 Body:")
        print(f"  Length: {len(resp.content)} bytes")

        if len(resp.content) > 0:
            print(f"  Preview: {resp.text[:200]}")
            return True
        else:
            print(f"  ❌ EMPTY RESPONSE!")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


async def main():
    """Main test."""
    print("\n" + "="*70)
    print("🎯 YOUTUBE API DIRECT TEST")
    print("="*70)
    print("\nПроверяем ТОЧНО тот же запрос что делает Docker контейнер\n")

    # YouTube transcript API URL for Rick Astley
    video_id = "dQw4w9WgXcQ"

    # Try different URL formats
    urls = [
        f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en&fmt=json3",
        f"https://www.youtube.com/api/timedtext?v={video_id}&lang=en",
    ]

    for i, url in enumerate(urls, 1):
        print(f"\n{'='*70}")
        print(f"URL VARIANT {i}")
        print(f"{'='*70}\n")

        # Test 1: Plain aiohttp (как в контейнере БЕЗ headers)
        result1 = await test_aiohttp_request(url)

        # Test 2: aiohttp with headers
        result2 = await test_aiohttp_with_headers(url)

        # Test 3: requests library
        result3 = test_requests_library(url)

        print(f"\n{'='*70}")
        print(f"RESULTS FOR URL {i}:")
        print(f"{'='*70}")
        print(f"  Plain aiohttp:     {'✅ WORKS' if result1 else '❌ FAILS'}")
        print(f"  aiohttp + headers: {'✅ WORKS' if result2 else '❌ FAILS'}")
        print(f"  requests:          {'✅ WORKS' if result3 else '❌ FAILS'}")

        if result1 or result2 or result3:
            print(f"\n💡 Хотя бы один метод работает!")
            break

    print(f"\n{'='*70}")
    print("🎯 ВЫВОД:")
    print(f"{'='*70}")
    print("\nЕсли локально всё работает, но в Docker нет -")
    print("проблема в сетевых настройках контейнера или rate limiting\n")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted")
        sys.exit(0)