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
        from .. import config
        self.llm = llm
        self.model = config.get_model(self.name, self.model)

    def complete(self, state, **kwargs):
        kwargs["prompt"] = with_instructions(state, kwargs["prompt"])
        if state.delivery_mode:
            kwargs['system'] += '\n当前为真实交付模式：禁止使用 mock、内存模拟或假成功提示冒充业务能力。外部服务缺失时明确说明不可交付，不进行演示降级。'
        return self.llm.complete(**kwargs)

    @abstractmethod
    def run(self, state: ProjectState) -> ProjectState: ...
