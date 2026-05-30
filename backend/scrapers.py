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
    # A massive list of known public Cobalt instances hosted by different users globally.
    # If one goes down or hits a rate limit, the Hydra automatically moves to the next.
    instances = [
        "https://api.cobalt.tools",
        "https://co.wuk.sh",
        "https://cobalt-api.kwiatekm.one",
        "https://cobalt.qewertyy.dev",
        "https://api.cobalt.beparanoid.de",
        "https://cobalt.cibere.dev",
        "https://api.cobalt.ac",
        "https://cobalt.jayw.uk",
        "https://api.cobalt.wlvs.space",
        "https://cobalt.owo.network",
        "https://co.eepy.today"
    ]

    async def fetch(self, url: str) -> Optional[list[dict]]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "vQuality": "1080",
            "isAudioOnly": False
        }

        # Try instances until one works
        for api_base in self.instances:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{api_base}/api/json", 
                        headers=headers, 
                        json=payload
                    )
                    
                    if resp.status_code == 429:
                        print(f"[{self.name}] Rate limited on {api_base}")
                        continue # Try next instance
                        
                    if resp.status_code != 200:
                        continue
                        
                    data = resp.json()
                    status = data.get("status")
                    
                    if status == "error":
                        continue
                        
                    if status == "redirect" or status == "stream":
                        return [{
                            "type": "video",
                            "url": data.get("url"),
                            "title": "Instagram Story",
                            "thumbnail": None
                        }]
                        
                    if status == "picker":
                        # Carousel/Multiple items
                        items = []
                        for item in data.get("picker", []):
                            items.append({
                                "type": "video" if item.get("type") == "video" else "image",
                                "url": item.get("url"),
                                "thumbnail": item.get("thumb")
                            })
                        return items
                        
            except Exception as e:
                print(f"[{self.name}] Instance {api_base} failed: {e}")
                continue
        
        # If all instances fail, cooldown this scraper
        self.set_cooldown(1) # Cooldown for 1 hour if all public nodes are dead
        return None

# ─────────────────────────────────────────────
# 2. SnapSave / SnapInsta Fallback
# Relies on their public frontend API. 
# ─────────────────────────────────────────────
class SnapInstaScraper(BaseScraper):
    name = "snapinsta"
    
    async def fetch(self, url: str) -> Optional[list[dict]]:
        # SnapInsta requires specific form data and headers to bypass their basic bot check
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Origin": "https://snapinsta.app",
            "Referer": "https://snapinsta.app/"
        }
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
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
                
                # SnapInsta returns raw HTML containing the download links.
                # A robust implementation would use BeautifulSoup here, but for zero-dependencies
                # we can use simple string extraction.
                text = resp.text
                if "No data found" in text:
                    return None
                    
                # Extremely rudimentary extraction (Proof of concept)
                # In production, regex or bs4 is needed here.
                links = []
                import re
                # Find hrefs inside the download buttons
                matches = re.findall(r'href="(https://[^"]+)"[^>]*>Download', text)
                for match in matches:
                    links.append({
                        "type": "video", # Assume video for safety
                        "url": match.replace("&amp;", "&"),
                        "title": "Instagram Media"
                    })
                
                if links:
                    return links
                
        except Exception as e:
            print(f"[{self.name}] Failed: {e}")
            
        return None

# ─────────────────────────────────────────────
# Engine Controller
# ─────────────────────────────────────────────
SCRAPERS = [
    CobaltScraper(),
    SnapInstaScraper()
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
