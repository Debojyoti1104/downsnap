<div align="center">

# DownSnap 🎬

**Free HD video & photo downloader for Facebook, Instagram, YouTube, TikTok and 1800+ sites.**  
No watermark · No login · No app · Instant downloads.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-2026.3+-FF0000?style=flat-square&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Deploy to Render](https://img.shields.io/badge/Deploy%20to-Render-46E3B7?style=flat-square&logo=render&logoColor=white)](https://render.com)

</div>

---

## What is DownSnap?

DownSnap is a self-hosted, open-source media downloader with a clean web interface. It extracts and proxies media directly from the source platform — no watermarks are ever added, no files are stored on the server, and no login is required.

**Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp)** — the industry-standard extraction engine with support for **1800+ websites**.

---

## Features

- ✅ **Facebook** — videos, reels, stories, live replays, group posts, `fb.watch` links
- ✅ **Instagram** — reels, stories, photos, carousels (all slides), IGTV
- ✅ **YouTube** — videos, shorts (playlists supported)
- ✅ **TikTok, Twitter/X, Vimeo, Reddit, Dailymotion, Twitch, Pinterest** and 1800+ more
- ✅ Always picks the **highest quality** format (720p / 1080p / 4K)
- ✅ **Hydra fallback** — multiple scraper engines for Instagram when yt-dlp is blocked
- ✅ **Streaming proxy** — large video files streamed directly to your browser, nothing stored
- ✅ HTTP Range support — video player scrubbing works correctly
- ✅ Clean, user-friendly error messages — no dev jargon exposed to users
- ✅ Dark / light theme with system preference detection
- ✅ Fully responsive — works on iPhone, Android, desktop
- ✅ SEO-optimised frontend (JSON-LD, Open Graph, semantic HTML5)

---

## Project Structure

```
downsnap/
├── backend/
│   ├── main.py          # FastAPI app — yt-dlp extraction + streaming proxy
│   ├── scrapers.py      # Hydra fallback scraper network (Cobalt, SnapInsta)
│   └── requirements.txt
├── frontend/
│   ├── index.html       # Single-page app (SEO, JSON-LD, Open Graph)
│   ├── style.css        # Vanilla CSS design system — dark/light themes
│   └── app.js           # State machine, fetch logic, media renderer
├── render.yaml          # One-click Render.com deployment blueprint
└── README.md
```

---

## Quick Start (Local)

### Prerequisites

- Python **3.11+**
- `pip`

### 1 · Run the backend

```powershell
cd backend

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now live at **http://localhost:8000**

| Endpoint | Method | Description |
|---|---|---|
| `/api/fetch-info` | `POST` | Extract media metadata from a URL |
| `/api/download-proxy` | `GET` | Stream a media file to the client |
| `/health` | `GET` | Health check |
| `/docs` | `GET` | Interactive Swagger UI |

### 2 · Open the frontend

The frontend is a plain static page — no build step.

```powershell
cd frontend
python -m http.server 3000
# Visit http://localhost:3000
```

> **Note:** When running locally the frontend auto-detects `localhost` and points to port `8000`. No configuration needed.

---

## Deployment (Free)

### Render.com — Recommended ✅

Render is the best free option for DownSnap. Unlike Vercel (serverless-only), Render runs FastAPI as a persistent process, which is required for yt-dlp and streaming downloads to work correctly.

**Free tier:** 750 hours/month — enough to run one instance 24/7.  
**Cold start:** ~30 seconds after 15 minutes of inactivity on the free plan.

#### Option A — One-click via Blueprint (easiest)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New → Blueprint**
3. Connect your repo — Render reads `render.yaml` and configures everything automatically
4. Click **Deploy** ✅

#### Option B — Manual setup

1. Go to [render.com](https://render.com) → **New → Web Service**
2. Connect your GitHub repo
3. Set the following:

| Setting | Value |
|---|---|
| **Root Directory** | `backend` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Free |

4. Add environment variables (optional):

| Variable | Description |
|---|---|
| `DOWNSNAP_PROXY` | Proxy URL for yt-dlp (e.g. `http://user:pass@host:port`) |
| `ALLOWED_ORIGINS` | CORS origin whitelist. Leave `*` for public use. |

5. Click **Create Web Service** — your app is live in ~2 minutes ✅

> The FastAPI backend automatically serves the `frontend/` folder as static files, so **one service hosts both the API and the UI**.

---

## API Reference

### `POST /api/fetch-info`

Extracts all downloadable media from a public URL.

**Request:**
```json
{ "url": "https://www.instagram.com/p/ABC123/" }
```

**Response:**
```json
{
  "platform": "instagram",
  "title": "Post caption",
  "thumbnail": "https://cdn.instagram.com/…",
  "media": [
    {
      "type": "video",
      "url": "https://cdn.instagram.com/…",
      "thumbnail": "https://…",
      "title": null,
      "width": 1080,
      "height": 1920,
      "duration": 15.2
    },
    {
      "type": "image",
      "url": "https://cdn.instagram.com/…",
      "thumbnail": null,
      "title": null,
      "width": 1080,
      "height": 1350,
      "duration": null
    }
  ]
}
```

**Error codes:**

| Code | Meaning |
|---|---|
| `400` | Bad URL or unsupported site |
| `403` | Private, age-restricted, DRM-protected, or paywalled content |
| `404` | Post deleted or not found |
| `410` | Content removed (copyright / policy) |
| `422` | Extraction failed |
| `429` | Rate limited by the source platform |
| `451` | Geo-restricted content |
| `503` | Network error or temporary block |

---

### `GET /api/download-proxy`

Proxies a remote media file directly to the browser as a download.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `media_url` | `string` | ✅ | Direct CDN media URL |
| `filename` | `string` | ❌ | Override the downloaded filename |
| `source_url` | `string` | ❌ | Original page URL (used to set `Referer` header) |

Supports HTTP **Range** requests — video scrubbing works natively in the browser.

---

## Supported Platforms

| Platform | Videos | Photos | Carousels | Stories | Reels |
|---|---|---|---|---|---|
| Facebook | ✅ | — | — | ✅ | ✅ |
| Instagram | ✅ | ✅ | ✅ | ✅ | ✅ |
| YouTube | ✅ | — | — | — | ✅ Shorts |
| TikTok | ✅ | — | — | — | — |
| Twitter / X | ✅ | — | — | — | — |
| Vimeo | ✅ | — | — | — | — |
| Reddit | ✅ | — | — | — | — |
| Dailymotion | ✅ | — | — | — | — |
| Twitch | ✅ Clips/VODs | — | — | — | — |
| **1800+ others** | ✅ via yt-dlp | | | | |

> Only **public** content is supported. Private, age-gated, DRM-protected, or paywalled content cannot be downloaded.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DOWNSNAP_PROXY` | _(unset)_ | HTTP/SOCKS proxy passed to yt-dlp |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins, or `*` for all |

**Cookie support:** Place a `cookies.txt` (Netscape format) inside `backend/` to bypass age restrictions or bot detection. yt-dlp picks it up automatically.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com) + [uvicorn](https://www.uvicorn.org) |
| Extraction | [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| HTTP client | [httpx](https://www.python-httpx.org) (async, streaming) |
| Frontend | Vanilla HTML + CSS + JavaScript (no framework, no build step) |
| Fonts | [Geist](https://vercel.com/font) via Google Fonts |
| Deployment | [Render.com](https://render.com) (free tier) |

---

## License

[MIT](LICENSE) — free for personal and commercial use.

---

<div align="center">
  Built with ❤️ · Powered by <code>yt-dlp</code> + FastAPI
</div>
