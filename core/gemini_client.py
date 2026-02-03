"""Shared Gemini client with rate limiting and retry logic."""

from typing import Optional, List
from google import genai
from google.genai import types

from config import get_config
from core.rate_limiter import retry_with_backoff


class GeminiClient:
    """Shared Gemini client with built-in retry logic."""

    _instance: Optional["GeminiClient"] = None

    def __new__(cls):
        """Singleton pattern to share client across modules."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the client."""
        if self._initialized:
            return
        self.config = get_config()
        self.client = genai.Client(api_key=self.config.gemini_api_key)
        self._initialized = True

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def generate(
        self,
        prompt: str,
        use_search: bool = True,
        tools: Optional[List] = None,
    ) -> str:
        """Generate content with retry logic.

        Args:
            prompt: The prompt to send.
            use_search: Whether to enable Google Search tool.
            tools: Custom tools list (overrides use_search if provided).

        Returns:
            Generated text response.
        """
        config_kwargs = {}

        if tools is not None:
            config_kwargs["tools"] = tools
        elif use_search:
            config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]

        response = self.client.models.generate_content(
            model=self.config.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None,
        )

        return response.text

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def generate_with_config(
        self,
        prompt: str,
        config: types.GenerateContentConfig,
    ) -> str:
        """Generate content with custom config.

        Args:
            prompt: The prompt to send.
            config: Custom generation config.

        Returns:
            Generated text response.
        """
        response = self.client.models.generate_content(
            model=self.config.model_name,
            contents=prompt,
            config=config,
        )
        return response.text


def get_gemini_client() -> GeminiClient:
    """Get the shared Gemini client instance."""
    return GeminiClient()
