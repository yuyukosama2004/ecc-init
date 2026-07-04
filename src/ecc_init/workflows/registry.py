from __future__ import annotations

from ..errors import ConfigError
from .gsd import GsdWorkflowAdapter
from .none import NoneWorkflowAdapter


def get_workflow_adapter(workflow_id: str):
    if workflow_id == "gsd":
        return GsdWorkflowAdapter()
    if workflow_id == "none":
        return NoneWorkflowAdapter()
    raise ConfigError(f"unknown workflow adapter: {workflow_id}")
