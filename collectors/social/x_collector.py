"""X (Twitter) collector using Nitter instances."""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

from collectors.base_collector import BaseCollector, CollectorResult
from watchlist import VIP_ACCOUNTS, COLLECTOR_CONFIG


class XCollector(BaseCollector):
    """Collector for X/Twitter posts via Nitter instances."""

    name = "x_collector"
    source = "x/twitter"

    def __init__(self, data_dir: str = "./data"):
        """Initialize the X collector."""
        super().__init__(data_dir)
        self.nitter_instances = COLLECTOR_CONFIG.get("nitter_instances", [])
        self.max_posts = COLLECTOR_CONFIG.get("max_posts_per_account", 10)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })

    def _get_working_instance(self) -> Optional[str]:
        """Find a working Nitter instance."""
        for instance in self.nitter_instances:
            try:
                resp = self.session.get(instance, timeout=5)
                if resp.status_code == 200:
                    return instance
            except Exception:
                continue
        return None

    def _parse_nitter_posts(self, html: str, handle: str) -> List[dict]:
        """Parse posts from Nitter HTML."""
        soup = BeautifulSoup(html, "html.parser")
        posts = []

        # Find timeline items
        timeline_items = soup.select(".timeline-item")

        for item in timeline_items[:self.max_posts]:
            try:
                # Skip retweets if needed
                if item.select_one(".retweet-header"):
                    continue

                # Get tweet content
                content_elem = item.select_one(".tweet-content")
                if not content_elem:
                    continue

                content = content_elem.get_text(strip=True)

                # Get timestamp
                time_elem = item.select_one(".tweet-date a")
                timestamp = ""
                post_url = ""
                if time_elem:
                    timestamp = time_elem.get("title", "")
                    post_url = time_elem.get("href", "")

                # Get stats
                stats = {}
                for stat_type in ["replies", "retweets", "quotes", "likes"]:
                    stat_elem = item.select_one(f".icon-{stat_type.rstrip('s')}")
                    if stat_elem and stat_elem.parent:
                        stat_text = stat_elem.parent.get_text(strip=True)
                        # Parse numbers like "1.2K" or "500"
                        stats[stat_type] = self._parse_stat_number(stat_text)

                posts.append({
                    "handle": handle,
                    "content": content,
                    "timestamp": timestamp,
                    "url": post_url,
                    "stats": stats,
                    "collected_at": datetime.utcnow().isoformat(),
                })

            except Exception as e:
                continue

        return posts

    def _parse_stat_number(self, text: str) -> int:
        """Parse stat numbers like '1.2K' to integers."""
        text = text.strip().upper()
        if not text:
            return 0

        multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}

        for suffix, mult in multipliers.items():
            if suffix in text:
                try:
                    num = float(text.replace(suffix, "").replace(",", ""))
                    return int(num * mult)
                except ValueError:
                    return 0

        try:
            return int(text.replace(",", ""))
        except ValueError:
            return 0

    def _collect_from_nitter(self, handle: str, instance: str) -> List[dict]:
        """Collect posts for a handle from a Nitter instance."""
        url = f"{instance}/{handle}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []

            return self._parse_nitter_posts(resp.text, handle)

        except Exception as e:
            return []

    def _collect_via_gemini_search(self, handle: str) -> List[dict]:
        """Fallback: Use Gemini Search to get recent tweets."""
        try:
            from google import genai
            from google.genai import types
            from config import get_config

            config = get_config()
            client = genai.Client(api_key=config.gemini_api_key)

            prompt = f"""
Search news and social media for recent statements, announcements, or posts by @{handle} in the past 24-48 hours.

Look for:
- News articles quoting their recent statements
- Reports about their social media activity
- Any market-moving comments they made

Summarize the key points from what you find. Include:
1. What they said or announced
2. When (approximate date/time)
3. Context and potential market impact

If you find specific quotes, include them.
"""

            response = client.models.generate_content(
                model=config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )

            # Parse the response into structured data
            posts = [{
                "handle": handle,
                "content": response.text,
                "timestamp": datetime.utcnow().isoformat(),
                "url": f"https://x.com/{handle}",
                "stats": {},
                "collected_at": datetime.utcnow().isoformat(),
                "source_method": "gemini_search",
            }]

            return posts

        except Exception as e:
            return []

    def collect(self, handles: Optional[List[str]] = None, use_gemini_fallback: bool = True) -> CollectorResult:
        """Collect posts from X/Twitter.

        Args:
            handles: List of handles to collect. Defaults to VIP_ACCOUNTS.
            use_gemini_fallback: Whether to use Gemini Search as fallback.

        Returns:
            CollectorResult with collected posts.
        """
        if handles is None:
            handles = [acc["handle"] for acc in VIP_ACCOUNTS.get("x", [])]

        all_posts = []
        errors = []

        # Try Nitter first
        instance = self._get_working_instance()

        for handle in handles:
            posts = []

            if instance:
                posts = self._collect_from_nitter(handle, instance)

            # Fallback to Gemini if no posts and fallback is enabled
            if not posts and use_gemini_fallback:
                posts = self._collect_via_gemini_search(handle)
                if posts:
                    for p in posts:
                        p["source_method"] = "gemini_search"

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
                "nitter_instance": instance,
            },
        )

    def collect_single(self, handle: str) -> CollectorResult:
        """Collect posts from a single handle.

        Args:
            handle: The Twitter handle to collect.

        Returns:
            CollectorResult with collected posts.
        """
        return self.collect(handles=[handle])
