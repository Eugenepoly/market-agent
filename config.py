"""Configuration management for Market Agent."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration."""

    # API Keys
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))

    # Storage settings
    gcs_bucket: str = field(default_factory=lambda: os.environ.get("GCS_BUCKET", "market-reports-bucket"))
    local_output_dir: str = field(default_factory=lambda: os.environ.get("LOCAL_OUTPUT_DIR", "./reports"))

    # Runtime mode
    run_local: bool = field(default_factory=lambda: os.environ.get("RUN_LOCAL", "false").lower() == "true")

    # Workflow storage
    workflow_state_dir: str = field(default_factory=lambda: os.environ.get("WORKFLOW_STATE_DIR", "./.workflow_state"))

    # Model settings
    model_name: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"))

    # Approval settings
    pending_approval_dir: str = field(default_factory=lambda: os.environ.get("PENDING_APPROVAL_DIR", "./pending_social_content"))
    approved_drafts_dir: str = field(default_factory=lambda: os.environ.get("APPROVED_DRAFTS_DIR", "./approved_social_content"))

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

    @property
    def is_local_mode(self) -> bool:
        """Check if running in local mode."""
        return self.run_local


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
