"""Report Agent - generates daily market analysis reports."""

from core.base_agent import BaseAgent
from core.state import WorkflowContext
from prompts import get_report_prompt
from collectors.data_aggregator import DataAggregator


class ReportAgent(BaseAgent):
    """Agent for generating daily market analysis reports."""

    name = "report_agent"
    requires_approval = False

    def __init__(self, data_dir: str = "./data"):
        """Initialize the report agent.

        Args:
            data_dir: Directory containing collected data.
        """
        super().__init__()
        self.data_aggregator = DataAggregator(data_dir)

    def get_prompt(self, context: WorkflowContext) -> str:
        """Get the market analysis prompt with collected data.

        Args:
            context: The workflow context.

        Returns:
            The report generation prompt with pre-collected data.
        """
        # Aggregate all collected data
        collected_data = self.data_aggregator.format_for_prompt()

        return get_report_prompt(collected_data=collected_data)
