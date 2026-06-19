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
# Invidious is a free, open-source YouTube frontend.
# Instance list is refreshed from the official API periodically.
# ─────────────────────────────────────────────
class InvidiousScraper(BaseScraper):
    name = "invidious"
    # Updated 2026-06 — checked against https://api.invidious.io/instances.json
    instances = [
        "https://inv.nadeko.net",
        "https://invidious.perennialte.ch",
        "https://iv.datura.network",
        "https://invidious.privacydev.net",
        "https://yt.drgnz.club",
        "https://invidious.io.lol",
        "https://invidious.fdn.fr",
    ]

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        for pat in patterns:
            m = re.search(pat, url)
            if m:
                return m.group(1)
        return None

    async def _get_live_instances(self) -> list[str]:
        """Fetch the live instance list from the Invidious API aggregator."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get("https://api.invidious.io/instances.json?sort_by=health")
                if resp.status_code == 200:
                    data = resp.json()
                    # Each entry is [domain, {api: bool, type: "https", ...}]
                    return [
                        f"https://{entry[0]}"
                        for entry in data
                        if isinstance(entry, list)
                        and entry[1].get("api") is True
                        and entry[1].get("type") == "https"
                    ][:8]  # cap at 8 to avoid long timeouts
        except Exception:
            pass
        return self.instances  # fallback to hardcoded list

    async def fetch(self, url: str) -> Optional[list[dict]]:
        video_id = self._extract_video_id(url)
        if not video_id:
            return None

        # Try live instances first, fall back to hardcoded
        try:
            instances_to_try = await self._get_live_instances()
        except Exception:
            instances_to_try = self.instances

        for instance in instances_to_try:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.get(
                        f"{instance}/api/v1/videos/{video_id}",
                        params={"fields": "title,videoThumbnails,formatStreams,adaptiveFormats"},
                    )
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    title = data.get("title", "YouTube Video")
                    thumbs = data.get("videoThumbnails", [])
                    thumbnail = thumbs[0]["url"] if thumbs else None

                    # formatStreams = progressive muxed (audio+video) — preferred
                    streams = data.get("formatStreams", [])
                    if streams:
                        best = max(
                            streams,
                            key=lambda s: int(s.get("size", "0x0").split("x")[-1]) if "x" in s.get("size", "") else 0
                        )
                        return [{"type": "video", "url": best["url"], "title": title, "thumbnail": thumbnail}]

                    # adaptiveFormats fallback (video-only track)
                    adaptive = data.get("adaptiveFormats", [])
                    video_formats = [f for f in adaptive if f.get("type", "").startswith("video/")]
                    if video_formats:
                        best = max(video_formats, key=lambda f: int(f.get("resolution", "0p").rstrip("p") or 0))
                        return [{"type": "video", "url": best["url"], "title": title, "thumbnail": thumbnail}]

            except Exception as e:
                print(f"[{self.name}] {instance} failed: {e}")
                continue

        self.set_cooldown(1)
        return None


# ─────────────────────────────────────────────
# 6. Piped API Fallback (YouTube-specific, open-source)
# Piped is a privacy-friendly YouTube frontend. Many public instances exist.
# https://github.com/TeamPiped/Piped — returns direct stream URLs.
# ─────────────────────────────────────────────
class PipedScraper(BaseScraper):
    name = "piped"
    instances = [
        "https://pipedapi.kavin.rocks",
        "https://pipedapi.coldforge.xyz",
        "https://api.piped.projectsegfau.lt",
        "https://pipedapi.nosebs.ru",
        "https://piped-api.lunar.icu",
        "https://api.piped.privacydev.net",
        "https://pipedapi.r4fo.com",
    ]

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        for pat in patterns:
            m = re.search(pat, url)
            if m:
                return m.group(1)
        return None

    async def fetch(self, url: str) -> Optional[list[dict]]:
        video_id = self._extract_video_id(url)
        if not video_id:
            return None

        for instance in self.instances:
            try:
                async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                    resp = await client.get(f"{instance}/streams/{video_id}")
                    if resp.status_code != 200:
                        print(f"[{self.name}] {instance} returned {resp.status_code}")
                        continue

                    data = resp.json()
                    title = data.get("title", "YouTube Video")
                    thumbnail = data.get("thumbnailUrl")

                    # videoStreams contains muxed progressive streams
                    video_streams = data.get("videoStreams", [])
                    # Filter to mimeType video/mp4 with audio (mimeType check)
                    # Piped marks progressive streams — prefer them
                    muxed = [
                        s for s in video_streams
                        if s.get("videoOnly") is False and "video/mp4" in s.get("mimeType", "")
                    ]
                    if not muxed:
                        # take any non-video-only stream
                        muxed = [s for s in video_streams if s.get("videoOnly") is False]
                    if not muxed:
                        muxed = video_streams  # last resort: any stream

                    if muxed:
                        best = max(muxed, key=lambda s: s.get("quality", 0) if isinstance(s.get("quality"), int)
                                   else int(str(s.get("quality", "0")).rstrip("p") or 0))
                        stream_url = best.get("url")
                        if stream_url:
                            return [{"type": "video", "url": stream_url, "title": title, "thumbnail": thumbnail}]

            except Exception as e:
                print(f"[{self.name}] {instance} failed: {e}")
                continue

        self.set_cooldown(2)
        return None


# ─────────────────────────────────────────────
# 7. ytapi.ch Scraper (YouTube-specific)
# ytapi.ch is a small public REST API that wraps innertube.
# Returns direct mp4 stream URLs without requiring yt-dlp.
# ─────────────────────────────────────────────
class YTAPIChScraper(BaseScraper):
    name = "ytapich"

    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        for pat in patterns:
            m = re.search(pat, url)
            if m:
                return m.group(1)
        return None

    async def fetch(self, url: str) -> Optional[list[dict]]:
        video_id = self._extract_video_id(url)
        if not video_id:
            return None

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    f"https://ytapi.ch/api/video",
                    params={"id": video_id}
                )
                if resp.status_code != 200:
                    return None

                data = resp.json()
                streams = data.get("streams", []) or data.get("formats", [])
                title = data.get("title", "YouTube Video")
                thumbnail = data.get("thumbnail")

                # Pick best muxed (has both audio and video)
                muxed = [s for s in streams if s.get("hasAudio") and s.get("hasVideo")]
                if not muxed:
                    muxed = streams

                if muxed:
                    best = max(muxed, key=lambda s: int(str(s.get("height", 0) or s.get("quality", 0) or 0)))
                    stream_url = best.get("url")
                    if stream_url:
                        return [{"type": "video", "url": stream_url, "title": title, "thumbnail": thumbnail}]

        except Exception as e:
            print(f"[{self.name}] Failed: {e}")

        return None


# ─────────────────────────────────────────────
# 8. Reddit JSON API Scraper (Reddit-specific)
# Reddit exposes a public JSON API at <post_url>.json
# This bypasses yt-dlp entirely for Reddit videos with audio.
# DASH streams need ffmpeg to merge, so we return the best video track
# and let the frontend/proxy handle it.
# ─────────────────────────────────────────────
class RedditJSONScraper(BaseScraper):
    name = "reddit_json"

    async def fetch(self, url: str) -> Optional[list[dict]]:
        if "reddit.com" not in url and "redd.it" not in url:
            return None

        # Normalise URL: ensure it ends without trailing slash before .json
        clean = url.split("?")[0].rstrip("/")
        json_url = clean + ".json"

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; DownSnap/1.0)",
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(json_url, headers=headers)
                if resp.status_code != 200:
                    return None

                data = resp.json()
                # Reddit JSON returns a list of two listings (post + comments)
                if not isinstance(data, list) or not data:
                    return None

                post_listing = data[0]
                children = post_listing.get("data", {}).get("children", [])
                if not children:
                    return None

                post_data = children[0].get("data", {})
                title = post_data.get("title", "Reddit Video")
                thumbnail = post_data.get("thumbnail") if post_data.get("thumbnail", "").startswith("http") else None

                # v.redd.it DASH video
                media = post_data.get("media") or {}
                reddit_video = media.get("reddit_video") or {}
                fallback_url = reddit_video.get("fallback_url")  # video-only (no audio)

                # Try the HLS playlist URL (has both audio and video in some cases)
                hls_url = reddit_video.get("hls_url")

                # Best direct mp4 from preview
                preview = post_data.get("preview") or {}
                reddit_video_preview = preview.get("reddit_video_preview") or {}
                preview_fallback = reddit_video_preview.get("fallback_url")

                # Derive audio URL by replacing /DASH_VIDEO with /DASH_audio
                best_video_url = fallback_url or preview_fallback
                audio_url = None
                if best_video_url:
                    # Reddit audio track lives at the same base URL with DASH_audio.mp4
                    base = best_video_url.split("/DASH_")[0] if "/DASH_" in best_video_url else None
                    if base:
                        audio_url = base + "/DASH_audio.mp4"

                if best_video_url:
                    items = [{
                        "type": "video",
                        "url": best_video_url,
                        "title": title,
                        "thumbnail": thumbnail,
                    }]
                    # Attach audio URL as extra metadata so the frontend can signal it
                    if audio_url:
                        items[0]["audio_url"] = audio_url
                    return items

                # Gallery posts
                media_metadata = post_data.get("media_metadata") or {}
                gallery_items = []
                for key, val in media_metadata.items():
                    if val.get("e") == "Image":
                        best_img = val.get("s") or {}
                        img_url = best_img.get("u") or best_img.get("gif")
                        if img_url:
                            gallery_items.append({"type": "image", "url": img_url.replace("&amp;", "&"), "title": title, "thumbnail": thumbnail})
                if gallery_items:
                    return gallery_items

        except Exception as e:
            print(f"[{self.name}] Failed: {e}")

        return None


# ─────────────────────────────────────────────
# Engine Controller
# ─────────────────────────────────────────────

# Singleton instances (preserves cooldown state across requests)
_cobalt = CobaltScraper()
_invidious = InvidiousScraper()
_piped = PipedScraper()
_ytapich = YTAPIChScraper()
_instagram_direct = InstagramDirectScraper()
_saveig = SaveIGScraper()
_snapinsta = SnapInstaScraper()
_reddit_json = RedditJSONScraper()

INSTAGRAM_SCRAPERS = [
    _instagram_direct,
    _cobalt,
    _saveig,
    _snapinsta,
]

# YouTube waterfall: 4 independent sources, none rely on yt-dlp
# Order: Cobalt (best quality) → Piped (reliable) → Invidious (fallback) → ytapi.ch (last resort)
YOUTUBE_SCRAPERS = [
    _cobalt,
    _piped,
    _invidious,
    _ytapich,
]

# Reddit: native JSON API first (fast, no rate limit), then Cobalt
REDDIT_SCRAPERS = [
    _reddit_json,
    _cobalt,
]

# Generic: Cobalt handles most platforms
GENERIC_SCRAPERS = [
    _cobalt,
]


async def hydra_fetch(url: str, platform: str = "generic") -> Optional[list[dict]]:
    """Try available scrapers in order. Return the first successful result.

    Routes to platform-specific scrapers when available, falls back to generic.
    Each scraper is tried sequentially — failures are swallowed and logged.
    """
    url_lower = url.lower()

    if platform == "instagram":
        scrapers = INSTAGRAM_SCRAPERS
    elif platform == "youtube" or "youtube.com" in url_lower or "youtu.be" in url_lower:
        scrapers = YOUTUBE_SCRAPERS
    elif "reddit.com" in url_lower or "redd.it" in url_lower:
        scrapers = REDDIT_SCRAPERS
    else:
        scrapers = GENERIC_SCRAPERS

    for scraper in scrapers:
        if not scraper.is_available():
            print(f"[Hydra] Skipping {scraper.name} (on cooldown)")
            continue

        print(f"[Hydra] Trying {scraper.name} for {url} (platform={platform})...")
        try:
            result = await scraper.fetch(url)
        except Exception as e:
            print(f"[Hydra] {scraper.name} raised unexpectedly: {e}")
            result = None

        if result:
            print(f"[Hydra] Success with {scraper.name}")
            return result

    print(f"[Hydra] All fallback scrapers exhausted for platform={platform}.")
    return None
