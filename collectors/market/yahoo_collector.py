"""Yahoo Finance collector using yfinance library."""

import yfinance as yf
from datetime import datetime
from typing import List, Optional, Dict, Any

from collectors.base_collector import BaseCollector, CollectorResult
from watchlist import WATCHLIST


class YahooCollector(BaseCollector):
    """Collector for Yahoo Finance market data using yfinance."""

    name = "yahoo_collector"
    source = "yahoo_finance"

    # ETFs don't have fundamentals/institutional data
    ETF_SYMBOLS = {"GLD", "SLV", "SPY", "QQQ", "IWM", "EEM", "TLT", "HYG", "LQD"}

    def __init__(self, data_dir: str = "./data"):
        """Initialize the Yahoo Finance collector."""
        super().__init__(data_dir)

    def _get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time quote data."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return {
                "symbol": symbol,
                "price": info.get("regularMarketPrice") or info.get("currentPrice"),
                "change": info.get("regularMarketChange"),
                "change_percent": info.get("regularMarketChangePercent"),
                "volume": info.get("regularMarketVolume") or info.get("volume"),
                "avg_volume": info.get("averageVolume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "fifty_day_avg": info.get("fiftyDayAverage"),
                "two_hundred_day_avg": info.get("twoHundredDayAverage"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            }

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_options_data(self, symbol: str) -> Dict[str, Any]:
        """Get options data including put/call info."""
        try:
            ticker = yf.Ticker(symbol)

            # Get available expiration dates
            expirations = ticker.options
            if not expirations:
                return {"symbol": symbol, "error": "No options data available"}

            # Get nearest expiration
            nearest_exp = expirations[0]
            opt_chain = ticker.option_chain(nearest_exp)

            calls = opt_chain.calls
            puts = opt_chain.puts

            # Calculate put/call ratio based on open interest
            total_call_oi = calls['openInterest'].sum() if 'openInterest' in calls.columns else 0
            total_put_oi = puts['openInterest'].sum() if 'openInterest' in puts.columns else 0
            total_call_vol = calls['volume'].sum() if 'volume' in calls.columns else 0
            total_put_vol = puts['volume'].sum() if 'volume' in puts.columns else 0

            pc_ratio_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
            pc_ratio_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0

            # Get implied volatility (average)
            avg_call_iv = calls['impliedVolatility'].mean() if 'impliedVolatility' in calls.columns else 0
            avg_put_iv = puts['impliedVolatility'].mean() if 'impliedVolatility' in puts.columns else 0

            return {
                "symbol": symbol,
                "nearest_expiration": nearest_exp,
                "total_expirations": len(expirations),
                "total_call_open_interest": int(total_call_oi),
                "total_put_open_interest": int(total_put_oi),
                "total_call_volume": int(total_call_vol),
                "total_put_volume": int(total_put_vol),
                "put_call_ratio_oi": round(pc_ratio_oi, 3),
                "put_call_ratio_volume": round(pc_ratio_vol, 3),
                "avg_call_iv": round(avg_call_iv, 4) if avg_call_iv else None,
                "avg_put_iv": round(avg_put_iv, 4) if avg_put_iv else None,
            }

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_key_statistics(self, symbol: str) -> Dict[str, Any]:
        """Get key statistics including institutional holdings."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Get institutional holders
            try:
                inst_holders = ticker.institutional_holders
                top_holders = []
                if inst_holders is not None and not inst_holders.empty:
                    for _, row in inst_holders.head(5).iterrows():
                        top_holders.append({
                            "name": row.get("Holder", ""),
                            "shares": row.get("Shares", 0),
                            "percent": row.get("% Out", 0),
                        })
            except Exception:
                top_holders = []

            return {
                "symbol": symbol,
                "short_ratio": info.get("shortRatio"),
                "short_percent_of_float": info.get("shortPercentOfFloat"),
                "shares_short": info.get("sharesShort"),
                "shares_short_prior": info.get("sharesShortPriorMonth"),
                "held_percent_insiders": info.get("heldPercentInsiders"),
                "held_percent_institutions": info.get("heldPercentInstitutions"),
                "top_institutional_holders": top_holders,
            }

        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def collect_symbol(self, symbol: str) -> Dict[str, Any]:
        """Collect all available data for a symbol."""
        data = {
            "symbol": symbol,
            "quote": self._get_quote(symbol),
            "options": self._get_options_data(symbol),
            "collected_at": datetime.utcnow().isoformat(),
        }

        # Skip statistics for ETFs (no fundamentals data available)
        if symbol.upper() not in self.ETF_SYMBOLS:
            data["statistics"] = self._get_key_statistics(symbol)

        return data

    def collect(self, symbols: Optional[List[str]] = None) -> CollectorResult:
        """Collect market data for symbols.

        Args:
            symbols: List of symbols. Defaults to WATCHLIST stocks + indices.

        Returns:
            CollectorResult with collected data.
        """
        if symbols is None:
            stock_symbols = [s["symbol"] for s in WATCHLIST.get("stocks", [])]
            # Skip indices for now as they may have different data availability
            symbols = stock_symbols

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
        indices = {
            "^GSPC": "S&P 500",
            "^IXIC": "Nasdaq",
            "^DJI": "Dow Jones",
            "^VIX": "VIX",
            "^TNX": "10Y Treasury",
        }

        summary = {}

        for symbol, name in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")

                if not hist.empty:
                    current = hist['Close'].iloc[-1]
                    open_price = hist['Open'].iloc[-1]
                    change = current - open_price
                    change_pct = (change / open_price) * 100 if open_price else 0

                    summary[symbol] = {
                        "name": name,
                        "price": round(current, 2),
                        "change": round(change, 2),
                        "change_percent": round(change_pct, 2),
                    }
            except Exception as e:
                summary[symbol] = {"name": name, "error": str(e)}

        return summary
