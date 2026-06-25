"""
Threat Intelligence Feed Integration — Check URL reputation via external APIs.
Supports VirusTotal, URLhaus, and PhishTank.
"""

import os
import logging
import asyncio
import aiohttp
from urllib.parse import urlparse
import hashlib

logger = logging.getLogger(__name__)

VT_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")
URLHAUS_API = "https://urlhaus-api.abuse.ch/v1/url/"
PHISHTANK_API = "https://checkurl.phishtank.com/checkurl/"


class ThreatIntel:
    def __init__(self):
        self.session: aiohttp.ClientSession = None

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": "LTI-AntiPhishing/3.0"}
            )

    async def check_virustotal(self, url: str) -> dict:
        if not VT_API_KEY:
            return {"source": "virustotal", "malicious": None, "reason": "No API key"}
        await self.ensure_session()
        url_id = hashlib.sha256(url.encode()).hexdigest()
        try:
            async with self.session.get(
                f"https://www.virustotal.com/api/v3/urls/{url_id}",
                headers={"x-apikey": VT_API_KEY},
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    malicious = stats.get("malicious", 0)
                    suspicious = stats.get("suspicious", 0)
                    return {
                        "source": "virustotal",
                        "malicious": malicious + suspicious > 0,
                        "malicious_count": malicious,
                        "suspicious_count": suspicious,
                        "total_scanners": sum(stats.values()),
                    }
                return {"source": "virustotal", "malicious": None, "error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"source": "virustotal", "malicious": None, "error": str(e)}

    async def check_urlhaus(self, url: str) -> dict:
        await self.ensure_session()
        try:
            async with self.session.post(
                URLHAUS_API,
                data={"url": url},
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("query_status") == "ok":
                        return {
                            "source": "urlhaus",
                            "malicious": True,
                            "threat": data.get("urlhaus_reference", ""),
                            "payload": data.get("payload", ""),
                        }
                return {"source": "urlhaus", "malicious": False}
        except Exception as e:
            return {"source": "urlhaus", "malicious": None, "error": str(e)}

    async def check_phishtank(self, url: str) -> dict:
        await self.ensure_session()
        try:
            async with self.session.post(
                PHISHTANK_API,
                data={"url": url, "format": "json", "app_key": "lti-antiphishing"},
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    in_database = data.get("results", {}).get("in_database", False)
                    valid_phish = data.get("results", {}).get("valid", False)
                    return {
                        "source": "phishtank",
                        "malicious": in_database and valid_phish,
                        "phish_id": data.get("results", {}).get("phish_id", ""),
                    }
                return {"source": "phishtank", "malicious": None}
        except Exception as e:
            return {"source": "phishtank", "malicious": None, "error": str(e)}

    async def check_url(self, url: str) -> dict:
        results = await asyncio.gather(
            self.check_virustotal(url),
            self.check_urlhaus(url),
            self.check_phishtank(url),
            return_exceptions=True,
        )
        combined = {"url": url, "results": []}
        malicious_count = 0
        for r in results:
            if isinstance(r, dict):
                combined["results"].append(r)
                if r.get("malicious"):
                    malicious_count += 1
        combined["malicious"] = malicious_count >= 2
        combined["threat_score"] = min(malicious_count / 3, 1.0)
        return combined

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


threat_intel = ThreatIntel()
