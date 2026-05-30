# DownSnap: Project Status & Architecture

## 📌 Project Overview
**DownSnap** is a universal, lightweight web application designed to download media (videos, reels, stories, photos) from almost any public URL on the internet (e.g., YouTube, Facebook, Instagram, Twitter, and adult content sites). 

The project is built atomically into two distinct layers to bypass cross-origin restrictions (CORS), referrer checks, and modern web application firewalls (WAFs) without requiring expensive third-party APIs.

---

## 🏗️ Architecture (Current State)

### Frontend (Client-Side)
- **Tech Stack:** Vanilla HTML, CSS, JavaScript (No frameworks, no Tailwind).
- **Role:** Provides a responsive, dark/light mode toggleable UI. It parses user URLs, sends extraction requests to the backend, and displays the extracted media cards.
- **Download Mechanism:** Instead of downloading directly from the source (which is blocked by CORS), the frontend points the "Download" buttons to the backend's `/api/download-proxy` endpoint with dynamically generated filenames (e.g., `.mp4`, `.jpg`).

### Backend (Server-Side)
- **Tech Stack:** Python, FastAPI, `yt-dlp`, `httpx`, `curl_cffi`, `instaloader`.
- **Media Extraction (`/api/fetch-info`):** 
  - Uses `yt-dlp` to extract direct media URLs. 
  - **Bot Bypass:** Uses `curl_cffi` to impersonate a Google Chrome browser (`impersonate: "chrome"`), successfully bypassing Cloudflare and other aggressive WAFs.
  - **Age-Gate Bypass:** Automatically detects and loads a `cookies.txt` file (if present) to bypass login/age restrictions on premium and adult sites.
  - **Format Filtering:** Aggressively filters out chunked streams (HLS/DASH) to prioritize fetching direct `.mp4` files.
- **Media Proxy (`/api/download-proxy`):**
  - Streams the remote video file through the backend directly to the user's browser.
  - Passes client HTTP `Range` headers to the source server, allowing the native HTML5 video player to seamlessly seek and buffer.
  - Prevents CORS issues and spoofs `Referer` headers to trick the source server into thinking the request is coming from its own platform.

---

## 🚧 Current Limitations (Optimized for Free Hosting)

The current architecture is intentionally restricted to **Proxying Direct Files (MP4/JPG)** to remain viable on **Free Hosting Tiers** (e.g., Render, Railway, Vercel). 

**What it CAN do:**
- Download from ~90% of websites that offer direct progressive video files.
- Run on a $0 budget with minimal CPU/RAM footprint.

**What it CANNOT do:**
- Download live streams or chunked playlists (HLS/`m3u8` or DASH/`mpd`) such as those found exclusively on Twitch or highly-protected DRM platforms. 
- Proxying chunked text files as video fails in the browser because a simple proxy cannot stitch video chunks together.
- Download Instagram or Facebook **Stories**. Because stories are strictly tied to authenticated user sessions, the "Story" function has been intentionally omitted from the UI to prevent unresolvable authentication errors on the free backend.

---

## 🚀 Future Updates

### 1. The Ultimate FFmpeg Implementation
To achieve 100% internet coverage (including Twitch, live streams, and HLS-only adult sites), the backend requires an FFmpeg integration. *Note: This upgrade requires a paid hosting environment (VPS or Docker container with >1GB RAM and high bandwidth).*

**Detailed Implementation Plan:**
1. **Infrastructure Upgrade:**
   - Containerize the backend using a `Dockerfile`.
   - Install the `ffmpeg` binary at the system OS level inside the Docker container.
2. **Stream Detection:**
   - Modify `extract_best_format` to accept `.m3u8` streams if no direct `.mp4` exists.
3. **On-the-Fly Transcoding Pipeline:**
   - When the `/api/download-proxy` endpoint receives an `.m3u8` URL, it bypasses the standard `httpx` stream.
   - Instead, the backend spawns a lightweight asynchronous subprocess:
     ```bash
     ffmpeg -i "https://remote-server.com/playlist.m3u8" -c copy -f mp4 pipe:1
     ```
   - `-c copy` ensures that the video/audio codecs are NOT re-encoded (which would fry the CPU), but merely re-muxed into an MP4 container.
   - `-f mp4 pipe:1` pushes the stitched video bytes directly to the standard output (`stdout`).
4. **Streaming Response:**
   - FastAPI intercepts the `stdout` of the FFmpeg process.
   - Returns a `StreamingResponse` that chunks the FFmpeg byte output directly to the user's browser in real-time.
5. **Zero-Disk Storage:**
   - The stitched video is streamed through RAM directly to the user's download folder. The backend never saves the `.mp4` file to its own hard drive, maintaining compliance with ephemeral cloud environments and saving disk space.

*Implementation of this FFmpeg architecture will formally graduate DownSnap from a basic proxy downloader to an enterprise-grade media ingestion engine.*

### 2. Client-Side Story Downloader (Zero-Cost Scale)
To officially support private Instagram and Facebook **Stories** without spending money on fleets of burner accounts or third-party scraping APIs:
- **Build a Browser Extension / Bookmarklet:** By shifting the story-fetching logic to the client-side, we can utilize the user's own active browser session to securely request and retrieve private story URLs directly from the Instagram API. This scales infinitely with $0 in backend costs and zero risk of IP bans.
