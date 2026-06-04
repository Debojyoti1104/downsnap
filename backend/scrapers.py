import time
import httpx
from typing import Optional

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
# 1. Cobalt API (Public Instances)
# Cobalt is an open-source downloader. People host public instances.
# It doesn't have terms of service blocking us from hitting public nodes.
# ─────────────────────────────────────────────
class CobaltScraper(BaseScraper):
    name = "cobalt"
    # Public Cobalt v2 instances — /api endpoint with Accept: application/json
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
                            "title": "Instagram Media",
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
                # Match direct CDN URLs in download links
                matches = re.findall(
                    r'href=["\x27](https://(?:cdn|scontent|video)[^"\x27]+\.(?:mp4|jpg|jpeg|png)[^"\x27]*)["\x27]',
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
# Engine Controller
# ─────────────────────────────────────────────
SCRAPERS = [
    CobaltScraper(),
    SaveIGScraper(),
    SnapInstaScraper(),
]

async def hydra_fetch(url: str) -> Optional[list[dict]]:
    """Try available scrapers in order. Return first successful result."""
    for scraper in SCRAPERS:
        if not scraper.is_available():
            continue
            
        print(f"[Hydra] Trying {scraper.name} for {url}...")
        result = await scraper.fetch(url)
        
        if result:
            print(f"[Hydra] Success with {scraper.name}")
            return result
            
    print("[Hydra] All fallback scrapers exhausted or on cooldown.")
    return None
