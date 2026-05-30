# DownSnap 🎬

> Free HD video & photo downloader for Facebook, Instagram, and any public URL.

---

## Project Structure

```
downsnap/
├── backend/
│   ├── main.py            # FastAPI app (yt-dlp + proxy streaming)
│   └── requirements.txt   # Python dependencies
├── frontend/
│   ├── index.html         # Single-page app (Tailwind, SEO, JSON-LD)
│   └── app.js             # State machine, fetch logic, media renderer
└── README.md
```

---

## Quick Start

### 1 · Backend

```powershell
# From project root
cd backend

# Create virtual environment (Python 3.11+)
python -m venv .venv
.venv\Scripts\activate        # Windows

pip install -r requirements.txt

# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be live at **http://localhost:8000**

- `POST /api/fetch-info`     — parse media from a URL
- `GET  /api/download-proxy` — stream file to client
- `GET  /health`             — health check
- `GET  /docs`               — Swagger UI

---

### 2 · Frontend

The frontend is a single static page — no build step needed.

**Option A — Open directly:**
```
Open frontend/index.html in any browser.
```

**Option B — Serve with Python (avoids CORS quirks):**
```powershell
cd frontend
python -m http.server 3000
# Visit http://localhost:3000
```

> **Note:** The frontend assumes the backend runs on `http://localhost:8000`.  
> Update `API_BASE` in `app.js` if you deploy the backend elsewhere.

---

## API Reference

### `POST /api/fetch-info`

**Request:**
```json
{ "url": "https://www.instagram.com/p/ABC123/" }
```

**Response:**
```json
{
  "platform": "instagram",
  "title": "Post title / caption",
  "thumbnail": "https://…",
  "media": [
    {
      "type": "image",
      "url": "https://cdn.instagram.com/…",
      "thumbnail": null,
      "title": null,
      "width": 1080,
      "height": 1350,
      "duration": null
    },
    {
      "type": "video",
      "url": "https://cdn.instagram.com/…",
      "thumbnail": "https://…",
      "title": null,
      "width": 1080,
      "height": 1920,
      "duration": 15.2
    }
  ]
}
```

**Error codes:**
| Code | Meaning |
|------|---------|
| 403  | Private content / login required |
| 404  | No downloadable media found |
| 422  | URL parsing failed |
| 500  | Internal server error |

---

### `GET /api/download-proxy`

| Param | Type | Description |
|-------|------|-------------|
| `media_url` | string (required) | Direct CDN media URL to proxy |
| `filename`  | string (optional) | Override download filename |

Returns a `StreamingResponse` with `Content-Disposition: attachment`.

---

## Supported Platforms

| Platform | Posts | Stories | Reels / IGTV | Carousels |
|----------|-------|---------|--------------|-----------|
| Facebook ✓ | ✓ | ✓ | ✓ | — |
| Instagram ✓ | ✓ | ✓ | ✓ | ✓ (all slides) |
| YouTube | ✓ | — | — | — |
| Twitter/X | ✓ | — | — | — |
| TikTok | ✓ | — | — | — |
| Vimeo | ✓ | — | — | — |
| 1800+ others | ✓ via yt-dlp | | | |

> Only **public** content is supported. Private/login-gated posts will return HTTP 403.

---

## SEO Features

- Semantic HTML5 structure (`<section>`, `<article>`, `<nav>`, `<header>`, `<footer>`, `<main>`)
- JSON-LD `SoftwareApplication` schema for Google rich snippets
- Full Open Graph + Twitter Card tags
- Canonical URL tag
- Keyword-rich static content blocks
- `<h1>` → `<h2>` → `<h3>` heading hierarchy
- Lazy-loaded images (`loading="lazy"`, `decoding="async"`)
- Preconnect hints for Google Fonts
- `aria-*` labels on all interactive elements

---

## License

MIT — free for personal and commercial use.
backend cd d:\downsnap\backend
python -m uvicorn main:app --reload --port 8000

frontend: cd d:\downsnap\frontend
python -m http.server 3000
