"""Coinglass collector for crypto futures and exchange flow data."""

import requests
from datetime import datetime
from typing import List, Optional, Dict, Any

from collectors.base_collector import BaseCollector, CollectorResult
from watchlist import WATCHLIST


class CoinglassCollector(BaseCollector):
    """Collector for Coinglass crypto data.

    Note: Some endpoints require API key for full access.
    Free tier provides limited data.
    """

    name = "coinglass_collector"
    source = "coinglass"

    def __init__(self, data_dir: str = "./data", api_key: Optional[str] = None):
        """Initialize the Coinglass collector."""
        super().__init__(data_dir)
        self.base_url = "https://open-api.coinglass.com/public/v2"
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        if api_key:
            self.session.headers["coinglassSecret"] = api_key

    def _get_fear_greed_index(self) -> Dict[str, Any]:
        """Get crypto fear and greed index from alternative.me."""
        url = "https://api.alternative.me/fng/?limit=1"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = resp.json()
            fng = data.get("data", [{}])[0]

            return {
                "value": int(fng.get("value", 0)),
                "classification": fng.get("value_classification", ""),
                "timestamp": fng.get("timestamp", ""),
            }

        except Exception as e:
            return {"error": str(e)}

    def _get_btc_exchange_flows(self) -> Dict[str, Any]:
        """Get BTC exchange inflow/outflow data via web scraping or Gemini."""
        # Since Coinglass API requires paid subscription for detailed data,
        # we'll use Gemini Search as fallback
        try:
            from google import genai
            from google.genai import types
            from config import get_config

            config = get_config()
            client = genai.Client(api_key=config.gemini_api_key)

            prompt = """
Search for the latest Bitcoin exchange inflow and outflow data (past 24 hours).
Look for:
1. Net exchange flow (positive = inflow/selling pressure, negative = outflow/accumulation)
2. Total exchange balance trend
3. Any significant whale movements

Provide specific numbers if available.
"""

            response = client.models.generate_content(
                model=config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )

            return {
                "analysis": response.text,
                "source_method": "gemini_search",
                "collected_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"error": str(e)}

    def _get_funding_rates(self) -> Dict[str, Any]:
        """Get funding rates for major cryptos."""
        # Try free API endpoint first
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = resp.json()

            # Filter for major symbols
            major_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
            funding_rates = {}

            for item in data:
                symbol = item.get("symbol", "")
                if symbol in major_symbols:
                    funding_rates[symbol] = {
                        "funding_rate": float(item.get("lastFundingRate", 0)),
                        "mark_price": float(item.get("markPrice", 0)),
                        "index_price": float(item.get("indexPrice", 0)),
                        "next_funding_time": item.get("nextFundingTime"),
                    }

            return funding_rates

        except Exception as e:
            return {"error": str(e)}

    def _get_liquidations(self) -> Dict[str, Any]:
        """Get recent liquidation data via Gemini Search."""
        try:
            from google import genai
            from google.genai import types
            from config import get_config

            config = get_config()
            client = genai.Client(api_key=config.gemini_api_key)

            prompt = """
Search for the latest cryptocurrency liquidation data (past 24 hours).
Look for:
1. Total liquidation amount (longs vs shorts)
2. Largest single liquidation events
3. Which exchanges had the most liquidations

Provide specific numbers if available.
"""

            response = client.models.generate_content(
                model=config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )

            return {
                "analysis": response.text,
                "source_method": "gemini_search",
            }

        except Exception as e:
            return {"error": str(e)}

    def _get_open_interest(self) -> Dict[str, Any]:
        """Get futures open interest data from Binance."""
        url = "https://fapi.binance.com/fapi/v1/openInterest"

        try:
            results = {}
            symbols = ["BTCUSDT", "ETHUSDT"]

            for symbol in symbols:
                resp = self.session.get(f"{url}?symbol={symbol}", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    results[symbol] = {
                        "open_interest": float(data.get("openInterest", 0)),
                        "time": data.get("time"),
                    }

            return results

        except Exception as e:
            return {"error": str(e)}

    def collect(self, include_gemini_analysis: bool = True) -> CollectorResult:
        """Collect crypto fund flow data.

        Args:
            include_gemini_analysis: Whether to use Gemini for detailed analysis.

        Returns:
            CollectorResult with collected data.
        """
        data = {
            "fear_greed_index": self._get_fear_greed_index(),
            "funding_rates": self._get_funding_rates(),
            "open_interest": self._get_open_interest(),
            "collected_at": datetime.utcnow().isoformat(),
        }

        if include_gemini_analysis:
            data["exchange_flows"] = self._get_btc_exchange_flows()
            data["liquidations"] = self._get_liquidations()

        errors = []
        for key, value in data.items():
            if isinstance(value, dict) and "error" in value:
                errors.append(f"{key}: {value['error']}")

        return CollectorResult(
            collector_name=self.name,
            source=self.source,
            success=True,
            data=[data],
            error="; ".join(errors) if errors else None,
            metadata={
                "include_gemini_analysis": include_gemini_analysis,
            },
        )
