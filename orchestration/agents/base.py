"""Stateless agent base class.

run(state) -> state。Agent 不持有跨调用状态，一切经 ProjectState 流动。
LLM client 由外部注入，便于用 MockLLM 测试。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..llm import LLMClient
from ..state import ProjectState
from ..instructions import with_instructions


class Agent(ABC):
    name: str
    model: str

    def __init__(self, llm: LLMClient):
        import os
        self.llm = llm
        self.model = os.environ.get("FACTORY_MODEL") or os.environ.get(
            f"FACTORY_{self.name.upper()}_MODEL", self.model
        )

    def complete(self, state, **kwargs):
        kwargs["prompt"] = with_instructions(state, kwargs["prompt"])
        return self.llm.complete(**kwargs)

    @abstractmethod
    def run(self, state: ProjectState) -> ProjectState: ...
