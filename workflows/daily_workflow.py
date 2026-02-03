"""Daily workflow definition."""

from typing import List, Optional

from core.base_agent import BaseAgent
from agents import ReportAgent, DeepAnalysisAgent, SocialAgent
from agents.data_collection_agent import DataCollectionAgent


class DailyWorkflow:
    """Daily market analysis workflow.

    Pipeline:
    1. DataCollectionAgent - Collect VIP social, fund flow, onchain data (optional)
    2. ReportAgent - Generate daily market report (uses collected data)
    3. DeepAnalysisAgent - Deep dive into key topics (optional)
    4. SocialAgent - Generate X/Twitter draft (requires approval)
    """

    name = "daily"

    @staticmethod
    def create_agents(
        include_analysis: bool = True,
        analysis_topic: Optional[str] = None,
        collect_data: bool = True,
        quick_collection: bool = False,
    ) -> List[BaseAgent]:
        """Create the list of agents for this workflow.

        Args:
            include_analysis: Whether to include deep analysis step.
            analysis_topic: Optional topic for deep analysis.
            collect_data: Whether to run data collection first.
            quick_collection: If True, run quick data collection without LLM analysis.

        Returns:
            List of agent instances.
        """
        agents = []

        # Step 1: Data collection (optional but recommended)
        if collect_data:
            agents.append(DataCollectionAgent(quick=quick_collection))

        # Step 2: Report generation (uses collected data)
        agents.append(ReportAgent())

        # Step 3: Deep analysis (optional)
        if include_analysis:
            agents.append(DeepAnalysisAgent(topic=analysis_topic))

        # Step 4: Social draft (requires approval)
        agents.append(SocialAgent())

        return agents


def get_daily_workflow_factory(
    include_analysis: bool = True,
    analysis_topic: Optional[str] = None,
    collect_data: bool = True,
    quick_collection: bool = True,
):
    """Get a factory function for the daily workflow.

    Args:
        include_analysis: Whether to include deep analysis.
        analysis_topic: Optional analysis topic.
        collect_data: Whether to collect data before report.
        quick_collection: If True, run quick data collection.

    Returns:
        A callable that creates the workflow agents.
    """
    def factory():
        return DailyWorkflow.create_agents(
            include_analysis=include_analysis,
            analysis_topic=analysis_topic,
            collect_data=collect_data,
            quick_collection=quick_collection,
        )
    return factory
