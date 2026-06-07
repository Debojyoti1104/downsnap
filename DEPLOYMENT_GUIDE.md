# DownSnap Deployment Guide

To achieve **#1 SEO rankings** and lightning-fast global load times, we highly recommend splitting your deployment into two parts: a **Static Frontend** (Free) and an **API Backend**.

This guide explains how to migrate off a monolithic Render free-tier setup to an enterprise-grade (but cheap/free) architecture.

---

## Part 1: Deploying the Frontend (100% Free)

By hosting the frontend on a CDN, your HTML/CSS/JS will load in milliseconds globally, giving you a massive SEO advantage.

### Recommended Host: Cloudflare Pages
*(Alternatives: Vercel, Netlify)*

1. Create a free account at [Cloudflare Dashboard](https://dash.cloudflare.com/) and navigate to **Workers & Pages**.
2. Click **Create Application** -> **Pages** -> **Connect to Git**.
3. Connect your GitHub repository containing the DownSnap codebase.
4. **Build Settings:**
   - **Framework preset:** `None`
   - **Build command:** *(leave blank)*
   - **Build output directory:** `frontend`
5. Click **Save and Deploy**.
6. Cloudflare will give you a free `*.pages.dev` URL. You can then attach your custom domain (`downsnap.in`) via the Cloudflare dashboard.

---

## Part 2: Adjusting the Frontend to Talk to the Backend

Currently, your frontend likely expects the backend API to be on the same domain (e.g., `/api/download`). Since the frontend is now on Cloudflare and the backend is elsewhere, you need to point the frontend to the backend's URL.

1. Open `frontend/app.js`.
2. Locate where the fetch request is made to the backend (e.g., `fetch('/api/download...')`).
3. Update it to point to your deployed backend URL.
   - Example: `fetch('https://downsnap-backend.onrender.com/api/download...')`
4. **CORS:** Ensure your Python backend is configured to allow Cross-Origin Resource Sharing (CORS) from your frontend domain (`https://downsnap.in`).
   - If using FastAPI, use `CORSMiddleware` and add `https://downsnap.in` to your `allow_origins` list.

---

## Part 3: Deploying the Backend (API)

Your backend (Python + yt-dlp) needs compute power to download and process videos.

### Option A: Render Free Tier (Current Setup)
- **Cost:** $0/month.
- **Pros:** Free.
- **Cons:** Shared IP addresses frequently get blocked by YouTube/Instagram. Server sleeps after 15 mins, causing a 30-50s "cold start" delay. 750 free hours/month limit.
- **Workaround:** Use a cron job (like cron-job.org) to ping your API every 14 minutes. Ensure you don't exceed 750 hours/month across all your Render projects.

### Option B: Dedicated VPS (Recommended for Production)
- **Cost:** ~$4 to $5/month.
- **Recommended Hosts:** Hetzner, DigitalOcean, or Linode.
- **Why it's better:** 
  1. **Zero Cold Starts:** Downloads begin instantly.
  2. **Dedicated IP:** You aren't sharing an IP with thousands of other free-tier scrapers, meaning you won't get IP-banned by TikTok or Instagram.
  3. **No Limits:** Run 24/7 without worrying about hour quotas.
- **How to deploy:**
  1. Buy a $5 Ubuntu server.
  2. Install Docker.
  3. Clone your repo to the server.
  4. Run your backend API using `docker-compose up -d`.

---

## Summary of the Final Architecture
- `https://downsnap.in` -> Points to **Cloudflare Pages** (Serves `frontend/index.html` instantly).
- `https://api.downsnap.in` -> Points to your **Backend VPS / Render Server** (Runs `backend/main.py` to fetch videos via `yt-dlp`).
