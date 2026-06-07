"""
DownSnap Backend - FastAPI + yt-dlp media downloader proxy
"""

import asyncio
import datetime
import logging
import os
import re
import mimetypes
import urllib.parse
from typing import Optional

import httpx
import yt_dlp
try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
    _IMPERSONATE_TARGET = ImpersonateTarget.from_str("chrome")
except Exception:
    _IMPERSONATE_TARGET = None
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, field_validator

logger = logging.getLogger("downsnap")

# ─────────────────────────────────────────────
# App bootstrap
# ─────────────────────────────────────────────
app = FastAPI(
    title="DownSnap API",
    description="Proxy media downloader for Facebook, Instagram, and public video URLs.",
    version="1.0.0",
)

# ─────────────────────────────────────────────
# Keep-alive self-pinger (prevents Render free-tier spin-down)
# ─────────────────────────────────────────────
_PING_INTERVAL_SECONDS = 10 * 60  # 10 minutes — well under Render's 15-min idle timeout
_ping_task: Optional[asyncio.Task] = None
_last_ping: Optional[datetime.datetime] = None


async def _self_ping_loop() -> None:
    """
    Background coroutine that pings /ping on this server every 10 minutes.
    This prevents Render's free-tier from spinning down the instance due to inactivity.
    The loop is intentionally resilient: network errors are swallowed and retried
    on the next interval so a transient failure never kills the loop.
    """
    global _last_ping
    # Give the server a few seconds to fully start before the first ping
    await asyncio.sleep(30)

    # Determine our own URL: Render injects RENDER_EXTERNAL_URL automatically
    base_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        # Fallback for local dev — just skip pinging
        logger.info("[keep-alive] RENDER_EXTERNAL_URL not set; self-ping disabled.")
        return

    ping_url = f"{base_url}/ping"
    logger.info("[keep-alive] Self-ping loop started → %s (every %ds)", ping_url, _PING_INTERVAL_SECONDS)

    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                resp = await client.get(ping_url)
                _last_ping = datetime.datetime.utcnow()
                logger.info("[keep-alive] Ping OK (%d) at %s", resp.status_code, _last_ping.isoformat())
            except Exception as exc:  # noqa: BLE001
                logger.warning("[keep-alive] Ping failed (will retry): %s", exc)

            await asyncio.sleep(_PING_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_keep_alive() -> None:
    global _ping_task
    _ping_task = asyncio.create_task(_self_ping_loop())


@app.on_event("shutdown")
async def stop_keep_alive() -> None:
    if _ping_task and not _ping_task.done():
        _ping_task.cancel()

# In production set ALLOWED_ORIGINS to your frontend domain, e.g.:
#   ALLOWED_ORIGINS=https://downsnap.onrender.com
# Leave unset (or "*") for local development.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_cors_origins: list[str] = (
    ["*"] if _raw_origins.strip() == "*"
    else [o.strip() for o in _raw_origins.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_raw_origins.strip() != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Static frontend (served by Cloudflare Pages — no mount needed here)
# ─────────────────────────────────────────────
SEO_PAGES = {
    "youtube-downloader": {
        "title": "YouTube Video Downloader Free Online - DownSnap",
        "description": "Download YouTube videos free online in HD. No app, no login, no watermark. Supports YouTube Shorts, 1080p & 4K. The fastest YouTube video downloader.",
        "og_title": "YouTube Video Downloader - DownSnap",
        "og_desc": "Download YouTube videos free in HD. YouTube Shorts, 1080p & 4K supported. No watermark, no app.",
        "tw_title": "YouTube Video Downloader Free - DownSnap",
        "tw_desc": "Download any YouTube video free in HD. Shorts, 1080p & 4K. No login needed.",
        "h1": "YouTube Video Downloader &mdash; HD, No Watermark, Free",
        "hero_sub": "Paste any YouTube link below and download in seconds. Works with YouTube Shorts, playlists and regular videos. 1080p HD &amp; 4K supported.",
        "placeholder": "Paste YouTube video or Shorts URL here...",
        "breadcrumb": "YouTube Downloader",
    },
    "instagram-downloader": {
        "title": "Instagram Video & Photo Downloader Free - DownSnap",
        "description": "Download Instagram Reels, posts, carousels & photos free online. No watermark, no login. Save any Instagram content in original quality instantly.",
        "og_title": "Instagram Downloader - DownSnap",
        "og_desc": "Download Instagram Reels, posts & photos free. No watermark, no login. Save any IG content instantly.",
        "tw_title": "Instagram Downloader Free - DownSnap",
        "tw_desc": "Download Instagram Reels & posts free. No watermark. Save any IG content instantly.",
        "h1": "Instagram Video &amp; Photo Downloader &mdash; No Watermark",
        "hero_sub": "Paste any Instagram link below. Works with Reels, posts, carousels and IGTV. Download in original quality with zero watermark.",
        "placeholder": "Paste Instagram Reel or Post URL here...",
        "breadcrumb": "Instagram Downloader",
    },
    "online-video-downloader": {
        "title": "Online Video Downloader Free - DownSnap | Download Any Video from Any Website",
        "description": "Free online video downloader for YouTube, Instagram, Facebook, Pinterest, TikTok & 1800+ sites. Download any video from any website in HD. No app, no login, no watermark.",
        "og_title": "Online Video Downloader - DownSnap | Any Website",
        "og_desc": "Download any video from 1800+ sites free. YouTube, Instagram, Facebook, TikTok & more. HD quality, no watermark, no login.",
        "tw_title": "Online Video Downloader - DownSnap",
        "tw_desc": "Free online video downloader for 1800+ sites. HD quality, no watermark, no login. Download any video from any website.",
        "h1": "Free Online Video Downloader &mdash; Download Any Video from 1800+ Sites",
        "hero_sub": "The best <strong>any video downloader</strong> — works with YouTube, Instagram, Facebook, Pinterest, TikTok, Twitter/X, Kuaishou and <strong>1800+ sites</strong>. HD quality, no watermark, no login.",
        "placeholder": "Paste any video URL from any website...",
        "breadcrumb": "Any Video Downloader",
    },
    "facebook-video-downloader": {
        "title": "Facebook Video Downloader Free Online - DownSnap",
        "description": "Download Facebook videos and Reels free online in HD. No watermark, no login. Save Facebook Watch videos, Reels & Stories instantly to your device.",
        "og_title": "Facebook Video Downloader - DownSnap",
        "og_desc": "Download Facebook videos & Reels free in HD. No watermark, no login. Save any FB video instantly.",
        "tw_title": "Facebook Video Downloader - DownSnap",
        "tw_desc": "Download Facebook videos & Reels free. HD quality, no watermark.",
        "h1": "Facebook Video Downloader &mdash; Download Reels &amp; Videos in HD",
        "hero_sub": "Paste any Facebook link below. Works with Reels, Watch videos, Stories and regular posts. Download in HD with no watermark.",
        "placeholder": "Paste Facebook video or Reel URL here...",
        "breadcrumb": "Facebook Downloader",
    },
    "pinterest-video-downloader": {
        "title": "Pinterest Video Downloader Free Online - DownSnap",
        "description": "Download Pinterest videos and video pins free online in HD. No watermark, no login. Save any Pinterest video directly to your device instantly.",
        "og_title": "Pinterest Video Downloader - DownSnap",
        "og_desc": "Download Pinterest videos free in HD. No watermark, no login. Save any Pinterest pin video.",
        "tw_title": "Pinterest Video Downloader - DownSnap",
        "tw_desc": "Download Pinterest videos free. HD quality, no watermark.",
        "h1": "Pinterest Video Downloader &mdash; Save Pinterest Videos in HD",
        "hero_sub": "Paste any Pinterest link below. Works with video pins and idea pins. Download in original HD quality with no watermark.",
        "placeholder": "Paste Pinterest video URL here...",
        "breadcrumb": "Pinterest Downloader",
    },
}

SEO_PAGE_ORDER = [
    "online-video-downloader",
    "youtube-downloader",
    "instagram-downloader",
    "pinterest-video-downloader",
    "facebook-video-downloader",
]


# ─────────────────────────────────────────────
# Redirect middleware — www→non-www, http→https, HSTS
# ─────────────────────────────────────────────
@app.middleware("http")
async def seo_redirect_middleware(request: Request, call_next):
    url = request.url
    host = url.hostname or ""

    # Redirect www.downsnap.in → downsnap.in
    if host.startswith("www."):
        canonical = url.replace(hostname=host.removeprefix("www."))
        return RedirectResponse(str(canonical), status_code=301)

    # Redirect HTTP → HTTPS (for Render or behind proxy)
    if url.scheme == "http" and not host.startswith("localhost") and not host.startswith("127.0.0.1"):
        canonical = url.replace(scheme="https")
        return RedirectResponse(str(canonical), status_code=301)

    response = await call_next(request)
    # Add HSTS header for HTTPS enforcement
    if url.scheme == "https" or os.getenv("RENDER_EXTERNAL_URL"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Content-Language"] = "en"
    return response


# ─────────────────────────────────────────────
# Constants & helpers
# ─────────────────────────────────────────────
SPOOF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "video",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}


def _make_headers_for_url(url: str) -> dict:
    """Return a copy of SPOOF_HEADERS with a Referer matching the target site."""
    headers = dict(SPOOF_HEADERS)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
    except Exception:
        headers["Referer"] = "https://www.google.com/"
    return headers

# Minimal URL sanity check — just needs a host with at least one dot.
# We deliberately allow ALL domains so every yt-dlp-supported site works.
URL_PATTERN = re.compile(
    r"^https?://[^/\s]+\.[^/\s]",
    re.IGNORECASE,
)

# YouTube player client preference order — updated for mid-2026.
_YT_PLAYER_CLIENTS = ["tv_embedded", "ios", "web_creator", "android"]

YDL_OPTS_BASE: dict = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": False,
    "http_headers": SPOOF_HEADERS,
    "extractor_args": {
        "instagram": {"max_comments": ["0"]},
        "facebook": {},
        "youtube": {
            "skip": ["webpage"],
        },
    },
}

# Browser impersonation: use curl-cffi to mimic Chrome's TLS fingerprint.
# This is the single most effective way to bypass bot detection on datacenter IPs
# without needing cookies. Only enabled if curl-cffi + yt-dlp support it.
if _IMPERSONATE_TARGET is not None:
    YDL_OPTS_BASE["impersonate"] = _IMPERSONATE_TARGET
    logger.info("[yt-dlp] Browser impersonation enabled (chrome)")
else:
    logger.info("[yt-dlp] Browser impersonation not available — curl-cffi may be missing")

# Apply cookies to bypass age restrictions and bot detection
if os.path.exists("cookies.txt"):
    YDL_OPTS_BASE["cookiefile"] = "cookies.txt"

# Apply proxy if configured via environment variable (good for scaling)
_proxy = os.getenv("DOWNSNAP_PROXY")
if _proxy:
    YDL_OPTS_BASE["proxy"] = _proxy


def sanitize_url(raw: str) -> str:
    """Strip whitespace and validate basic URL structure."""
    url = raw.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    # Only reject strings that clearly aren't URLs at all (no host, no dot)
    if not URL_PATTERN.match(url):
        raise ValueError("That doesn't look like a valid web link. Please paste the full URL starting with https://")
    return url


def classify_url(url: str) -> str:
    """Return 'facebook', 'instagram', 'youtube', or 'generic'."""
    lower = url.lower()
    if "facebook.com" in lower or "fb.watch" in lower:
        return "facebook"
    if "instagram.com" in lower:
        return "instagram"
    if "youtube.com" in lower or "youtu.be" in lower:
        return "youtube"
    return "generic"


def guess_filename(url: str, content_type: Optional[str]) -> str:
    """Derive a safe filename from the URL or content-type."""
    parsed_path = urllib.parse.urlparse(url).path
    name = parsed_path.split("/")[-1].split("?")[0] or "media"
    if "." not in name and content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
        name += ext
    return name or "download"


def extract_best_format(formats: list[dict]) -> Optional[str]:
    """Pick the highest-quality progressive (audio+video muxed) URL."""
    if not formats:
        return None
        
    # We must exclude HLS (.m3u8) and DASH playlists because the proxy and browser 
    # cannot stream or download them as single MP4 files.
    direct_formats = [
        f for f in formats 
        if "m3u8" not in f.get("protocol", "") 
        and "dash" not in f.get("protocol", "")
        and ".m3u8" not in f.get("url", "")
    ]
    
    # If the site ONLY provides HLS, we fallback to it (though it will cause issues)
    candidates = direct_formats if direct_formats else formats

    # Prefer formats with both video + audio, sorted by height
    combined = [
        f for f in candidates
        if f.get("vcodec") not in (None, "none")
        and f.get("acodec") not in (None, "none")
        and f.get("url")
    ]
    if combined:
        best = max(combined, key=lambda f: f.get("height") or 0)
        return best["url"]
    
    # Fallback 1: any format with video
    video_only = [f for f in candidates if f.get("vcodec") not in (None, "none") and f.get("url")]
    if video_only:
        return max(video_only, key=lambda f: f.get("height") or 0)["url"]
        
    # Fallback 2: anything with a URL
    for f in reversed(candidates):
        if f.get("url"):
            return f["url"]
    return None


def _flatten_entries(info: dict) -> list[dict]:
    """
    Recursively collect all leaf entries from a yt-dlp info dict.
    yt-dlp sometimes nests entries (e.g. Instagram profile → posts → slides).
    Returns a flat list of dicts that each represent one media asset.
    """
    if "entries" in info:
        entries = info.get("entries") or []
        leaves = []
        for entry in entries:
            if not entry:
                continue
            leaves.extend(_flatten_entries(entry))
        return leaves
    
    # This node is a leaf (no entries array)
    return [info]


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────
class FetchRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        try:
            return sanitize_url(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class MediaItem(BaseModel):
    type: str          # "image" | "video"
    url: str
    thumbnail: Optional[str] = None
    title: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None


class FetchResponse(BaseModel):
    platform: str
    title: Optional[str]
    thumbnail: Optional[str]
    media: list[MediaItem]


# ─────────────────────────────────────────────
# Info extraction helpers
# ─────────────────────────────────────────────
def _has_video_formats(formats: list[dict]) -> bool:
    """Check if any format in the list has a video codec."""
    return any(
        f.get("vcodec") not in (None, "none", "") and f.get("url")
        for f in formats
    )


def _build_media_item_from_entry(entry: dict) -> MediaItem:
    """
    Convert a single yt-dlp info dict into a MediaItem.
    Tries multiple strategies to locate a usable media URL:
      1. formats[]          – standard video with quality options
      2. requested_formats[]– yt-dlp pre-selected best formats
      3. url                – direct media URL (images, simple videos)
      4. thumbnails[]       – last-resort image fallback
    """
    media_type = "image"
    media_url: Optional[str] = None

    # ── Strategy 1: formats array (most videos) ──────────────
    if entry.get("formats"):
        if _has_video_formats(entry["formats"]):
            media_type = "video"
        elif any(f.get("acodec") not in (None, "none", "") for f in entry["formats"] if f.get("url")):
            media_type = "video"
        media_url = extract_best_format(entry["formats"])

    # ── Strategy 2: requested_formats (yt-dlp best-pick) ─────
    if not media_url and entry.get("requested_formats"):
        if _has_video_formats(entry["requested_formats"]):
            media_type = "video"
        elif any(f.get("acodec") not in (None, "none", "") for f in entry["requested_formats"] if f.get("url")):
            media_type = "video"
        media_url = extract_best_format(entry["requested_formats"])

    # ── Strategy 3: direct url field ─────────────────────────
    if not media_url and entry.get("url"):
        media_url = entry["url"]
        if entry.get("duration") or entry.get("vcodec") not in (None, "none", ""):
            media_type = "video"
        else:
            media_type = "image"

    # ── Strategy 4: thumbnails array ─────────────────────────
    if not media_url:
        thumbs = entry.get("thumbnails") or []
        valid = [t for t in thumbs if t.get("url")]
        if valid:
            best_thumb = max(valid, key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
            media_url = best_thumb["url"]
            media_type = "image"

    # ── Strategy 5: thumbnail string ─────────────────────────
    if not media_url and entry.get("thumbnail"):
        media_url = entry["thumbnail"]
        media_type = "image"

    if not media_url:
        raise ValueError("No usable URL found in entry.")

    if media_type == "image" and re.search(r'\.(mp4|webm|mkv|avi|mov|flv|wmv|3gp|m4v|ts)([/?#&]|$)', media_url, re.I):
        media_type = "video"

    return MediaItem(
        type=media_type,
        url=media_url,
        thumbnail=entry.get("thumbnail") or (entry.get("thumbnails") or [{}])[-1].get("url"),
        title=entry.get("title") or entry.get("description"),
        width=entry.get("width"),
        height=entry.get("height"),
        duration=entry.get("duration"),
    )


def run_yt_dlp(url: str) -> dict:
    """
    Run yt-dlp extraction and return raw info dict.
    For YouTube URLs, if the default player client chain fails, retries with
    each client individually to maximise success rate against YouTube's
    rotating player JS obfuscation.
    """
    opts = dict(YDL_OPTS_BASE)
    # Deep-copy extractor_args so mutations don't bleed between calls
    opts["extractor_args"] = {k: dict(v) for k, v in YDL_OPTS_BASE["extractor_args"].items()}
    # Set dynamic Referer header matching the target site
    opts["http_headers"] = _make_headers_for_url(url)

    is_youtube = "youtube.com" in url or "youtu.be" in url

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info or {}
    except yt_dlp.utils.YoutubeDLError:
        opts.pop("impersonate", None)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info or {}
    except yt_dlp.utils.DownloadError as exc:
        err_str = str(exc)

        # ── YouTube retry with individual clients ──────────────────────
        if not is_youtube or "player response" not in err_str.lower():
            raise

        last_exc = exc
        for client in _YT_PLAYER_CLIENTS:
            retry_opts = dict(opts)
            retry_opts["extractor_args"] = {
                **opts["extractor_args"],
                "youtube": {"player_client": [client], "skip": ["hls", "dash"]},
            }
            try:
                with yt_dlp.YoutubeDL(retry_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if info:
                    return info
            except yt_dlp.utils.DownloadError as retry_exc:
                last_exc = retry_exc
                continue

        # All clients exhausted
        raise last_exc


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
@app.post("/api/fetch-info", response_model=FetchResponse)
async def fetch_info(payload: FetchRequest):
    """
    Parse a URL and return structured media metadata.
    Handles Facebook, Instagram (including carousels), and generic URLs.
    """
    url = payload.url
    platform = classify_url(url)

    try:
        info = run_yt_dlp(url)
    except yt_dlp.utils.DownloadError as exc:
        detail = str(exc).lower()

        # ── All messages here are plain English, user-facing — no dev jargon ──

        # Login / private content → try Hydra fallback first (for Instagram)
        # "logged" matches "logged-in" / "logged in"
        # "empty media" matches "instagram sent an empty media response"
        if any(kw in detail for kw in [
            "private", "login", "logged", "sign in", "sign-in",
            "authentication", "cookies", "account", "members only",
            "empty media",
        ]):
            info = {}  # let the empty-results path trigger Hydra for Instagram

        elif any(kw in detail for kw in ["player response", "playerresponse", "nsig"]):
            info = {}  # fall through to Hydra fallback (Invidious/Cobalt)

        elif any(kw in detail for kw in ["geo", "not available in your country", "region"]):
            raise HTTPException(status_code=451, detail={
                "code": "geo_blocked",
                "message": "This video isn't available in your region.",
                "hint": "The uploader has restricted this content to certain countries.",
            })

        elif any(kw in detail for kw in ["copyright", "removed", "has been terminated", "account has been"]):
            raise HTTPException(status_code=410, detail={
                "code": "removed",
                "message": "This video has been removed or taken down.",
                "hint": "The content may have been deleted by the uploader or removed for policy reasons.",
            })

        elif "age" in detail and any(kw in detail for kw in ["restrict", "gate", "confirm"]):
            raise HTTPException(status_code=403, detail={
                "code": "age_restricted",
                "message": "This video is age-restricted and can't be downloaded without a login.",
                "hint": "Age-gated content requires an account to access.",
            })

        elif "drm" in detail or "widevine" in detail or "encrypted" in detail:
            raise HTTPException(status_code=403, detail={
                "code": "drm",
                "message": "This video is DRM-protected and can't be downloaded.",
                "hint": "DRM-protected videos (like Netflix, Disney+) are encrypted and can't be saved.",
            })

        elif any(kw in detail for kw in ["premium", "subscription", "paid", "paywalled"]):
            raise HTTPException(status_code=403, detail={
                "code": "premium",
                "message": "This content is behind a paywall or requires a paid subscription.",
                "hint": "Only free, publicly accessible content can be downloaded.",
            })

        elif any(kw in detail for kw in ["404", "not found", "video unavailable", "no video", "deleted"]):
            raise HTTPException(status_code=404, detail={
                "code": "not_found",
                "message": "We couldn't find that video. It may have been deleted.",
                "hint": "Double-check the link — the post or video may no longer exist.",
            })

        elif any(kw in detail for kw in [
            "unsupported url", "no suitable", "unable to extract", "extractor"
        ]):
            raise HTTPException(status_code=400, detail={
                "code": "unsupported",
                "message": "This link or website isn't supported yet.",
                "hint": "Make sure the link points directly to a video or photo post, not a profile page or home feed.",
            })

        elif any(kw in detail for kw in ["captcha", "bot check", "robot", "challenge"]):
            raise HTTPException(status_code=503, detail={
                "code": "captcha",
                "message": "The website is blocking automated requests right now.",
                "hint": "Try again in a few minutes — the block is usually temporary.",
            })

        elif any(kw in detail for kw in ["429", "too many requests", "rate limit", "ratelimit"]):
            raise HTTPException(status_code=429, detail={
                "code": "rate_limited",
                "message": "Too many requests — the website is throttling us.",
                "hint": "Wait a minute and try again.",
            })

        elif any(kw in detail for kw in [
            "timeout", "timed out", "connection aborted", "connection reset",
            "network", "unreachable", "ssl", "certificate"
        ]):
            raise HTTPException(status_code=503, detail={
                "code": "network_error",
                "message": "Couldn't connect to the website.",
                "hint": "The site may be down, slow, or blocking our server. Try again shortly.",
            })

        elif any(kw in detail for kw in ["live", "is live", "livestream"]):
            raise HTTPException(status_code=400, detail={
                "code": "live_stream",
                "message": "Live streams can't be downloaded while they're airing.",
                "hint": "Wait until the stream ends and a replay is available, then try again.",
            })

        else:
            # Generic — do NOT expose the raw yt-dlp message
            raise HTTPException(status_code=422, detail={
                "code": "extraction_failed",
                "message": "Couldn't extract media from this link.",
                "hint": "Make sure the link points to a public video or photo post and try again.",
            })

    except HTTPException:
        raise  # re-raise our own structured errors unchanged
    except Exception as e:
        logger.error("Unhandled exception in fetch_info: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={
            "code": "server_error",
            "message": "Something went wrong on our end.",
            "hint": "Please try again in a moment.",
        })

    # ── Flatten nested entries (handles carousels, playlists, nested posts)
    try:
        media_items: list[MediaItem] = []

        if info:
            leaves = _flatten_entries(info)
            last_exc: Optional[Exception] = None

            for leaf in leaves:
                try:
                    item = _build_media_item_from_entry(leaf)
                    media_items.append(item)
                except Exception as exc:
                    last_exc = exc
                    continue  # skip unparseable entries gracefully

            # If we got zero items and there was only one leaf, surface a clean error
            if not media_items and last_exc is not None and len(leaves) == 1:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "extraction_failed",
                        "message": "Found the post but couldn't extract any downloadable media.",
                        "hint": "The post may contain only text, a live stream, or a format we can't download yet.",
                    },
                )

        if not media_items:
            # ── Hydra Fallback Network ──
            # Try third-party scrapers for ALL platforms, not just Instagram.
            # This is critical on datacenter IPs (like Render) where platforms
            # aggressively block direct yt-dlp requests.
            from scrapers import hydra_fetch
            hydra_items = await hydra_fetch(url, platform=platform)
            if hydra_items:
                # Convert dicts to MediaItems
                media_objects = [MediaItem(**i) for i in hydra_items]
                return FetchResponse(
                    platform=platform,
                    title=media_objects[0].title or "Media",
                    thumbnail=media_objects[0].thumbnail,
                    media=media_objects,
                )

            if platform == "instagram":
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "no_media",
                        "message": "Instagram requires authentication to access this post.",
                        "hint": "Try again in a moment, or ensure the post is publicly accessible.",
                    },
                )

            raise HTTPException(
                status_code=404,
                detail={
                    "code": "no_media",
                    "message": "No downloadable media was found in this post.",
                    "hint": "The post might be private, contain only text, or be from a section we can't access yet.",
                },
            )

        return FetchResponse(
            platform=platform,
            title=info.get("title") or info.get("description"),
            thumbnail=info.get("thumbnail"),
            media=media_items,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unhandled exception in fetch_info (processing): %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={
            "code": "server_error",
            "message": "Something went wrong on our end.",
            "hint": "Please try again in a moment.",
        })


@app.get("/api/download-proxy")
async def download_proxy(
    request: Request,
    media_url: str = Query(..., description="Direct media URL to proxy-stream to client"),
    filename: Optional[str] = Query(None, description="Override filename for download"),
    source_url: Optional[str] = Query(None, description="Original source URL for referer"),
):
    """
    Proxy-stream a remote media file to the client.
    Spoofs browser headers to bypass CORS, referer checks, and signed URL restrictions.
    Supports HTTP Range requests so video players can scrub and buffer correctly.
    """
    if not media_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid media URL.")

    # Build platform-specific referer dynamically
    referer = "https://www.instagram.com/"
    if source_url:
        parsed = urllib.parse.urlparse(source_url)
        referer = f"{parsed.scheme}://{parsed.netloc}/"
    elif "fbcdn" in media_url or "facebook" in media_url:
        referer = "https://www.facebook.com/"

    headers = {**SPOOF_HEADERS, "Referer": referer}
    
    # Forward the client's Range header to support video buffering/seeking
    client_range = request.headers.get("range")
    if client_range:
        headers["Range"] = client_range

    try:
        # Disable timeout for large video streams
        client = httpx.AsyncClient(follow_redirects=True, timeout=None)
        req = client.build_request("GET", media_url, headers=headers)
        response = await client.send(req, stream=True)

        if response.status_code >= 400:
            await response.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Remote server returned {response.status_code}.",
            )

        content_type = response.headers.get("content-type", "application/octet-stream")
        dl_filename = filename or guess_filename(media_url, content_type)

        async def streamer():
            try:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        # Pass through range and length headers for the browser video player
        resp_headers = {
            "Content-Disposition": f'attachment; filename="{dl_filename}"',
            "X-Content-Type-Options": "nosniff",
            "Accept-Ranges": "bytes",
        }
        
        if "content-length" in response.headers:
            resp_headers["Content-Length"] = response.headers["content-length"]
        if "content-range" in response.headers:
            resp_headers["Content-Range"] = response.headers["content-range"]

        return StreamingResponse(
            streamer(),
            status_code=response.status_code,
            media_type=content_type,
            headers=resp_headers,
        )

    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach media server: {str(exc)}")


@app.get("/ping")
async def ping():
    """
    Lightweight keep-alive endpoint.
    Point UptimeRobot / cron-job.org at this URL every 5–14 minutes
    to prevent Render's free-tier from spinning down the service.
    """
    return {"status": "pong", "ts": datetime.datetime.utcnow().isoformat() + "Z"}


@app.get("/health")
async def health():
    """Health-check endpoint (also referenced in render.yaml as healthCheckPath)."""
    return {
        "status": "ok",
        "service": "DownSnap API",
        "last_self_ping": _last_ping.isoformat() + "Z" if _last_ping else None,
    }

 
# ─────────────────────────────────────────────
# Static frontend (served by Cloudflare Pages)
# ─────────────────────────────────────────────
