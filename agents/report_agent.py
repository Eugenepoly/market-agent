"""Report Agent - generates daily market analysis reports."""

from core.base_agent import BaseAgent
from core.state import WorkflowContext
from prompts import get_report_prompt


class ReportAgent(BaseAgent):
    """Agent for generating daily market analysis reports."""

    name = "report_agent"
    requires_approval = False

    def get_prompt(self, context: WorkflowContext) -> str:
        """Get the market analysis prompt.

        Args:
            context: The workflow context (not used for report generation).

        Returns:
            The report generation prompt.
        """
        return get_report_prompt()
