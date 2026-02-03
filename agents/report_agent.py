"""Report Agent - generates daily market analysis reports."""

from core.base_agent import BaseAgent, AgentResult
from core.state import WorkflowContext
from prompts import get_report_prompt
from collectors.data_aggregator import DataAggregator


class ReportAgent(BaseAgent):
    """Agent for generating daily market analysis reports."""

    name = "report_agent"
    requires_approval = False

    def __init__(self, data_dir: str = "./data", send_email: bool = True, test_mode: bool = False):
        """Initialize the report agent.

        Args:
            data_dir: Directory containing collected data.
            send_email: Whether to send email after generating report.
            test_mode: If True, only send email to first recipient.
        """
        super().__init__()
        self.data_aggregator = DataAggregator(data_dir)
        self.send_email = send_email
        self.test_mode = test_mode

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

    def run(self, context: WorkflowContext) -> AgentResult:
        """Run the report agent and optionally send email.

        Args:
            context: The workflow context.

        Returns:
            AgentResult with the generated report.
        """
        # Generate report using parent class
        result = super().run(context)

        # Send email if enabled and report was generated successfully
        if self.send_email and result.success and result.output:
            try:
                from services.email_service import send_market_report
                send_market_report(result.output, test_mode=self.test_mode)
            except Exception as e:
                print(f"⚠️ Failed to send email: {e}")

        return result
