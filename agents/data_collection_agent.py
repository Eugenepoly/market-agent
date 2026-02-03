"""Data Collection Agent - collects all monitoring data before report generation."""

from typing import Any

from core.base_agent import BaseAgent
from core.state import WorkflowContext, AgentResult
from agents.monitor_agent import MonitorAgent
from agents.fundflow_agent import FundFlowAgent
from agents.onchain_agent import OnchainAgent


class DataCollectionAgent(BaseAgent):
    """Agent that runs all data collectors before report generation.

    This agent should run first in the daily workflow to ensure
    fresh data is available for the report.
    """

    name = "data_collection_agent"
    requires_approval = False

    def __init__(self, data_dir: str = "./data", quick: bool = True):
        """Initialize the data collection agent.

        Args:
            data_dir: Directory to store collected data.
            quick: If True, run quick checks without LLM analysis.
        """
        super().__init__()
        self.data_dir = data_dir
        self.quick = quick
        self.monitor = MonitorAgent(data_dir)
        self.fundflow = FundFlowAgent(data_dir)
        self.onchain = OnchainAgent(data_dir)

    def get_prompt(self, context: WorkflowContext) -> str:
        """Not used - this agent doesn't call LLM directly."""
        return ""

    def get_tools(self):
        """No tools needed for data collection."""
        return None

    def run(self, context: WorkflowContext) -> AgentResult:
        """Run all data collectors.

        Args:
            context: The workflow context.

        Returns:
            AgentResult with collection summary.
        """
        results = {
            "monitor": None,
            "fundflow": None,
            "onchain": None,
            "errors": [],
        }

        # Run VIP monitor
        try:
            if self.quick:
                monitor_result = self.monitor.run_quick_check()
                results["monitor"] = {
                    "posts_collected": monitor_result.get("posts_collected", 0),
                    "alerts": len(monitor_result.get("alerts", [])),
                }
            else:
                monitor_result = self.monitor.run(context)
                results["monitor"] = {
                    "success": monitor_result.success,
                    "posts_collected": monitor_result.output.get("posts_collected", 0) if monitor_result.output else 0,
                }
        except Exception as e:
            results["errors"].append(f"monitor: {str(e)}")

        # Run fund flow
        try:
            if self.quick:
                fundflow_result = self.fundflow.run_quick_check()
                results["fundflow"] = {
                    "has_data": bool(fundflow_result),
                }
            else:
                fundflow_result = self.fundflow.run(context)
                results["fundflow"] = {
                    "success": fundflow_result.success,
                }
        except Exception as e:
            results["errors"].append(f"fundflow: {str(e)}")

        # Run onchain
        try:
            onchain_result = self.onchain.run(context, quick=self.quick)
            results["onchain"] = {
                "success": onchain_result.success,
            }
        except Exception as e:
            results["errors"].append(f"onchain: {str(e)}")

        # Summary
        success = len(results["errors"]) == 0
        summary = f"数据采集完成: VIP监控={results['monitor']}, 资金流向={results['fundflow']}, 链上数据={results['onchain']}"

        return AgentResult(
            agent_name=self.name,
            success=success,
            output={
                "summary": summary,
                "results": results,
            },
            error="; ".join(results["errors"]) if results["errors"] else None,
        )
