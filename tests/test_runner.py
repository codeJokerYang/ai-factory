from orchestration.runner import SequentialRunner
from orchestration.state import ProjectPhase, ProjectState


def _state():
    return ProjectState(project_id="t", idea="i")


def test_runner_threads_state_in_order():
    order = []

    def step_a(s):
        order.append("a")
        s.errors.append("a")
        return s

    def step_b(s):
        order.append("b")
        s.errors.append("b")
        return s

    out = SequentialRunner([step_a, step_b]).run(_state())

    assert order == ["a", "b"]
    assert out.errors == ["a", "b"]


def test_runner_stops_on_terminal_phase():
    def fail(s):
        s.phase = ProjectPhase.FAILED
        return s

    def should_not_run(s):
        s.errors.append("ran")
        return s

    out = SequentialRunner([fail, should_not_run]).run(_state())

    assert out.phase == ProjectPhase.FAILED
    assert "ran" not in out.errors
