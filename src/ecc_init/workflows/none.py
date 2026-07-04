from __future__ import annotations

from .base import WorkflowResult


class NoneWorkflowAdapter:
    workflow_id = "none"

    def inspect(self) -> WorkflowResult:
        return WorkflowResult(self.workflow_id, "ok", warnings=["No workflow adapter is enabled."])
