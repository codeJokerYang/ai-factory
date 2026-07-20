"""LangGraphRunner —— 验证"替换点"：与 SequentialRunner 等价 + 条件路由短路 + make_runner 选择。"""
import pytest

pytest.importorskip("langgraph")

from orchestration.lang_runner import LangGraphRunner  # noqa: E402
from orchestration.runner import SequentialRunner, make_runner  # noqa: E402
from orchestration.state import ProjectPhase, ProjectState  # noqa: E402


def _steps(order):
    def a(s):
        order.append("a")
        s.errors.append("a")
        return s

    def b(s):
        order.append("b")
        s.errors.append("b")
        return s

    return [a, b]


def _state():
    return ProjectState(project_id="t", idea="i")


def test_langgraph_equivalent_to_sequential():
    o_seq, o_lg = [], []
    seq = SequentialRunner(_steps(o_seq)).run(_state())
    lg = LangGraphRunner(_steps(o_lg)).run(_state())
    assert o_seq == o_lg == ["a", "b"]
    assert lg.errors == seq.errors == ["a", "b"]
    assert isinstance(lg, ProjectState)


def test_langgraph_short_circuits_on_terminal():
    ran = []

    def fail(s):
        s.phase = ProjectPhase.FAILED
        return s

    def should_not_run(s):
        ran.append("x")
        return s

    out = LangGraphRunner([fail, should_not_run]).run(_state())
    assert out.phase == ProjectPhase.FAILED
    assert ran == []  # 条件路由短路，下游不执行


def test_make_runner_selects_engine():
    assert isinstance(make_runner([], runner="sequential"), SequentialRunner)
    assert isinstance(make_runner([], runner="langgraph"), LangGraphRunner)
    assert isinstance(make_runner([]), SequentialRunner)  # 默认


def test_langgraph_converts_step_exception_to_failed_state():
    def unavailable(_state):
        raise ConnectionError("gateway unavailable")

    out = LangGraphRunner([unavailable]).run(_state())

    assert out.phase == ProjectPhase.FAILED
    assert any("ConnectionError" in error for error in out.errors)


def test_langgraph_reuses_compiled_graph():
    runner = LangGraphRunner(_steps([]))
    first = runner._compile()
    second = runner._compile()
    assert first is second
