"""On-chain data collector for whale monitoring.

TODO: 升级到 Whale Alert API
- 官网: https://whale-alert.io
- 需要付费订阅 ($29.95/month)
- 支持 WebSocket 实时推送
- 可替换现有 Gemini Search 方案
"""

import requests
from datetime import datetime
from typing import List, Optional, Dict, Any

from collectors.base_collector import BaseCollector, CollectorResult
from watchlist import WATCHLIST, ONCHAIN_CONFIG


class OnchainCollector(BaseCollector):
    """Collector for on-chain whale activity and large transactions."""

    name = "onchain_collector"
    source = "onchain"

    def __init__(self, data_dir: str = "./data"):
        """Initialize the on-chain collector."""
        super().__init__(data_dir)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        self.min_btc_value = ONCHAIN_CONFIG.get("min_btc_value", 100)
        self.min_eth_value = ONCHAIN_CONFIG.get("min_eth_value", 1000)

    def _get_btc_large_transactions(self) -> Dict[str, Any]:
        """Get large BTC transactions from recent blocks via blockchain.com.

        Note: blockchain.com rate limit is 1 request per 10 seconds.
        """
        try:
            # Get latest block
            resp = self.session.get(
                "https://blockchain.info/latestblock",
                timeout=10
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            latest = resp.json()
            block_height = latest.get("height", 0)

            # Get recent block transactions
            resp = self.session.get(
                f"https://blockchain.info/rawblock/{latest.get('hash')}",
                timeout=15
            )
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}

            block_data = resp.json()
            large_txs = []

            for tx in block_data.get("tx", [])[:50]:  # Check first 50 txs
                total_output = sum(out.get("value", 0) for out in tx.get("out", []))
                btc_value = total_output / 100_000_000  # satoshi to BTC

                if btc_value >= self.min_btc_value:
                    large_txs.append({
                        "hash": tx.get("hash", "")[:16] + "...",
                        "btc_value": round(btc_value, 2),
                        "outputs": len(tx.get("out", [])),
                        "time": datetime.fromtimestamp(tx.get("time", 0)).isoformat(),
                    })

            return {
                "block_height": block_height,
                "large_transactions": large_txs[:10],  # Top 10
                "threshold_btc": self.min_btc_value,
                "collected_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"error": str(e)}

    def _get_whale_addresses_balance(self) -> Dict[str, Any]:
        """Check balances of known whale addresses."""
        whale_addresses = ONCHAIN_CONFIG.get("whale_addresses", {})
        results = {}

        # BTC addresses
        btc_addresses = whale_addresses.get("btc", [])
        if btc_addresses:
            try:
                address_list = "|".join(btc_addresses[:5])  # Limit to 5
                resp = self.session.get(
                    f"https://blockchain.info/balance?active={address_list}",
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results["btc"] = {
                        addr: {
                            "balance_btc": info.get("final_balance", 0) / 100_000_000,
                            "tx_count": info.get("n_tx", 0),
                        }
                        for addr, info in data.items()
                    }
            except Exception as e:
                results["btc"] = {"error": str(e)}

        return results

    def _get_whale_alerts_news(self) -> Dict[str, Any]:
        """Get recent whale alert news via Gemini Search."""
        try:
            from google import genai
            from google.genai import types
            from config import get_config

            config = get_config()
            client = genai.Client(api_key=config.gemini_api_key)

            prompt = """
Search for the latest cryptocurrency whale alerts and large transactions in the past 24 hours.

Look for:
1. Large BTC transfers (>1000 BTC)
2. Large ETH transfers (>10000 ETH)
3. Large stablecoin movements (USDT, USDC >100M)
4. Exchange deposits/withdrawals by whales
5. Any notable wallet activity from known entities

For each significant movement, note:
- Amount and asset
- From/To (if known: exchange, unknown wallet, etc.)
- Potential market implications

Focus on movements that could indicate:
- Selling pressure (large deposits to exchanges)
- Accumulation (withdrawals from exchanges)
- OTC deals or institutional activity
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

    def _get_exchange_reserves(self) -> Dict[str, Any]:
        """Get exchange reserve data via Gemini Search."""
        try:
            from google import genai
            from google.genai import types
            from config import get_config

            config = get_config()
            client = genai.Client(api_key=config.gemini_api_key)

            prompt = """
Search for the latest cryptocurrency exchange reserve data.

Look for:
1. Bitcoin exchange reserves trend (increasing or decreasing)
2. Ethereum exchange reserves trend
3. Net exchange inflows/outflows in the past 24-48 hours
4. Which exchanges are seeing the most activity

Provide specific numbers if available from sources like:
- CryptoQuant
- Glassnode
- IntoTheBlock
- Santiment

Explain what the reserve trends suggest about market sentiment.
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

    def collect(self, quick: bool = False) -> CollectorResult:
        """Collect on-chain data.

        Args:
            quick: If True, skip Gemini analysis for faster collection.

        Returns:
            CollectorResult with collected data.
        """
        data = {
            "btc_large_transactions": self._get_btc_large_transactions(),
            "whale_addresses": self._get_whale_addresses_balance(),
            "collected_at": datetime.utcnow().isoformat(),
        }

        if not quick:
            data["whale_alerts"] = self._get_whale_alerts_news()
            data["exchange_reserves"] = self._get_exchange_reserves()

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
                "quick_mode": quick,
                "min_btc_value": self.min_btc_value,
                "min_eth_value": self.min_eth_value,
            },
        )
