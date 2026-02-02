"""Social Agent - generates X/Twitter post drafts."""

from typing import Any, Optional

from core.base_agent import BaseAgent
from core.state import WorkflowContext
from prompts import get_social_prompt


class SocialAgent(BaseAgent):
    """Agent for generating social media (X/Twitter) post drafts.

    This agent requires human approval before the draft is finalized.
    The draft is saved to a file for the user to manually copy and post.
    """

    name = "social_agent"
    requires_approval = True

    def get_prompt(self, context: WorkflowContext) -> str:
        """Get the social media prompt.

        Args:
            context: The workflow context containing report and optionally analysis.

        Returns:
            The social media draft prompt.

        Raises:
            ValueError: If no report is found in the context.
        """
        report = context.data.get("report_agent")
        if not report:
            raise ValueError("No report found in context. ReportAgent must run first.")

        # Get analysis if available
        analysis_data = context.data.get("deep_analysis_agent")
        analysis = None
        if analysis_data and isinstance(analysis_data, dict):
            analysis = analysis_data.get("analysis")

        return get_social_prompt(report, analysis)

    def get_tools(self) -> Optional[list]:
        """Social agent doesn't need search tools."""
        return None

    def process_response(self, response_text: str, context: WorkflowContext) -> Any:
        """Process the social media draft response.

        Args:
            response_text: The raw response from the model.
            context: The workflow context.

        Returns:
            Dictionary containing the draft and metadata.
        """
        return {
            "draft": response_text,
            "platform": "x",
            "based_on_analysis": "deep_analysis_agent" in context.data,
        }
