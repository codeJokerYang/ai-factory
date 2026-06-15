"""Stateless agent base class.

run(state) -> state。Agent 不持有跨调用状态，一切经 ProjectState 流动。
LLM client 由外部注入，便于用 MockLLM 测试。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..llm import LLMClient
from ..state import ProjectState


class Agent(ABC):
    name: str
    model: str

    def __init__(self, llm: LLMClient):
        self.llm = llm

    @abstractmethod
    def run(self, state: ProjectState) -> ProjectState: ...
