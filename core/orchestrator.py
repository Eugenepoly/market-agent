"""Workflow orchestrator for managing agent execution."""

import os
from typing import Dict, Optional, Type, Callable

from config import get_config
from core.base_agent import BaseAgent
from core.state import WorkflowContext, WorkflowStatus, AgentResult, ApprovalRequest
from storage import Storage


class Orchestrator:
    """Orchestrates workflow execution and agent coordination."""

    def __init__(self):
        """Initialize the orchestrator."""
        self.config = get_config()
        self.storage = Storage()
        self._workflows: Dict[str, Callable[[], list]] = {}
        self._agents: Dict[str, Type[BaseAgent]] = {}

    def register_workflow(self, name: str, workflow_factory: Callable[[], list]) -> None:
        """Register a workflow.

        Args:
            name: The workflow name.
            workflow_factory: A callable that returns a list of agent instances.
        """
        self._workflows[name] = workflow_factory

    def register_agent(self, agent_class: Type[BaseAgent]) -> None:
        """Register an agent class.

        Args:
            agent_class: The agent class to register.
        """
        self._agents[agent_class.name] = agent_class

    def get_agent_class(self, name: str) -> Optional[Type[BaseAgent]]:
        """Get a registered agent class by name.

        Args:
            name: The agent name.

        Returns:
            The agent class or None if not found.
        """
        return self._agents.get(name)

    def run_workflow(
        self,
        workflow_name: str,
        skip_analysis: bool = False,
        analysis_topic: Optional[str] = None,
    ) -> WorkflowContext:
        """Run a workflow by name.

        Args:
            workflow_name: The name of the workflow to run.
            skip_analysis: Whether to skip the deep analysis step.
            analysis_topic: Optional topic for deep analysis.

        Returns:
            The workflow context after execution.

        Raises:
            ValueError: If workflow is not found.
        """
        if workflow_name not in self._workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        # Create new context
        context = WorkflowContext(workflow_name=workflow_name)
        context.status = WorkflowStatus.RUNNING

        # Get workflow agents
        agents = self._workflows[workflow_name]()

        # Filter agents if needed
        if skip_analysis:
            agents = [a for a in agents if a.name != "deep_analysis_agent"]

        # Set analysis topic if provided
        for agent in agents:
            if hasattr(agent, "topic") and analysis_topic:
                agent.topic = analysis_topic

        # Execute agents
        for agent in agents:
            context.current_agent = agent.name
            context.save(self.config.workflow_state_dir)

            # Run agent
            result = agent.run(context)
            context.add_result(result)

            if not result.success:
                context.status = WorkflowStatus.FAILED
                context.error = result.error
                context.save(self.config.workflow_state_dir)
                return context

            # Save intermediate results
            if agent.name == "report_agent":
                self.storage.save_report(result.output)
            elif agent.name == "deep_analysis_agent":
                analysis_content = result.output.get("analysis", str(result.output))
                self.storage.save_analysis(analysis_content)

            # Check if approval is needed
            if agent.requires_approval:
                draft_content = result.output.get("draft", str(result.output))
                self.storage.save_pending_draft(draft_content, context.workflow_id)

                context.set_pending_approval(ApprovalRequest(
                    agent_name=agent.name,
                    content=result.output,
                    content_type="tweet_draft",
                    message="Please review the tweet draft before publishing.",
                ))
                context.save(self.config.workflow_state_dir)
                return context

        # All done
        context.status = WorkflowStatus.COMPLETED
        context.current_agent = None
        context.save(self.config.workflow_state_dir)
        return context

    def run_single_agent(
        self,
        agent_name: str,
        context: Optional[WorkflowContext] = None,
        **agent_kwargs,
    ) -> WorkflowContext:
        """Run a single agent.

        Args:
            agent_name: The name of the agent to run.
            context: Optional existing context. Creates new if not provided.
            **agent_kwargs: Arguments to pass to agent constructor.

        Returns:
            The workflow context after execution.

        Raises:
            ValueError: If agent is not found.
        """
        agent_class = self._agents.get(agent_name)
        if agent_class is None:
            raise ValueError(f"Agent '{agent_name}' not found")

        if context is None:
            context = WorkflowContext(workflow_name=f"single_{agent_name}")

        context.status = WorkflowStatus.RUNNING
        context.current_agent = agent_name

        agent = agent_class(**agent_kwargs) if agent_kwargs else agent_class()
        result = agent.run(context)
        context.add_result(result)

        if result.success:
            context.status = WorkflowStatus.COMPLETED
        else:
            context.status = WorkflowStatus.FAILED
            context.error = result.error

        context.current_agent = None
        context.save(self.config.workflow_state_dir)
        return context

    def approve(self, workflow_id: str) -> WorkflowContext:
        """Approve a pending workflow.

        Args:
            workflow_id: The workflow ID.

        Returns:
            The updated workflow context.

        Raises:
            ValueError: If workflow not found or not waiting approval.
        """
        context = WorkflowContext.load(workflow_id, self.config.workflow_state_dir)
        if context is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        if context.status != WorkflowStatus.WAITING_APPROVAL:
            raise ValueError(f"Workflow is not waiting for approval (status: {context.status})")

        if context.pending_approval is None:
            raise ValueError("No pending approval found")

        # Get the draft content
        draft_content = self.storage.load_pending_draft(workflow_id)
        if draft_content:
            # Save to approved location
            self.storage.save_approved_draft(draft_content, workflow_id)
            # Clean up pending
            self.storage.delete_pending_draft(workflow_id)

        # Update context
        context.clear_approval()
        context.status = WorkflowStatus.COMPLETED
        context.save(self.config.workflow_state_dir)

        return context

    def reject(self, workflow_id: str, reason: Optional[str] = None) -> WorkflowContext:
        """Reject a pending workflow.

        Args:
            workflow_id: The workflow ID.
            reason: Optional rejection reason.

        Returns:
            The updated workflow context.

        Raises:
            ValueError: If workflow not found or not waiting approval.
        """
        context = WorkflowContext.load(workflow_id, self.config.workflow_state_dir)
        if context is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        if context.status != WorkflowStatus.WAITING_APPROVAL:
            raise ValueError(f"Workflow is not waiting for approval (status: {context.status})")

        # Clean up pending draft
        self.storage.delete_pending_draft(workflow_id)

        # Update context
        context.clear_approval()
        context.status = WorkflowStatus.REJECTED
        context.error = reason or "Rejected by user"
        context.save(self.config.workflow_state_dir)

        return context

    def get_status(self, workflow_id: str) -> Optional[WorkflowContext]:
        """Get workflow status.

        Args:
            workflow_id: The workflow ID.

        Returns:
            The workflow context or None if not found.
        """
        return WorkflowContext.load(workflow_id, self.config.workflow_state_dir)

    def list_workflows(self) -> list:
        """List all workflow states.

        Returns:
            List of workflow context dictionaries.
        """
        state_dir = self.config.workflow_state_dir
        if not os.path.exists(state_dir):
            return []

        workflows = []
        for filename in os.listdir(state_dir):
            if filename.endswith(".json"):
                workflow_id = filename[:-5]  # Remove .json
                context = WorkflowContext.load(workflow_id, state_dir)
                if context:
                    workflows.append(context.to_dict())

        return sorted(workflows, key=lambda x: x["created_at"], reverse=True)
