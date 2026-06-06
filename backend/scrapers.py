import json
import re
import time
from typing import Optional

import httpx

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


# ─────────────────────────────────────────────
# Base Scraper Class
# ─────────────────────────────────────────────
class BaseScraper:
    name: str = "base"
    cooldown_until: float = 0

    async def fetch(self, url: str) -> Optional[list[dict]]:
        """Must return a list of MediaItems (as dicts) or None if it fails."""
        raise NotImplementedError

    def set_cooldown(self, hours: int = 24):
        self.cooldown_until = time.time() + (hours * 3600)
        print(f"[{self.name}] Put on cooldown for {hours} hours.")

    def is_available(self) -> bool:
        return time.time() > self.cooldown_until

# ─────────────────────────────────────────────
# 1. Instagram Direct API (via curl-cffi impersonation)
# Fetches Instagram's GraphQL API directly using Chrome TLS fingerprint,
# bypassing bot detection without needing any login or cookies.
# curl-cffi is already in requirements.txt.
# ─────────────────────────────────────────────
class InstagramDirectScraper(BaseScraper):
    name = "instagram_direct"

    async def fetch(self, url: str) -> Optional[list[dict]]:
        if not HAS_CURL_CFFI:
            return None

        shortcode_match = re.search(r'instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)', url)
        if not shortcode_match:
            return None
        shortcode = shortcode_match.group(1)

        try:
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_fetch, shortcode, url)
            return result
        except Exception as e:
            print(f"[{self.name}] Failed: {e}")
            return None

    def _sync_fetch(self, shortcode: str, source_url: str) -> Optional[list[dict]]:
        session = curl_requests.Session()
        session.impersonate = 'chrome124'

        # Step 1: Fetch the post page to get CSRF token + session cookies
        page = session.get(source_url)
        if page.status_code != 200:
            return None

        csrf = dict(session.cookies).get('csrftoken', '')

        # Step 2: Try GraphQL API with doc_id
        variables = {
            'shortcode': shortcode,
            'child_comment_count': 3,
            'fetch_comment_count': 40,
            'parent_comment_count': 24,
            'has_threaded_comments': True,
        }

        graphql_resp = session.get(
            'https://www.instagram.com/graphql/query/',
            params={
                'doc_id': '8845758582119845',
                'variables': json.dumps(variables, separators=(',', ':')),
            },
            headers={
                'X-CSRFToken': csrf,
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': source_url,
                'Accept': 'application/json',
            },
        )

        if graphql_resp.status_code == 200:
            data = graphql_resp.json()
            media = data.get('data', {}).get('xdt_shortcode_media')
            if media:
                items = self._parse_media(media)
                if items:
                    return items

        # Step 3: Fallback to embed page scraping
        try:
            embed = session.get(f'{source_url}embed/')
            if embed.status_code == 200:
                html = embed.text
                items = self._parse_embed(html)
                if items:
                    return items
        except Exception:
            pass

        return None

    def _parse_media(self, media: dict) -> list[dict]:
        items = []

        # Check for carousel (sidecar)
        sidecar = media.get('edge_sidecar_to_children', {}).get('edges')
        if sidecar:
            for edge in sidecar:
                node = edge.get('node', {})
                items.append(self._media_node_to_item(node))
            if items:
                return items

        # Single post
        item = self._media_node_to_item(media)
        if item.get('url'):
            items.append(item)

        return items

    def _media_node_to_item(self, node: dict) -> dict:
        video_url = node.get('video_url')
        display_url = node.get('display_url') or node.get('display_src', '')
        is_video = node.get('is_video', False) or bool(video_url)

        if is_video and video_url:
            return {
                'type': 'video',
                'url': video_url,
                'title': 'Instagram Media',
                'thumbnail': display_url,
            }

        if display_url:
            return {
                'type': 'image',
                'url': display_url,
                'title': 'Instagram Media',
                'thumbnail': display_url,
            }

        return {'type': 'image', 'url': '', 'title': 'Instagram Media', 'thumbnail': None}

    def _parse_embed(self, html: str) -> Optional[list[dict]]:
        # Look for video_url in the embed HTML
        video_urls = re.findall(r'"video_url"\s*:\s*"([^"]+)"', html)
        display_urls = re.findall(r'"display_url"\s*:\s*"([^"]+)"', html)

        if not video_urls and not display_urls:
            return None

        # Unescape JSON unicode sequences
        def unescape(s):
            return s.encode().decode('unicode-escape') if '\\u' in s else s

        items = []
        # If we have both, pair them (for carousels) or all videos then all images
        if video_urls and display_urls:
            # Try to detect if it's a carousel
            if 'edge_sidecar_to_children' in html:
                nodes = re.findall(
                    r'\{"__typename"[^}]+"video_url"\s*:\s*"([^"]*)"[^}]+"display_url"\s*:\s*"([^"]*)"[^}]+"is_video"\s*:\s*(true|false)',
                    html
                )
                if not nodes:
                    nodes = re.findall(
                        r'\{"__typename"[^}]+"display_url"\s*:\s*"([^"]*)"[^}]+"is_video"\s*:\s*(true|false)',
                        html
                    )
                for node in nodes:
                    if len(node) == 3:
                        v_url, d_url, is_v = node
                        if is_v == 'true' and v_url:
                            items.append({'type': 'video', 'url': unescape(v_url), 'title': 'Instagram Media', 'thumbnail': unescape(d_url)})
                        elif d_url:
                            items.append({'type': 'image', 'url': unescape(d_url), 'title': 'Instagram Media', 'thumbnail': unescape(d_url)})
                    elif len(node) == 2:
                        d_url, is_v = node
                        items.append({'type': 'image', 'url': unescape(d_url), 'title': 'Instagram Media', 'thumbnail': unescape(d_url)})
                if items:
                    return items

            # Fallback: pair by index
            for i, v in enumerate(video_urls):
                thumb = display_urls[i] if i < len(display_urls) else None
                items.append({'type': 'video', 'url': unescape(v), 'title': 'Instagram Media', 'thumbnail': unescape(thumb) if thumb else None})
            for i in range(len(video_urls), len(display_urls)):
                items.append({'type': 'image', 'url': unescape(display_urls[i]), 'title': 'Instagram Media', 'thumbnail': unescape(display_urls[i])})
        elif video_urls:
            for v in video_urls:
                items.append({'type': 'video', 'url': unescape(v), 'title': 'Instagram Media', 'thumbnail': None})
        elif display_urls:
            for d in display_urls:
                items.append({'type': 'image', 'url': unescape(d), 'title': 'Instagram Media', 'thumbnail': unescape(d)})

        return items if items else None


# ─────────────────────────────────────────────
# 2. Cobalt API (Public Instances)
# Cobalt is an open-source downloader. People host public instances.
# It doesn't have terms of service blocking us from hitting public nodes.
# ─────────────────────────────────────────────
class CobaltScraper(BaseScraper):
    name = "cobalt"
    # Public Cobalt v2 instances — /api endpoint with Accept: application/json
    # Cobalt supports YouTube, Instagram, TikTok, Twitter/X, Reddit, Pinterest,
    # Tumblr, Vimeo, SoundCloud, and many more platforms.
    instances = [
        "https://api.cobalt.tools",
        "https://cobalt.cibere.dev",
        "https://cobalt.qewertyy.dev",
        "https://cobalt.owo.network",
        "https://co.eepy.today",
        "https://api.cobalt.ac",
        "https://cobalt.jayw.uk",
    ]

    async def fetch(self, url: str) -> Optional[list[dict]]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        # Cobalt v2 payload format
        payload = {
            "url": url,
            "videoQuality": "1080",
            "downloadMode": "auto",
            "filenameStyle": "basic",
        }

        for api_base in self.instances:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{api_base}/api",
                        headers=headers,
                        json=payload
                    )

                    if resp.status_code == 429:
                        print(f"[{self.name}] Rate limited on {api_base}")
                        continue

                    if resp.status_code not in (200, 201):
                        print(f"[{self.name}] {api_base} returned {resp.status_code}")
                        continue

                    data = resp.json()
                    status = data.get("status")

                    if status == "error":
                        print(f"[{self.name}] Error from {api_base}: {data.get('error', {})}")
                        continue

                    if status in ("redirect", "tunnel", "stream"):
                        return [{
                            "type": "video",
                            "url": data.get("url"),
                            "title": "Media",
                            "thumbnail": None
                        }]

                    if status == "picker":
                        items = []
                        for item in data.get("picker", []):
                            items.append({
                                "type": "video" if item.get("type") == "video" else "image",
                                "url": item.get("url"),
                                "thumbnail": item.get("thumb")
                            })
                        if items:
                            return items

            except Exception as e:
                print(f"[{self.name}] Instance {api_base} failed: {e}")
                continue

        self.set_cooldown(1)
        return None


# ─────────────────────────────────────────────
# 2. SaveIG Fallback (JSON API, no HTML scraping)
# ─────────────────────────────────────────────
class SaveIGScraper(BaseScraper):
    name = "saveig"

    async def fetch(self, url: str) -> Optional[list[dict]]:
        import re
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://saveig.app",
            "Referer": "https://saveig.app/",
            "X-Requested-With": "XMLHttpRequest",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.post(
                    "https://v3.saveig.app/api/ajaxSearch",
                    headers=headers,
                    data={"q": url, "t": "media", "lang": "en"}
                )
                if resp.status_code == 429:
                    self.set_cooldown(24)
                    return None
                if resp.status_code != 200:
                    return None

                data = resp.json()
                if not data.get("status") == "ok":
                    return None

                html = data.get("data", "")
                # Extract HD/SD download links from the response HTML
                matches = re.findall(r'href=["\x27](https://[^"\x27]+\.(?:mp4|jpg|jpeg|png)[^"\x27]*)["\x27]', html, re.IGNORECASE)
                if not matches:
                    matches = re.findall(r'href=["\x27](https://[^"\x27]+)["\x27][^>]*>[^<]*(?:Download|HD|SD)', html, re.IGNORECASE)
                items = []
                seen = set()
                for link in matches:
                    clean = link.replace("&amp;", "&")
                    if clean not in seen:
                        seen.add(clean)
                        items.append({
                            "type": "video",
                            "url": clean,
                            "title": "Instagram Media",
                            "thumbnail": None
                        })
                if items:
                    return items

        except Exception as e:
            print(f"[{self.name}] Failed: {e}")

        return None


# ─────────────────────────────────────────────
# 3. SnapInsta Fallback (last resort)
# ─────────────────────────────────────────────
class SnapInstaScraper(BaseScraper):
    name = "snapinsta"

    async def fetch(self, url: str) -> Optional[list[dict]]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Origin": "https://snapinsta.app",
            "Referer": "https://snapinsta.app/"
        }
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.post(
                    "https://snapinsta.app/action.php",
                    headers=headers,
                    data={"url": url, "action": "post"}
                )
                if resp.status_code == 429:
                    self.set_cooldown(24)
                    return None
                if resp.status_code != 200:
                    return None

                text = resp.text
                if "No data found" in text or not text.strip():
                    return None

                import re
                # Match direct media URLs in download links (broader pattern)
                matches = re.findall(
                    r'href=["\x27](https://[^"\x27]+\.(?:mp4|jpg|jpeg|png)(?:[?"\x27][^"\x27]*)?)["\x27]',
                    text, re.IGNORECASE
                )
                items = []
                seen = set()
                for m in matches:
                    clean = m.replace("&amp;", "&")
                    if clean not in seen:
                        seen.add(clean)
                        ext = clean.split("?")[0].rsplit(".", 1)[-1].lower()
                        items.append({
                            "type": "image" if ext in ("jpg", "jpeg", "png") else "video",
                            "url": clean,
                            "title": "Instagram Media",
                            "thumbnail": None
                        })
                if items:
                    return items

        except Exception as e:
            print(f"[{self.name}] Failed: {e}")

        return None


# ─────────────────────────────────────────────
# 5. Invidious API Fallback (YouTube-specific)
# Invidious is a free, open-source YouTube frontend with public API instances.
# No API key needed. Great fallback when yt-dlp can't reach YouTube.
# ─────────────────────────────────────────────
class InvidiousScraper(BaseScraper):
    name = "invidious"
    instances = [
        "https://vid.puffyan.us",
        "https://invidious.nerdvpn.de",
        "https://inv.nadeko.net",
        "https://invidious.jing.rocks",
        "https://invidious.privacyredirect.com",
    ]

    async def fetch(self, url: str) -> Optional[list[dict]]:
        # Extract YouTube video ID
        video_id = None
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break

        if not video_id:
            return None

        for instance in self.instances:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{instance}/api/v1/videos/{video_id}",
                        params={"fields": "title,videoThumbnails,formatStreams,adaptiveFormats"},
                    )
                    if resp.status_code != 200:
                        print(f"[{self.name}] {instance} returned {resp.status_code}")
                        continue

                    data = resp.json()
                    title = data.get("title", "YouTube Video")
                    thumbs = data.get("videoThumbnails", [])
                    thumbnail = thumbs[0]["url"] if thumbs else None

                    # Prefer formatStreams (progressive, muxed audio+video)
                    streams = data.get("formatStreams", [])
                    if streams:
                        # Pick highest quality progressive stream
                        best = max(streams, key=lambda s: int(s.get("size", "0x0").split("x")[1]) if "x" in s.get("size", "") else 0)
                        return [{
                            "type": "video",
                            "url": best["url"],
                            "title": title,
                            "thumbnail": thumbnail,
                        }]

                    # Fallback to adaptiveFormats (video-only, but still usable)
                    adaptive = data.get("adaptiveFormats", [])
                    video_formats = [f for f in adaptive if f.get("type", "").startswith("video/")]
                    if video_formats:
                        best = max(video_formats, key=lambda f: int(f.get("resolution", "0p").rstrip("p") or 0))
                        return [{
                            "type": "video",
                            "url": best["url"],
                            "title": title,
                            "thumbnail": thumbnail,
                        }]

            except Exception as e:
                print(f"[{self.name}] Instance {instance} failed: {e}")
                continue

        self.set_cooldown(1)
        return None


# ─────────────────────────────────────────────
# Engine Controller
# Scrapers are organized by platform. The "generic" list is tried for any URL.
# ─────────────────────────────────────────────
INSTAGRAM_SCRAPERS = [
    InstagramDirectScraper(),
    CobaltScraper(),
    SaveIGScraper(),
    SnapInstaScraper(),
]

YOUTUBE_SCRAPERS = [
    CobaltScraper(),
    InvidiousScraper(),
]

# Generic scrapers that work across many platforms
GENERIC_SCRAPERS = [
    CobaltScraper(),
]


async def hydra_fetch(url: str, platform: str = "generic") -> Optional[list[dict]]:
    """Try available scrapers in order. Return first successful result.
    
    Routes to platform-specific scrapers when available, falls back to generic.
    """
    if platform == "instagram":
        scrapers = INSTAGRAM_SCRAPERS
    elif platform == "youtube":
        scrapers = YOUTUBE_SCRAPERS
    else:
        scrapers = GENERIC_SCRAPERS

    for scraper in scrapers:
        if not scraper.is_available():
            continue
            
        print(f"[Hydra] Trying {scraper.name} for {url} (platform={platform})...")
        result = await scraper.fetch(url)
        
        if result:
            print(f"[Hydra] Success with {scraper.name}")
            return result
            
    print(f"[Hydra] All fallback scrapers exhausted for platform={platform}.")
    return None
