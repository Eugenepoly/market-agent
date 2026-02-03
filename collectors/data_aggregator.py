"""Data aggregator to load latest collected data for report generation."""

import os
import json
import glob
from datetime import datetime
from typing import Dict, Any, Optional


class DataAggregator:
    """Aggregates data from all collectors for report generation."""

    def __init__(self, data_dir: str = "./data"):
        """Initialize the data aggregator.

        Args:
            data_dir: Base directory for collected data.
        """
        self.data_dir = data_dir

    def _get_latest_file(self, subdir: str, prefix: str) -> Optional[str]:
        """Get the most recent file matching the pattern.

        Args:
            subdir: Subdirectory under data_dir.
            prefix: File prefix to match.

        Returns:
            Path to the latest file or None if not found.
        """
        pattern = os.path.join(self.data_dir, subdir, f"{prefix}*.json")
        files = glob.glob(pattern)
        if not files:
            return None
        # Sort by modification time, get most recent
        files.sort(key=os.path.getmtime, reverse=True)
        return files[0]

    def _load_json_file(self, filepath: str) -> Optional[Dict]:
        """Load JSON data from file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _get_latest_analysis(self, subdir: str, prefix: str = "analysis_") -> Optional[str]:
        """Get latest analysis text file content."""
        pattern = os.path.join(self.data_dir, subdir, f"{prefix}*.txt")
        files = glob.glob(pattern)
        if not files:
            return None
        files.sort(key=os.path.getmtime, reverse=True)
        try:
            with open(files[0], "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def get_social_data(self) -> Dict[str, Any]:
        """Get latest social media monitoring data."""
        result = {"x": [], "truth_social": [], "analysis": None}

        # X/Twitter posts
        x_file = self._get_latest_file("social_posts", "x_collector_")
        if x_file:
            data = self._load_json_file(x_file)
            if data:
                result["x"] = data.get("data", [])

        # Truth Social posts
        truth_file = self._get_latest_file("social_posts", "truth_collector_")
        if truth_file:
            data = self._load_json_file(truth_file)
            if data:
                result["truth_social"] = data.get("data", [])

        # Monitor analysis
        result["analysis"] = self._get_latest_analysis("monitor")

        return result

    def get_fund_flow_data(self) -> Dict[str, Any]:
        """Get latest fund flow data."""
        result = {"raw": None, "analysis": None}

        # Raw data
        raw_file = self._get_latest_file("fund_flows", "quick_check_")
        if raw_file:
            result["raw"] = self._load_json_file(raw_file)

        # Analysis
        result["analysis"] = self._get_latest_analysis("fund_flows")

        return result

    def get_onchain_data(self) -> Dict[str, Any]:
        """Get latest on-chain data."""
        result = {"raw": None, "analysis": None}

        # Raw data
        raw_file = self._get_latest_file("onchain", "onchain_collector_")
        if raw_file:
            result["raw"] = self._load_json_file(raw_file)

        # Analysis
        result["analysis"] = self._get_latest_analysis("onchain")

        return result

    def aggregate_all(self) -> Dict[str, Any]:
        """Aggregate all available data.

        Returns:
            Dictionary with all collected data.
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "social": self.get_social_data(),
            "fund_flow": self.get_fund_flow_data(),
            "onchain": self.get_onchain_data(),
        }

    def format_for_prompt(self) -> str:
        """Format aggregated data for inclusion in report prompt.

        Returns:
            Formatted string of all collected data.
        """
        data = self.aggregate_all()
        sections = []

        # Social Media Section
        social = data.get("social", {})
        if social.get("analysis"):
            sections.append("### 大V社交动态分析\n" + social["analysis"])
        elif social.get("x") or social.get("truth_social"):
            posts_summary = []
            for post in social.get("x", [])[:5]:
                if isinstance(post, dict):
                    handle = post.get("handle", "unknown")
                    content = post.get("content", "")[:200]
                    posts_summary.append(f"- @{handle}: {content}")
            for post in social.get("truth_social", [])[:3]:
                if isinstance(post, dict):
                    handle = post.get("handle", "unknown")
                    content = post.get("content", "")[:200]
                    posts_summary.append(f"- @{handle} (Truth): {content}")
            if posts_summary:
                sections.append("### 大V社交动态\n" + "\n".join(posts_summary))

        # Fund Flow Section
        fund_flow = data.get("fund_flow", {})
        if fund_flow.get("analysis"):
            sections.append("### 资金流向分析\n" + fund_flow["analysis"])
        elif fund_flow.get("raw"):
            raw = fund_flow["raw"]
            summary = []
            if raw.get("crypto", {}).get("fear_greed"):
                fg = raw["crypto"]
                summary.append(f"- 恐惧贪婪指数: {fg.get('fear_greed')} ({fg.get('fear_greed_label', '')})")
            if raw.get("options"):
                for symbol, opt in list(raw["options"].items())[:3]:
                    pc = opt.get("pc_ratio", "N/A")
                    summary.append(f"- {symbol} Put/Call: {pc}")
            if summary:
                sections.append("### 资金流向快照\n" + "\n".join(summary))

        # On-chain Section
        onchain = data.get("onchain", {})
        if onchain.get("analysis"):
            sections.append("### 链上数据分析\n" + onchain["analysis"])

        if not sections:
            return "（暂无最新采集数据）"

        return "\n\n".join(sections)
