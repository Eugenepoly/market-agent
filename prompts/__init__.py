"""Prompt templates for agents."""

from .report_prompt import get_report_prompt
from .deep_analysis_prompt import get_deep_analysis_prompt
from .social_prompt import get_social_prompt

__all__ = [
    "get_report_prompt",
    "get_deep_analysis_prompt",
    "get_social_prompt",
]
