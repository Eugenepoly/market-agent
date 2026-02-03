"""Fund Flow Agent - analyzes institutional and retail fund flows."""

import os
import json
from datetime import datetime
from typing import Any, List, Optional

from core.base_agent import BaseAgent
from core.state import WorkflowContext, AgentResult
from collectors.market import FinvizCollector, YahooCollector
from collectors.crypto import CoinglassCollector
from watchlist import WATCHLIST


class FundFlowAgent(BaseAgent):
    """Agent for analyzing fund flows across stocks and crypto."""

    name = "fundflow_agent"
    requires_approval = False

    def __init__(self, data_dir: str = "./data"):
        """Initialize the fund flow agent."""
        super().__init__()
        self.data_dir = data_dir
        self.finviz_collector = FinvizCollector(data_dir)
        self.yahoo_collector = YahooCollector(data_dir)
        self.crypto_collector = CoinglassCollector(data_dir)

    def get_prompt(self, context: WorkflowContext) -> str:
        """Generate analysis prompt based on collected data."""
        collected_data = context.data.get("fund_flow_data", {})
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        data_text = self._format_data_for_prompt(collected_data)

        return f"""
### 角色：资金流向分析师 (Fund Flow Analyst)

### 任务
分析以下资金流向数据，识别机构和大资金的动向，判断市场情绪。

### 收集到的数据
{data_text}

### 分析要求

1. **机构动向分析**
   - 机构持仓变化最显著的标的
   - 内部人交易信号（买入/卖出）
   - 做空比例变化

2. **期权市场信号**
   - Put/Call Ratio 解读（>1 偏空，<1 偏多）
   - 隐含波动率变化
   - 异常期权活动

3. **加密货币资金流**
   - 交易所净流入/流出
   - 恐惧贪婪指数
   - 资金费率（正=做多拥挤，负=做空拥挤）
   - 清算数据

4. **综合判断**
   - 聪明钱（Smart Money）在做什么？
   - 与散户情绪的背离？
   - 潜在的反转信号？

### 输出格式

# 资金流向分析报告 [{current_time}]

## 📊 市场概览
[VIX、主要指数、恐惧贪婪指数]

## 🏦 机构动向
[按重要性排序列出]

## 📈 期权信号
[Put/Call Ratio 及解读]

## ₿ 加密资金流
[交易所流向、资金费率、清算]

## ⚡ 核心结论
[3 条最重要的发现]

## 🎯 操作建议
[基于资金流向的具体建议]
"""

    def _format_data_for_prompt(self, data: dict) -> str:
        """Format collected data for the analysis prompt."""
        sections = []

        # Market summary
        if "market_summary" in data:
            sections.append("### 市场概览")
            summary = data["market_summary"]
            for symbol, info in summary.items():
                if isinstance(info, dict) and "name" in info:
                    change = info.get("change_percent", 0)
                    sign = "+" if change and change > 0 else ""
                    sections.append(f"- {info['name']}: {info.get('price', 'N/A')} ({sign}{change:.2f}%)" if change else f"- {info['name']}: {info.get('price', 'N/A')}")

        # Stock data
        if "stocks" in data:
            sections.append("\n### 股票数据")
            for stock in data["stocks"]:
                symbol = stock.get("symbol", "")
                sections.append(f"\n**{symbol}**")

                # Quote data
                quote = stock.get("quote", {})
                if quote and quote.get("price"):
                    change = quote.get("change_percent", 0)
                    sign = "+" if change and change > 0 else ""
                    sections.append(f"- 价格: ${quote['price']} ({sign}{change:.2f}%)" if change else f"- 价格: ${quote['price']}")

                # Options
                opts = stock.get("options", {})
                if opts and "put_call_ratio_oi" in opts:
                    sections.append(f"- Put/Call Ratio (OI): {opts['put_call_ratio_oi']}")
                    sections.append(f"- Put/Call Ratio (Vol): {opts.get('put_call_ratio_volume', 'N/A')}")
                    if opts.get("avg_call_iv"):
                        sections.append(f"- 隐含波动率 (Call): {opts['avg_call_iv']*100:.1f}%")

                # Statistics from Yahoo
                stats = stock.get("statistics", {})
                if stats:
                    inst = stats.get('held_percent_institutions')
                    insider = stats.get('held_percent_insiders')
                    short_pct = stats.get('short_percent_of_float')
                    if inst:
                        sections.append(f"- 机构持仓: {inst*100:.1f}%")
                    if insider:
                        sections.append(f"- 内部人持仓: {insider*100:.1f}%")
                    if short_pct:
                        sections.append(f"- 做空比例: {short_pct*100:.2f}%")

                # Finviz data (institutional movement)
                finviz = stock.get("finviz", {})
                if finviz:
                    inst_data = finviz.get("institutional", {})
                    if inst_data:
                        sections.append(f"- 机构持仓 (Finviz): {inst_data.get('inst_own', 'N/A')}")
                        sections.append(f"- 机构变动: {inst_data.get('inst_trans', 'N/A')}")
                        sections.append(f"- 内部人变动: {inst_data.get('insider_trans', 'N/A')}")
                        sections.append(f"- 做空比例: {inst_data.get('short_float', 'N/A')}")

        # Crypto data
        if "crypto" in data:
            sections.append("\n### 加密货币数据")
            crypto = data["crypto"]

            # Fear & Greed
            fng = crypto.get("fear_greed_index", {})
            if fng and "value" in fng:
                sections.append(f"- 恐惧贪婪指数: {fng['value']} ({fng.get('classification', '')})")

            # Funding rates
            funding = crypto.get("funding_rates", {})
            if funding:
                sections.append("- 资金费率:")
                for symbol, info in funding.items():
                    if isinstance(info, dict) and "funding_rate" in info:
                        rate = info["funding_rate"] * 100
                        sections.append(f"  - {symbol}: {rate:.4f}%")

            # Open interest
            oi = crypto.get("open_interest", {})
            if oi:
                sections.append("- 未平仓合约:")
                for symbol, info in oi.items():
                    if isinstance(info, dict) and "open_interest" in info:
                        sections.append(f"  - {symbol}: {info['open_interest']:,.0f}")

            # Exchange flows (from Gemini)
            flows = crypto.get("exchange_flows", {})
            if flows and "analysis" in flows:
                sections.append(f"\n- 交易所资金流分析:\n{flows['analysis'][:500]}...")

            # Liquidations
            liqs = crypto.get("liquidations", {})
            if liqs and "analysis" in liqs:
                sections.append(f"\n- 清算数据:\n{liqs['analysis'][:500]}...")

        return "\n".join(sections) if sections else "暂无数据"

    def collect_all(self, quick: bool = False) -> dict:
        """Collect all fund flow data.

        Args:
            quick: If True, skip Gemini-based analysis for faster collection.
        """
        collected = {}

        # Market summary
        collected["market_summary"] = self.yahoo_collector.get_market_summary()

        # Stock data from Yahoo (options, quotes)
        yahoo_result = self.yahoo_collector.collect()
        if yahoo_result.success:
            collected["stocks_yahoo"] = yahoo_result.data
            self.yahoo_collector.save_data(yahoo_result, "fund_flows")

        # Stock data from Finviz (institutional, insider trading)
        finviz_result = self.finviz_collector.collect()
        if finviz_result.success:
            collected["stocks_finviz"] = finviz_result.data
            self.finviz_collector.save_data(finviz_result, "fund_flows")

        # Merge stock data
        collected["stocks"] = self._merge_stock_data(
            collected.get("stocks_yahoo", []),
            collected.get("stocks_finviz", [])
        )

        # Crypto data
        crypto_result = self.crypto_collector.collect(include_gemini_analysis=not quick)
        if crypto_result.success and crypto_result.data:
            collected["crypto"] = crypto_result.data[0]
            self.crypto_collector.save_data(crypto_result, "fund_flows")

        return collected

    def _merge_stock_data(self, yahoo_data: list, finviz_data: list) -> list:
        """Merge Yahoo and Finviz data by symbol."""
        merged = {}

        # Add Yahoo data
        for item in yahoo_data:
            symbol = item.get("symbol", "")
            if symbol:
                merged[symbol] = item

        # Merge Finviz data
        for item in finviz_data:
            symbol = item.get("symbol", "")
            if symbol:
                if symbol in merged:
                    merged[symbol]["finviz"] = item
                else:
                    merged[symbol] = {"symbol": symbol, "finviz": item}

        return list(merged.values())

    def run(self, context: WorkflowContext) -> AgentResult:
        """Execute the fund flow agent."""
        try:
            # Collect data
            collected = self.collect_all(quick=False)

            if not collected:
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    output={
                        "message": "No data collected",
                        "data": {},
                    },
                )

            # Add to context
            context.data["fund_flow_data"] = collected

            # Generate analysis
            prompt = self.get_prompt(context)

            from google.genai import types
            response = self.client.models.generate_content(
                model=self.config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )

            analysis = response.text

            # Save analysis as markdown
            filepath = self._save_analysis(analysis)

            return AgentResult(
                agent_name=self.name,
                success=True,
                output={
                    "analysis": analysis,
                    "filepath": filepath,
                    "data_summary": {
                        "stocks_collected": len(collected.get("stocks", [])),
                        "has_crypto_data": "crypto" in collected,
                        "has_market_summary": "market_summary" in collected,
                    },
                },
            )

        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    def run_quick_check(self) -> dict:
        """Run a quick check without LLM analysis."""
        collected = self.collect_all(quick=True)

        # Extract key metrics
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "market": {},
            "options": {},
            "institutional": {},
            "crypto": {},
        }

        # Market indices
        market = collected.get("market_summary", {})
        if market:
            for symbol, info in market.items():
                if isinstance(info, dict) and "price" in info:
                    summary["market"][symbol] = {
                        "name": info.get("name"),
                        "price": info.get("price"),
                        "change_percent": info.get("change_percent"),
                    }

        # Stock data
        stocks = collected.get("stocks", [])
        for stock in stocks:
            symbol = stock.get("symbol", "")
            if not symbol:
                continue

            # Options P/C ratios
            opts = stock.get("options", {})
            if opts and "put_call_ratio_oi" in opts:
                summary["options"][symbol] = {
                    "pc_ratio": opts["put_call_ratio_oi"],
                    "pc_ratio_vol": opts.get("put_call_ratio_volume"),
                    "avg_iv": opts.get("avg_call_iv"),
                }

            # Institutional from Finviz
            finviz = stock.get("finviz", {})
            if finviz:
                inst = finviz.get("institutional", {})
                if inst:
                    summary["institutional"][symbol] = {
                        "inst_own": inst.get("inst_own"),
                        "inst_trans": inst.get("inst_trans"),
                        "insider_trans": inst.get("insider_trans"),
                        "short_float": inst.get("short_float"),
                    }

        # Crypto
        crypto = collected.get("crypto", {})
        if crypto:
            fng = crypto.get("fear_greed_index", {})
            if fng:
                summary["crypto"]["fear_greed"] = fng.get("value")
                summary["crypto"]["fear_greed_label"] = fng.get("classification")

            funding = crypto.get("funding_rates", {})
            if funding:
                summary["crypto"]["funding_rates"] = {
                    k: v.get("funding_rate") for k, v in funding.items()
                    if isinstance(v, dict)
                }

        # Save markdown summary
        self._save_fund_flow_summary(summary)

        return summary

    def _save_fund_flow_summary(self, summary: dict) -> str:
        """Save fund flow data as a markdown summary."""
        timestamp = datetime.now().strftime("%Y%m%d_%H")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        output_dir = os.path.join(self.data_dir, "fund_flows")
        os.makedirs(output_dir, exist_ok=True)

        lines = [
            f"# 资金流向数据摘要 [{current_time}]",
            "",
        ]

        # Market overview
        market = summary.get("market", {})
        if market:
            lines.extend([
                "## 📊 市场概览",
                "",
                "| 指数 | 价格 | 涨跌幅 | 状态 |",
                "|------|------|--------|------|",
            ])
            for symbol, info in market.items():
                name = info.get("name", symbol)
                price = info.get("price", "N/A")
                change = info.get("change_percent", 0)
                if change is None:
                    change = 0
                sign = "+" if change > 0 else ""
                # Status emoji
                if change > 1:
                    status = "🟢 强势"
                elif change > 0:
                    status = "🟢 上涨"
                elif change < -1:
                    status = "🔴 弱势"
                elif change < 0:
                    status = "🔴 下跌"
                else:
                    status = "⚪ 持平"
                lines.append(f"| {name} | {price} | {sign}{change:.2f}% | {status} |")
            lines.append("")

        # Options data
        options = summary.get("options", {})
        if options:
            lines.extend([
                "## 📈 期权数据",
                "",
                "| 标的 | P/C Ratio (OI) | P/C Ratio (Vol) | 隐含波动率 | 信号 |",
                "|------|----------------|-----------------|------------|------|",
            ])
            for symbol, info in options.items():
                pc_ratio = info.get("pc_ratio", "N/A")
                pc_vol = info.get("pc_ratio_vol", "N/A")
                iv = info.get("avg_iv")
                iv_str = f"{iv*100:.1f}%" if iv else "N/A"
                # Signal interpretation
                if isinstance(pc_ratio, (int, float)):
                    if pc_ratio > 1.2:
                        signal = "🔴 偏空"
                    elif pc_ratio < 0.7:
                        signal = "🟢 偏多"
                    else:
                        signal = "⚪ 中性"
                else:
                    signal = "-"
                pc_ratio_str = f"{pc_ratio:.3f}" if isinstance(pc_ratio, float) else str(pc_ratio)
                pc_vol_str = f"{pc_vol:.3f}" if isinstance(pc_vol, float) else str(pc_vol)
                lines.append(f"| {symbol} | {pc_ratio_str} | {pc_vol_str} | {iv_str} | {signal} |")
            lines.append("")

        # Institutional activity
        institutional = summary.get("institutional", {})
        if institutional:
            lines.extend([
                "## 🏦 机构持仓",
                "",
                "| 标的 | 机构持仓 | 机构变动 | 内部人交易 | 做空比例 |",
                "|------|----------|----------|------------|----------|",
            ])
            for symbol, info in institutional.items():
                inst_own = info.get("inst_own", "N/A")
                inst_trans = info.get("inst_trans", "N/A")
                insider_trans = info.get("insider_trans", "N/A")
                short_float = info.get("short_float", "N/A")
                lines.append(f"| {symbol} | {inst_own} | {inst_trans} | {insider_trans} | {short_float} |")
            lines.append("")

        # Crypto metrics
        crypto = summary.get("crypto", {})
        if crypto:
            lines.extend([
                "## ₿ 加密市场",
                "",
            ])
            fng = crypto.get("fear_greed")
            fng_label = crypto.get("fear_greed_label", "")
            if fng is not None:
                # Fear & Greed emoji
                if fng <= 25:
                    fng_emoji = "😱"
                elif fng <= 45:
                    fng_emoji = "😨"
                elif fng <= 55:
                    fng_emoji = "😐"
                elif fng <= 75:
                    fng_emoji = "😊"
                else:
                    fng_emoji = "🤑"
                lines.append(f"- **恐惧贪婪指数**: {fng} ({fng_label}) {fng_emoji}")
                lines.append("")

            funding = crypto.get("funding_rates", {})
            if funding:
                lines.append("- **资金费率**:")
                for symbol, rate in funding.items():
                    if rate is not None:
                        rate_pct = rate * 100
                        sign = "+" if rate_pct > 0 else ""
                        # Interpretation
                        if rate_pct > 0.01:
                            interp = "(多头拥挤)"
                        elif rate_pct < -0.01:
                            interp = "(空头拥挤)"
                        else:
                            interp = "(中性)"
                        lines.append(f"  - {symbol}: {sign}{rate_pct:.4f}% {interp}")
                lines.append("")

        # Collection stats
        lines.extend([
            "## 📋 采集信息",
            "",
            f"- **采集时间**: {summary.get('timestamp', '')}",
            f"- **股票数据**: {len(options)} 个标的",
            f"- **机构数据**: {len(institutional)} 个标的",
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

    def _save_analysis(self, analysis: str) -> str:
        """Save analysis report as markdown file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H")
        output_dir = os.path.join(self.data_dir, "fund_flows")
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
            files = [f for f in os.listdir(directory) if f.startswith(prefix) and f.endswith(".md")]
            if len(files) > max_files:
                files.sort()
                for filename in files[:-max_files]:
                    os.remove(os.path.join(directory, filename))
        except Exception:
            pass
