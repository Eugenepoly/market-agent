"""Deep Analysis Agent - performs in-depth analysis on market topics."""

from typing import Any, Optional

from core.base_agent import BaseAgent
from core.state import WorkflowContext
from prompts import get_deep_analysis_prompt


class DeepAnalysisAgent(BaseAgent):
    """Agent for deep analysis of market topics.

    Supports two modes:
    1. Manual topic: User specifies a topic to analyze
    2. Auto-extract: Agent identifies the most interesting points from the report
    """

    name = "deep_analysis_agent"
    requires_approval = False

    def __init__(self, topic: Optional[str] = None):
        """Initialize the deep analysis agent.

        Args:
            topic: Optional specific topic to analyze. If None, auto-extract.
        """
        super().__init__()
        self.topic = topic

    def get_prompt(self, context: WorkflowContext) -> str:
        """Get the deep analysis prompt.

        Args:
            context: The workflow context containing the report.

        Returns:
            The deep analysis prompt.

        Raises:
            ValueError: If no report is found in the context.
        """
        report = context.data.get("report_agent")
        if not report:
            raise ValueError("No report found in context. ReportAgent must run first.")

        return get_deep_analysis_prompt(report, self.topic)

    def process_response(self, response_text: str, context: WorkflowContext) -> Any:
        """Process the analysis response.

        Args:
            response_text: The raw response from the model.
            context: The workflow context.

        Returns:
            Dictionary containing the analysis and metadata.
        """
        return {
            "analysis": response_text,
            "topic": self.topic or "auto-extracted",
        }
