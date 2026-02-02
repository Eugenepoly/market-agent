"""Fund Flow Agent - analyzes institutional and retail fund flows."""

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

                # Options
                opts = stock.get("options", {})
                if opts and "put_call_ratio_oi" in opts:
                    sections.append(f"- Put/Call Ratio (OI): {opts['put_call_ratio_oi']}")
                    sections.append(f"- Put/Call Ratio (Vol): {opts.get('put_call_ratio_volume', 'N/A')}")

                # Statistics
                stats = stock.get("statistics", {})
                if stats:
                    sections.append(f"- 机构持仓: {stats.get('held_percent_institutions', 'N/A')}")
                    sections.append(f"- 内部人持仓: {stats.get('held_percent_insiders', 'N/A')}")
                    sections.append(f"- 做空比例: {stats.get('short_percent_of_float', 'N/A')}")

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

        # Stock data
        yahoo_result = self.yahoo_collector.collect()
        if yahoo_result.success:
            collected["stocks"] = yahoo_result.data
            self.yahoo_collector.save_data(yahoo_result, "fund_flows")

        # Crypto data
        crypto_result = self.crypto_collector.collect(include_gemini_analysis=not quick)
        if crypto_result.success and crypto_result.data:
            collected["crypto"] = crypto_result.data[0]
            self.crypto_collector.save_data(crypto_result, "fund_flows")

        return collected

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

            return AgentResult(
                agent_name=self.name,
                success=True,
                output={
                    "analysis": analysis,
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
            "crypto": {},
        }

        # Market indices
        market = collected.get("market_summary", {})
        if market:
            vix = market.get("^VIX", {})
            if vix:
                summary["market"]["vix"] = vix.get("price")
                summary["market"]["vix_change"] = vix.get("change_percent")

        # Options P/C ratios
        stocks = collected.get("stocks", [])
        for stock in stocks:
            opts = stock.get("options", {})
            if opts and "put_call_ratio_oi" in opts:
                summary["options"][stock["symbol"]] = {
                    "pc_ratio": opts["put_call_ratio_oi"],
                    "pc_ratio_vol": opts.get("put_call_ratio_volume"),
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

        return summary
