"""Finviz collector for institutional holdings and insider trading."""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional, Dict, Any

from collectors.base_collector import BaseCollector, CollectorResult
from watchlist import WATCHLIST


class FinvizCollector(BaseCollector):
    """Collector for Finviz market data."""

    name = "finviz_collector"
    source = "finviz"

    def __init__(self, data_dir: str = "./data"):
        """Initialize the Finviz collector."""
        super().__init__(data_dir)
        self.base_url = "https://finviz.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def _get_quote_data(self, symbol: str) -> Dict[str, Any]:
        """Get basic quote data for a symbol."""
        url = f"{self.base_url}/quote.ashx?t={symbol}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")
            data = {"symbol": symbol}

            # Parse the snapshot table
            table = soup.find("table", class_="snapshot-table2")
            if table:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    for i in range(0, len(cells) - 1, 2):
                        label = cells[i].get_text(strip=True)
                        value = cells[i + 1].get_text(strip=True)
                        data[label] = value

            return data

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_insider_trading(self, symbol: str) -> List[Dict[str, Any]]:
        """Get insider trading data for a symbol."""
        url = f"{self.base_url}/quote.ashx?t={symbol}&ty=c&p=d&b=1"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            trades = []

            # Find insider trading table
            table = soup.find("table", class_="body-table")
            if not table:
                return []

            rows = table.find_all("tr")[1:]  # Skip header

            for row in rows[:10]:  # Limit to 10 most recent
                cells = row.find_all("td")
                if len(cells) >= 6:
                    trades.append({
                        "owner": cells[0].get_text(strip=True),
                        "relationship": cells[1].get_text(strip=True),
                        "date": cells[2].get_text(strip=True),
                        "transaction": cells[3].get_text(strip=True),
                        "cost": cells[4].get_text(strip=True),
                        "shares": cells[5].get_text(strip=True),
                        "value": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                        "total_shares": cells[7].get_text(strip=True) if len(cells) > 7 else "",
                    })

            return trades

        except Exception as e:
            return []

    def _get_institutional_ownership(self, symbol: str) -> Dict[str, Any]:
        """Get institutional ownership data."""
        url = f"{self.base_url}/quote.ashx?t={symbol}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")

            # Find institutional ownership from snapshot table
            data = {}
            table = soup.find("table", class_="snapshot-table2")
            if table:
                text = table.get_text()

                # Extract key metrics
                patterns = {
                    "inst_own": r"Inst Own([\d.]+%)",
                    "inst_trans": r"Inst Trans([-\d.]+%)",
                    "insider_own": r"Insider Own([\d.]+%)",
                    "insider_trans": r"Insider Trans([-\d.]+%)",
                    "short_float": r"Short Float([\d.]+%)",
                    "short_ratio": r"Short Ratio([\d.]+)",
                }

                for key, pattern in patterns.items():
                    match = re.search(pattern, text)
                    if match:
                        data[key] = match.group(1)

            return data

        except Exception as e:
            return {"error": str(e)}

    def _get_analyst_ratings(self, symbol: str) -> Dict[str, Any]:
        """Get analyst ratings summary."""
        url = f"{self.base_url}/quote.ashx?t={symbol}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {}

            soup = BeautifulSoup(resp.text, "html.parser")
            data = {}

            # Find ratings from snapshot
            table = soup.find("table", class_="snapshot-table2")
            if table:
                text = table.get_text()

                patterns = {
                    "target_price": r"Target Price([\d.]+)",
                    "recom": r"Recom([\d.]+)",  # 1=Strong Buy, 5=Strong Sell
                }

                for key, pattern in patterns.items():
                    match = re.search(pattern, text)
                    if match:
                        data[key] = match.group(1)

            return data

        except Exception as e:
            return {"error": str(e)}

    def collect_symbol(self, symbol: str) -> Dict[str, Any]:
        """Collect all available data for a symbol."""
        return {
            "symbol": symbol,
            "quote": self._get_quote_data(symbol),
            "insider_trading": self._get_insider_trading(symbol),
            "institutional": self._get_institutional_ownership(symbol),
            "analyst": self._get_analyst_ratings(symbol),
            "collected_at": datetime.utcnow().isoformat(),
        }

    def collect(self, symbols: Optional[List[str]] = None) -> CollectorResult:
        """Collect fund flow data for symbols.

        Args:
            symbols: List of symbols. Defaults to WATCHLIST stocks.

        Returns:
            CollectorResult with collected data.
        """
        if symbols is None:
            symbols = [s["symbol"] for s in WATCHLIST.get("stocks", [])]

        all_data = []
        errors = []

        for symbol in symbols:
            try:
                data = self.collect_symbol(symbol)
                all_data.append(data)
            except Exception as e:
                errors.append(f"{symbol}: {str(e)}")

        return CollectorResult(
            collector_name=self.name,
            source=self.source,
            success=len(all_data) > 0,
            data=all_data,
            error="; ".join(errors) if errors else None,
            metadata={
                "symbols_requested": symbols,
                "symbols_collected": len(all_data),
            },
        )
