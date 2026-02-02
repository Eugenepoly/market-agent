"""Daily workflow definition."""

from typing import List, Optional

from core.base_agent import BaseAgent
from agents import ReportAgent, DeepAnalysisAgent, SocialAgent


class DailyWorkflow:
    """Daily market analysis workflow.

    Pipeline:
    1. ReportAgent - Generate daily market report
    2. DeepAnalysisAgent - Deep dive into key topics (optional)
    3. SocialAgent - Generate X/Twitter draft (requires approval)
    """

    name = "daily"

    @staticmethod
    def create_agents(
        include_analysis: bool = True,
        analysis_topic: Optional[str] = None,
    ) -> List[BaseAgent]:
        """Create the list of agents for this workflow.

        Args:
            include_analysis: Whether to include deep analysis step.
            analysis_topic: Optional topic for deep analysis.

        Returns:
            List of agent instances.
        """
        agents = [ReportAgent()]

        if include_analysis:
            agents.append(DeepAnalysisAgent(topic=analysis_topic))

        agents.append(SocialAgent())

        return agents


def get_daily_workflow_factory(
    include_analysis: bool = True,
    analysis_topic: Optional[str] = None,
):
    """Get a factory function for the daily workflow.

    Args:
        include_analysis: Whether to include deep analysis.
        analysis_topic: Optional analysis topic.

    Returns:
        A callable that creates the workflow agents.
    """
    def factory():
        return DailyWorkflow.create_agents(include_analysis, analysis_topic)
    return factory
