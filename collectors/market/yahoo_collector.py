"""Yahoo Finance collector for options and market data."""

import requests
from datetime import datetime
from typing import List, Optional, Dict, Any

from collectors.base_collector import BaseCollector, CollectorResult
from watchlist import WATCHLIST


class YahooCollector(BaseCollector):
    """Collector for Yahoo Finance market data."""

    name = "yahoo_collector"
    source = "yahoo_finance"

    def __init__(self, data_dir: str = "./data"):
        """Initialize the Yahoo Finance collector."""
        super().__init__(data_dir)
        self.base_url = "https://query1.finance.yahoo.com/v8/finance"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })

    def _get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote data."""
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = resp.json()
            result = data.get("quoteResponse", {}).get("result", [])

            if result:
                quote = result[0]
                return {
                    "symbol": symbol,
                    "price": quote.get("regularMarketPrice"),
                    "change": quote.get("regularMarketChange"),
                    "change_percent": quote.get("regularMarketChangePercent"),
                    "volume": quote.get("regularMarketVolume"),
                    "avg_volume": quote.get("averageDailyVolume3Month"),
                    "market_cap": quote.get("marketCap"),
                    "pe_ratio": quote.get("trailingPE"),
                    "fifty_day_avg": quote.get("fiftyDayAverage"),
                    "two_hundred_day_avg": quote.get("twoHundredDayAverage"),
                }

            return {"symbol": symbol, "error": "No data"}

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_options_data(self, symbol: str) -> Dict[str, Any]:
        """Get options data including put/call info."""
        url = f"https://query1.finance.yahoo.com/v7/finance/options/{symbol}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = resp.json()
            option_chain = data.get("optionChain", {}).get("result", [])

            if not option_chain:
                return {"symbol": symbol, "error": "No options data"}

            result = option_chain[0]
            quote = result.get("quote", {})
            options = result.get("options", [{}])[0]

            calls = options.get("calls", [])
            puts = options.get("puts", [])

            # Calculate put/call ratio based on open interest
            total_call_oi = sum(c.get("openInterest", 0) for c in calls)
            total_put_oi = sum(p.get("openInterest", 0) for p in puts)
            total_call_vol = sum(c.get("volume", 0) or 0 for c in calls)
            total_put_vol = sum(p.get("volume", 0) or 0 for p in puts)

            pc_ratio_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
            pc_ratio_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0

            return {
                "symbol": symbol,
                "expiration_dates": result.get("expirationDates", []),
                "total_call_open_interest": total_call_oi,
                "total_put_open_interest": total_put_oi,
                "total_call_volume": total_call_vol,
                "total_put_volume": total_put_vol,
                "put_call_ratio_oi": round(pc_ratio_oi, 3),
                "put_call_ratio_volume": round(pc_ratio_vol, 3),
                "implied_volatility": quote.get("impliedVolatility"),
            }

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_key_statistics(self, symbol: str) -> Dict[str, Any]:
        """Get key statistics including institutional holdings."""
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=defaultKeyStatistics,institutionOwnership"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = resp.json()
            result = data.get("quoteSummary", {}).get("result", [])

            if not result:
                return {"symbol": symbol, "error": "No data"}

            stats = result[0].get("defaultKeyStatistics", {})
            inst = result[0].get("institutionOwnership", {})

            # Get top institutional holders
            holders = inst.get("ownershipList", [])[:5]
            top_holders = [
                {
                    "name": h.get("organization", ""),
                    "shares": h.get("position", {}).get("raw", 0),
                    "percent": h.get("pctHeld", {}).get("raw", 0),
                }
                for h in holders
            ]

            return {
                "symbol": symbol,
                "short_ratio": stats.get("shortRatio", {}).get("raw"),
                "short_percent_of_float": stats.get("shortPercentOfFloat", {}).get("raw"),
                "shares_short": stats.get("sharesShort", {}).get("raw"),
                "shares_short_prior": stats.get("sharesShortPriorMonth", {}).get("raw"),
                "held_percent_insiders": stats.get("heldPercentInsiders", {}).get("raw"),
                "held_percent_institutions": stats.get("heldPercentInstitutions", {}).get("raw"),
                "top_institutional_holders": top_holders,
            }

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def collect_symbol(self, symbol: str) -> Dict[str, Any]:
        """Collect all available data for a symbol."""
        return {
            "symbol": symbol,
            "quote": self._get_quote(symbol),
            "options": self._get_options_data(symbol),
            "statistics": self._get_key_statistics(symbol),
            "collected_at": datetime.utcnow().isoformat(),
        }

    def collect(self, symbols: Optional[List[str]] = None) -> CollectorResult:
        """Collect market data for symbols.

        Args:
            symbols: List of symbols. Defaults to WATCHLIST stocks + indices.

        Returns:
            CollectorResult with collected data.
        """
        if symbols is None:
            stock_symbols = [s["symbol"] for s in WATCHLIST.get("stocks", [])]
            index_symbols = [s["symbol"] for s in WATCHLIST.get("indices", [])]
            symbols = stock_symbols + index_symbols

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

    def get_market_summary(self) -> Dict[str, Any]:
        """Get overall market summary including VIX, major indices."""
        indices = ["^GSPC", "^IXIC", "^DJI", "^VIX", "^TNX"]  # S&P, Nasdaq, Dow, VIX, 10Y Treasury

        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={','.join(indices)}"

        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            data = resp.json()
            results = data.get("quoteResponse", {}).get("result", [])

            summary = {}
            for quote in results:
                symbol = quote.get("symbol", "")
                summary[symbol] = {
                    "name": quote.get("shortName", ""),
                    "price": quote.get("regularMarketPrice"),
                    "change": quote.get("regularMarketChange"),
                    "change_percent": quote.get("regularMarketChangePercent"),
                }

            return summary

        except Exception as e:
            return {"error": str(e)}
