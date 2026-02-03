"""On-chain monitoring agent for whale activity and large transactions."""

import os
from datetime import datetime
from typing import Optional

from core.base_agent import BaseAgent
from core.state import WorkflowContext, AgentResult
from collectors.crypto.onchain_collector import OnchainCollector


class OnchainAgent(BaseAgent):
    """Agent for monitoring on-chain whale activity."""

    name = "onchain_agent"
    requires_approval = False

    def __init__(self, data_dir: str = "./data"):
        """Initialize the on-chain agent."""
        super().__init__()
        self.data_dir = data_dir
        self.collector = OnchainCollector(data_dir=data_dir)

    def get_prompt(self, context: WorkflowContext) -> str:
        """Generate analysis prompt based on collected on-chain data."""
        collected_data = context.data.get("onchain_data", {})
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        return f"""
Based on the following on-chain data, generate a concise analysis report in Chinese:

## Collected Data
{collected_data}

## Report Requirements

Generate a report with the following structure:

# 链上数据监控报告 [{current_time}]

## 🐋 巨鲸动向
- 大额转账汇总
- 交易所流入/流出趋势
- 重要钱包活动

## 📊 交易所储备
- BTC/ETH 储备变化
- 净流入/流出情况
- 对市场的潜在影响

## ⚠️ 风险信号
- 异常大额转账
- 可能的抛压/买入信号
- 值得关注的地址活动

## 📝 总结
- 1-2句话概括链上状态
- 对短期市场的影响判断

Keep the report concise and actionable.

IMPORTANT: Do NOT include any citation markers like [cite: ...] or [citation: ...] in your response.
"""

    def run(self, context: WorkflowContext = None, quick: bool = False) -> AgentResult:
        """Run on-chain monitoring.

        Args:
            context: Workflow context (optional).
            quick: If True, skip Gemini analysis for faster collection.

        Returns:
            AgentResult with monitoring data.
        """
        # Collect on-chain data
        result = self.collector.collect(quick=quick)

        # Save raw data
        self.collector.save_data(result, subdir="onchain")

        # Save markdown summary (always)
        self._save_onchain_summary(result.data)

        if quick:
            # Quick mode: just return raw data
            return AgentResult(
                agent_name=self.name,
                success=result.success,
                output=self._format_quick_summary(result.data),
                error=result.error,
            )

        # Full mode: generate analysis report
        analysis = self._generate_analysis(result.data)

        # Save analysis report
        self._save_analysis(analysis)

        return AgentResult(
            agent_name=self.name,
            success=True,
            output=analysis,
            error=result.error,
        )

    def _save_onchain_summary(self, data: list) -> str:
        """Save on-chain data as a markdown summary."""
        timestamp = datetime.now().strftime("%Y%m%d_%H")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        output_dir = os.path.join(self.data_dir, "onchain")
        os.makedirs(output_dir, exist_ok=True)

        lines = [
            f"# 链上数据摘要 [{current_time}]",
            "",
        ]

        if not data:
            lines.append("暂无数据")
        else:
            d = data[0]

            # BTC large transactions
            btc_txs = d.get("btc_large_transactions", {})
            if "error" not in btc_txs:
                threshold = btc_txs.get("threshold_btc", 100)
                block_height = btc_txs.get("block_height", "N/A")
                large_txs = btc_txs.get("large_transactions", [])

                lines.extend([
                    f"## 🔗 BTC 大额转账 (>{threshold} BTC)",
                    "",
                    f"- **区块高度**: {block_height}",
                    f"- **大额交易数**: {len(large_txs)} 笔",
                    "",
                ])

                if large_txs:
                    lines.extend([
                        "| 交易哈希 | BTC 数量 | 输出数 | 时间 |",
                        "|----------|----------|--------|------|",
                    ])
                    for tx in large_txs[:10]:
                        tx_hash = tx.get("hash", "")[:16] + "..."
                        btc_value = tx.get("btc_value", 0)
                        outputs = tx.get("outputs", 0)
                        tx_time = tx.get("time", "")
                        lines.append(f"| {tx_hash} | {btc_value:,.2f} | {outputs} | {tx_time} |")
                    lines.append("")
                else:
                    lines.append("*最新区块无大额转账*")
                    lines.append("")
            else:
                lines.extend([
                    "## 🔗 BTC 大额转账",
                    "",
                    f"*获取失败: {btc_txs.get('error', 'Unknown error')}*",
                    "",
                ])

            # Whale addresses
            whale_data = d.get("whale_addresses", {})
            btc_whales = whale_data.get("btc", {})
            if btc_whales and "error" not in btc_whales:
                lines.extend([
                    "## 🐋 巨鲸地址监控 (BTC)",
                    "",
                    "| 地址 | 余额 (BTC) | 交易数 | 状态 |",
                    "|------|-----------|--------|------|",
                ])

                total_btc = 0
                for addr, info in btc_whales.items():
                    if isinstance(info, dict) and "balance_btc" in info:
                        short_addr = addr[:12] + "..." + addr[-4:]
                        balance = info.get("balance_btc", 0)
                        tx_count = info.get("tx_count", 0)
                        total_btc += balance

                        # Status based on balance
                        if balance > 100000:
                            status = "🐋 MEGA"
                        elif balance > 10000:
                            status = "🐋 WHALE"
                        elif balance > 1000:
                            status = "🦈 SHARK"
                        else:
                            status = "🐠 FISH"

                        lines.append(f"| {short_addr} | {balance:,.2f} | {tx_count:,} | {status} |")

                lines.extend([
                    "",
                    f"**监控地址数**: {len(btc_whales)}",
                    f"**总持仓**: {total_btc:,.2f} BTC",
                    "",
                ])

            # ETH whales if present
            eth_whales = whale_data.get("eth", {})
            if eth_whales and "error" not in eth_whales:
                lines.extend([
                    "## 🐋 巨鲸地址监控 (ETH)",
                    "",
                    "| 地址 | 余额 (ETH) | 交易数 |",
                    "|------|-----------|--------|",
                ])

                for addr, info in eth_whales.items():
                    if isinstance(info, dict) and "balance_eth" in info:
                        short_addr = addr[:12] + "..." + addr[-4:]
                        balance = info.get("balance_eth", 0)
                        tx_count = info.get("tx_count", 0)
                        lines.append(f"| {short_addr} | {balance:,.2f} | {tx_count:,} |")

                lines.append("")

            # Collection info
            lines.extend([
                "## 📋 采集信息",
                "",
                f"- **采集时间**: {d.get('collected_at', current_time)}",
                f"- **数据来源**: Blockchain.info API",
                "",
            ])

        # Save file
        filename = f"summary_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Cleanup old files
        self._cleanup_old_files(output_dir, "summary_", max_files=3)

        return filepath

    def _format_quick_summary(self, data: list) -> str:
        """Format a quick summary of on-chain data."""
        if not data:
            return "No on-chain data collected."

        d = data[0]
        lines = ["# On-chain Quick Check", ""]

        # BTC large transactions
        btc_txs = d.get("btc_large_transactions", {})
        if "error" not in btc_txs:
            large_txs = btc_txs.get("large_transactions", [])
            lines.append(f"## BTC Large Transactions (>{btc_txs.get('threshold_btc', 100)} BTC)")
            lines.append(f"Block Height: {btc_txs.get('block_height', 'N/A')}")
            if large_txs:
                for tx in large_txs[:5]:
                    lines.append(f"- {tx['btc_value']} BTC @ {tx['time']}")
            else:
                lines.append("- No large transactions in latest block")
            lines.append("")

        # Whale addresses
        whale_data = d.get("whale_addresses", {})
        if whale_data.get("btc") and "error" not in whale_data.get("btc", {}):
            lines.append("## Whale Address Balances (BTC)")
            for addr, info in whale_data["btc"].items():
                short_addr = addr[:8] + "..." + addr[-4:]
                lines.append(f"- {short_addr}: {info['balance_btc']:,.2f} BTC")
            lines.append("")

        return "\n".join(lines)

    def _generate_analysis(self, data: list) -> str:
        """Generate on-chain analysis report using Gemini."""
        try:
            from google import genai
            from google.genai import types
            from config import get_config

            config = get_config()
            client = genai.Client(api_key=config.gemini_api_key)

            # Prepare data summary
            d = data[0] if data else {}

            prompt = f"""
Based on the following on-chain data, generate a concise analysis report in Chinese:

## Collected Data

### BTC Large Transactions
{d.get('btc_large_transactions', 'No data')}

### Whale Alerts (from news)
{d.get('whale_alerts', {}).get('analysis', 'No data')}

### Exchange Reserves
{d.get('exchange_reserves', {}).get('analysis', 'No data')}

## Report Requirements

Generate a report with the following structure:

# 链上数据监控报告 [{datetime.now().strftime('%Y-%m-%d %H:%M')}]

## 🐋 巨鲸动向
- 大额转账汇总
- 交易所流入/流出趋势
- 重要钱包活动

## 📊 交易所储备
- BTC/ETH 储备变化
- 净流入/流出情况
- 对市场的潜在影响

## ⚠️ 风险信号
- 异常大额转账
- 可能的抛压/买入信号
- 值得关注的地址活动

## 📝 总结
- 1-2句话概括链上状态
- 对短期市场的影响判断

Keep the report concise and actionable.

IMPORTANT: Do NOT include any citation markers like [cite: ...] or [citation: ...] in your response.
"""

            response = client.models.generate_content(
                model=config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )

            return response.text

        except Exception as e:
            return f"Error generating analysis: {str(e)}"

    def _save_analysis(self, analysis: str) -> str:
        """Save analysis report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H")
        output_dir = os.path.join(self.data_dir, "onchain")
        os.makedirs(output_dir, exist_ok=True)

        filename = f"analysis_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(analysis)

        # Cleanup old files (keep last 3)
        self._cleanup_old_files(output_dir, "analysis_", max_files=3)

        return filepath

    def _cleanup_old_files(self, directory: str, prefix: str, max_files: int = 3):
        """Remove old files, keeping only the most recent ones."""
        try:
            files = [f for f in os.listdir(directory) if f.startswith(prefix)]
            if len(files) > max_files:
                files.sort()
                for filename in files[:-max_files]:
                    os.remove(os.path.join(directory, filename))
        except Exception:
            pass
