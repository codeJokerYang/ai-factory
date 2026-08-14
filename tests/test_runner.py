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


def test_runner_converts_step_exception_to_failed_state():
    def unavailable(_state):
        raise TimeoutError("provider timed out")

    out = SequentialRunner([unavailable]).run(_state())

    assert out.phase == ProjectPhase.FAILED
    assert any("TimeoutError" in error and "provider timed out" in error for error in out.errors)


def test_runner_rejects_invalid_step_result():
    out = SequentialRunner([lambda _state: None]).run(_state())

    assert out.phase == ProjectPhase.FAILED
    assert any("expected ProjectState" in error for error in out.errors)


def test_runner_stops_after_gate_2_rejection():
    ran = []

    def reject(state):
        state.phase = ProjectPhase.GATE_2_REJECTED
        return state

    out = SequentialRunner([reject, lambda state: ran.append(True) or state]).run(_state())

    assert out.phase == ProjectPhase.GATE_2_REJECTED
    assert ran == []
