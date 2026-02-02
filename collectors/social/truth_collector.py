"""Truth Social collector."""

import requests
from datetime import datetime
from typing import List, Optional

from collectors.base_collector import BaseCollector, CollectorResult
from watchlist import VIP_ACCOUNTS, COLLECTOR_CONFIG


class TruthCollector(BaseCollector):
    """Collector for Truth Social posts."""

    name = "truth_collector"
    source = "truth_social"

    def __init__(self, data_dir: str = "./data"):
        """Initialize the Truth Social collector."""
        super().__init__(data_dir)
        self.base_url = "https://truthsocial.com"
        self.max_posts = COLLECTOR_CONFIG.get("max_posts_per_account", 10)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })

    def _collect_via_api(self, handle: str) -> List[dict]:
        """Try to collect via Truth Social's public API/RSS."""
        posts = []

        # Truth Social has a public RSS feed
        rss_url = f"https://truthsocial.com/@{handle}/rss"

        try:
            resp = self.session.get(rss_url, timeout=10)
            if resp.status_code == 200:
                # Parse RSS XML
                from xml.etree import ElementTree as ET
                root = ET.fromstring(resp.content)

                for item in root.findall(".//item")[:self.max_posts]:
                    title = item.find("title")
                    link = item.find("link")
                    pub_date = item.find("pubDate")
                    description = item.find("description")

                    posts.append({
                        "handle": handle,
                        "content": description.text if description is not None else (title.text if title is not None else ""),
                        "timestamp": pub_date.text if pub_date is not None else "",
                        "url": link.text if link is not None else "",
                        "stats": {},
                        "collected_at": datetime.utcnow().isoformat(),
                        "source_method": "rss",
                    })

        except Exception as e:
            pass

        return posts

    def _collect_via_gemini_search(self, handle: str) -> List[dict]:
        """Fallback: Use Gemini Search to get recent Truth Social posts."""
        try:
            from google import genai
            from google.genai import types
            from config import get_config

            config = get_config()
            client = genai.Client(api_key=config.gemini_api_key)

            prompt = f"""
Search news for recent Truth Social posts or statements by @{handle} (Donald Trump) in the past 24-48 hours.

Look for:
- News articles reporting on his Truth Social posts
- Quotes from his recent statements
- Any policy announcements or market-moving comments

Summarize the key points:
1. What he posted or announced
2. When (approximate date/time)
3. Potential market or political impact

Include specific quotes if available.
"""

            response = client.models.generate_content(
                model=config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )

            posts = [{
                "handle": handle,
                "content": response.text,
                "timestamp": datetime.utcnow().isoformat(),
                "url": f"https://truthsocial.com/@{handle}",
                "stats": {},
                "collected_at": datetime.utcnow().isoformat(),
                "source_method": "gemini_search",
            }]

            return posts

        except Exception as e:
            return []

    def collect(self, handles: Optional[List[str]] = None, use_gemini_fallback: bool = True) -> CollectorResult:
        """Collect posts from Truth Social.

        Args:
            handles: List of handles to collect. Defaults to VIP_ACCOUNTS.
            use_gemini_fallback: Whether to use Gemini Search as fallback.

        Returns:
            CollectorResult with collected posts.
        """
        if handles is None:
            handles = [acc["handle"] for acc in VIP_ACCOUNTS.get("truth_social", [])]

        all_posts = []
        errors = []

        for handle in handles:
            # Try API/RSS first
            posts = self._collect_via_api(handle)

            # Fallback to Gemini
            if not posts and use_gemini_fallback:
                posts = self._collect_via_gemini_search(handle)

            if posts:
                all_posts.extend(posts)
            else:
                errors.append(f"Failed to collect from @{handle}")

        success = len(all_posts) > 0

        return CollectorResult(
            collector_name=self.name,
            source=self.source,
            success=success,
            data=all_posts,
            error="; ".join(errors) if errors else None,
            metadata={
                "handles_requested": handles,
                "posts_collected": len(all_posts),
            },
        )

    def collect_single(self, handle: str) -> CollectorResult:
        """Collect posts from a single handle."""
        return self.collect(handles=[handle])
