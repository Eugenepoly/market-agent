"""State management for workflows."""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentResult":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class ApprovalRequest:
    """Request for human approval."""

    agent_name: str
    content: Any
    content_type: str  # e.g., "tweet_draft", "analysis"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    message: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ApprovalRequest":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class WorkflowContext:
    """Context for a workflow execution."""

    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_name: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_agent: Optional[str] = None
    data: dict = field(default_factory=dict)
    agent_results: list = field(default_factory=list)
    pending_approval: Optional[ApprovalRequest] = None
    error: Optional[str] = None

    def add_result(self, result: AgentResult) -> None:
        """Add an agent result to the context."""
        self.agent_results.append(result.to_dict())
        if result.output is not None:
            self.data[result.agent_name] = result.output
        self.updated_at = datetime.utcnow().isoformat()

    def set_pending_approval(self, request: ApprovalRequest) -> None:
        """Set a pending approval request."""
        self.pending_approval = request
        self.status = WorkflowStatus.WAITING_APPROVAL
        self.updated_at = datetime.utcnow().isoformat()

    def clear_approval(self) -> None:
        """Clear the pending approval."""
        self.pending_approval = None
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value if isinstance(self.status, WorkflowStatus) else self.status,
            "current_agent": self.current_agent,
            "data": self.data,
            "agent_results": self.agent_results,
            "pending_approval": self.pending_approval.to_dict() if self.pending_approval else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowContext":
        """Create from dictionary."""
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = WorkflowStatus(status)

        pending_approval = data.get("pending_approval")
        if pending_approval:
            pending_approval = ApprovalRequest.from_dict(pending_approval)

        return cls(
            workflow_id=data.get("workflow_id", str(uuid.uuid4())),
            workflow_name=data.get("workflow_name", ""),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
            status=status,
            current_agent=data.get("current_agent"),
            data=data.get("data", {}),
            agent_results=data.get("agent_results", []),
            pending_approval=pending_approval,
            error=data.get("error"),
        )

    def save(self, state_dir: str) -> None:
        """Save workflow state to disk."""
        os.makedirs(state_dir, exist_ok=True)
        filepath = os.path.join(state_dir, f"{self.workflow_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, workflow_id: str, state_dir: str) -> Optional["WorkflowContext"]:
        """Load workflow state from disk."""
        filepath = os.path.join(state_dir, f"{workflow_id}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
