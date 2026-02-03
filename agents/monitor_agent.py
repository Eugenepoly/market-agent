"""Monitor Agent - monitors VIP accounts and generates alerts."""

import os
import json
from datetime import datetime
from typing import Any, List, Optional

from core.base_agent import BaseAgent
from core.state import WorkflowContext
from collectors.social import XCollector, TruthCollector
from watchlist import VIP_ACCOUNTS, ALERT_KEYWORDS


class MonitorAgent(BaseAgent):
    """Agent for monitoring VIP social accounts and detecting market-moving content."""

    name = "monitor_agent"
    requires_approval = False

    def __init__(self, data_dir: str = "./data"):
        """Initialize the monitor agent."""
        super().__init__()
        self.data_dir = data_dir
        self.x_collector = XCollector(data_dir)
        self.truth_collector = TruthCollector(data_dir)

    def get_prompt(self, context: WorkflowContext) -> str:
        """Generate analysis prompt based on collected posts."""
        collected_data = context.data.get("collected_posts", {})

        posts_text = self._format_posts_for_prompt(collected_data)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")

        return f"""
### 角色：社交媒体市场信号分析师

### 任务
分析以下来自重要人物（大V）的最新社交媒体帖子，识别可能影响市场的信号。

### 收集到的帖子
{posts_text}

### 分析要求

1. **市场影响评估**
   对每条重要帖子评估其市场影响：
   - 🔴 高影响：可能直接影响资产价格（如政策声明、收购消息）
   - 🟡 中影响：值得关注但影响有限
   - 🟢 低影响：日常内容，无明显市场影响

2. **关键信息提取**
   - 提及的具体资产/公司/加密货币
   - 政策方向暗示
   - 市场情绪信号（看多/看空/中立）

3. **跨账号关联**
   - 不同大V之间是否有呼应/冲突的观点
   - 是否存在信息套利机会

4. **行动建议**
   基于以上分析，给出：
   - 需要密切关注的资产
   - 潜在的交易机会或风险

### 输出格式

# VIP 社交监控报告 [{current_time}]

## 📢 重要帖子摘要
[按影响程度排序列出]

## 🎯 市场信号
[提取的关键市场信号]

## ⚡ 行动建议
[具体建议]

## 📊 情绪总览
[总体市场情绪判断]
"""

    def _format_posts_for_prompt(self, collected_data: dict) -> str:
        """Format collected posts for the analysis prompt."""
        sections = []

        for source, posts in collected_data.items():
            if not posts:
                continue

            section = f"\n### {source.upper()}\n"
            for post in posts:
                handle = post.get("handle", "unknown")
                content = post.get("content", "")
                timestamp = post.get("timestamp", "")

                # Truncate very long content
                if len(content) > 500:
                    content = content[:500] + "..."

                section += f"\n**@{handle}** ({timestamp}):\n{content}\n"

            sections.append(section)

        return "\n".join(sections) if sections else "没有收集到新帖子"

    def collect_all(self) -> dict:
        """Collect posts from all configured sources."""
        collected = {}

        # Collect from X
        x_result = self.x_collector.collect()
        if x_result.success and x_result.data:
            collected["x"] = x_result.data
            self.x_collector.save_data(x_result, "social_posts")

        # Collect from Truth Social
        truth_result = self.truth_collector.collect()
        if truth_result.success and truth_result.data:
            collected["truth_social"] = truth_result.data
            self.truth_collector.save_data(truth_result, "social_posts")

        return collected

    def detect_keywords(self, posts: List[dict]) -> List[dict]:
        """Detect alert keywords in posts."""
        alerts = []

        for post in posts:
            content = post.get("content", "").lower()
            matched_keywords = []

            for category, keywords in ALERT_KEYWORDS.items():
                for keyword in keywords:
                    if keyword.lower() in content:
                        matched_keywords.append((category, keyword))

            if matched_keywords:
                alerts.append({
                    "post": post,
                    "matched_keywords": matched_keywords,
                    "alert_level": "high" if len(matched_keywords) >= 3 else "medium",
                })

        return alerts

    def run(self, context: WorkflowContext) -> Any:
        """Execute the monitor agent.

        Collects posts, detects keywords, and generates analysis.
        """
        from core.state import AgentResult

        try:
            # Step 1: Collect posts
            collected = self.collect_all()

            if not collected:
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    output={
                        "message": "No new posts collected",
                        "posts": {},
                        "alerts": [],
                    },
                )

            # Step 2: Detect keywords
            all_posts = []
            for source_posts in collected.values():
                all_posts.extend(source_posts)

            alerts = self.detect_keywords(all_posts)

            # Step 3: Add collected data to context for analysis
            context.data["collected_posts"] = collected

            # Step 4: Generate analysis using LLM
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
                    "posts_collected": len(all_posts),
                    "sources": list(collected.keys()),
                    "alerts": alerts,
                    "keyword_alerts_count": len(alerts),
                },
            )

        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    def run_quick_check(self) -> dict:
        """Run a quick check without full LLM analysis.

        Useful for hourly monitoring.
        """
        collected = self.collect_all()

        all_posts = []
        for source_posts in collected.values():
            all_posts.extend(source_posts)

        alerts = self.detect_keywords(all_posts)

        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "posts_collected": len(all_posts),
            "sources": list(collected.keys()),
            "alerts": alerts,
            "high_priority_alerts": [a for a in alerts if a.get("alert_level") == "high"],
            "collected": collected,
        }

        # Save markdown summary
        self._save_posts_summary(result)

        return result

    def _save_posts_summary(self, result: dict) -> str:
        """Save collected posts as a markdown summary."""
        timestamp = datetime.now().strftime("%Y%m%d_%H")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        output_dir = os.path.join(self.data_dir, "monitor")
        os.makedirs(output_dir, exist_ok=True)

        # Build markdown content
        lines = [
            f"# VIP 社交监控数据摘要 [{current_time}]",
            "",
            "## 采集统计",
            f"- **帖子总数**: {result.get('posts_collected', 0)}",
            f"- **数据来源**: {', '.join(result.get('sources', []))}",
            f"- **高优先级告警**: {len(result.get('high_priority_alerts', []))} 条",
            f"- **采集时间**: {result.get('timestamp', '')}",
            "",
        ]

        # High priority alerts
        high_alerts = result.get("high_priority_alerts", [])
        if high_alerts:
            lines.extend([
                "## 🔴 高优先级告警",
                "",
                "| 账号 | 内容摘要 | 关键词 |",
                "|------|----------|--------|",
            ])
            for alert in high_alerts:
                post = alert.get("post", {})
                handle = post.get("handle", "unknown")
                content = post.get("content", "")[:80].replace("|", "\\|").replace("\n", " ")
                keywords = ", ".join([kw[1] for kw in alert.get("matched_keywords", [])])
                lines.append(f"| @{handle} | {content}... | {keywords} |")
            lines.append("")

        # All alerts
        all_alerts = result.get("alerts", [])
        medium_alerts = [a for a in all_alerts if a.get("alert_level") == "medium"]
        if medium_alerts:
            lines.extend([
                "## 🟡 中优先级告警",
                "",
            ])
            for alert in medium_alerts[:5]:
                post = alert.get("post", {})
                handle = post.get("handle", "unknown")
                content = post.get("content", "")[:100].replace("\n", " ")
                keywords = ", ".join([kw[1] for kw in alert.get("matched_keywords", [])])
                lines.append(f"- **@{handle}**: {content}... (关键词: {keywords})")
            lines.append("")

        # Posts by source
        collected = result.get("collected", {})
        for source, posts in collected.items():
            if not posts:
                continue
            source_name = "X/Twitter" if source == "x" else "Truth Social"
            lines.extend([
                f"## {source_name} ({len(posts)} 条)",
                "",
            ])
            for post in posts[:10]:
                handle = post.get("handle", "unknown")
                content = post.get("content", "")[:150].replace("\n", " ")
                timestamp_str = post.get("timestamp", "")
                stats = post.get("stats", {})
                stats_str = ""
                if stats:
                    likes = stats.get("likes", 0)
                    retweets = stats.get("retweets", 0)
                    if likes or retweets:
                        stats_str = f" (❤️ {likes:,}, 🔁 {retweets:,})"
                lines.append(f"- **@{handle}** ({timestamp_str}){stats_str}")
                lines.append(f"  > {content}...")
                lines.append("")

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
        output_dir = os.path.join(self.data_dir, "monitor")
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
