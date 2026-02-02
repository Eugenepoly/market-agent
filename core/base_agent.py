"""Base agent class for all agents."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from google import genai
from google.genai import types

from config import get_config
from core.state import WorkflowContext, AgentResult


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    name: str = "base_agent"
    requires_approval: bool = False

    def __init__(self):
        """Initialize the agent."""
        self.config = get_config()
        self.client = genai.Client(api_key=self.config.gemini_api_key)

    @abstractmethod
    def get_prompt(self, context: WorkflowContext) -> str:
        """Generate the prompt for this agent.

        Args:
            context: The workflow context containing data from previous agents.

        Returns:
            The prompt string to send to the model.
        """
        pass

    def get_tools(self) -> Optional[list]:
        """Get the tools available to this agent.

        Override this method to provide custom tools.

        Returns:
            List of tools or None if no tools are needed.
        """
        return [types.Tool(google_search=types.GoogleSearch())]

    def run(self, context: WorkflowContext) -> AgentResult:
        """Execute the agent.

        Args:
            context: The workflow context.

        Returns:
            AgentResult containing the output or error.
        """
        try:
            prompt = self.get_prompt(context)
            config_kwargs = {}
            tools = self.get_tools()
            if tools:
                config_kwargs["tools"] = tools

            response = self.client.models.generate_content(
                model=self.config.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
            )

            output = self.process_response(response.text, context)

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    def process_response(self, response_text: str, context: WorkflowContext) -> Any:
        """Process the model response.

        Override this method to customize response processing.

        Args:
            response_text: The raw response from the model.
            context: The workflow context.

        Returns:
            The processed output to store in context.
        """
        return response_text
