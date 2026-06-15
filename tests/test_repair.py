"""B3 自愈回路：build_and_verify（注入假 verifier）+ Builder.repair（MockLLM）。"""
from orchestration.agents.builder import Builder
from orchestration.build_cli import build_and_verify
from orchestration.llm import MockLLM
from orchestration.schemas import GeneratedFile
from orchestration.state import ProjectPhase, ProjectState
from orchestration.verify import VerifyResult


class _FakeBuilder:
    def __init__(self):
        self.calls = 0

    def repair(self, state, error_log):
        self.calls += 1
        state.generated_files = [GeneratedFile(path="app/page.tsx", content="fixed")]
        return state


def _state():
    return ProjectState(
        project_id="t",
        idea="i",
        generated_files=[GeneratedFile(path="app/page.tsx", content="broken")],
    )


def test_pass_first_no_repair():
    def vf(target, install=True):
        return VerifyResult(True, "ok", "")

    b = _FakeBuilder()
    st = _state()
    res = build_and_verify("x", "p", st, b, verify_fn=vf, write_fn=lambda *a: None)
    assert res.passed is True
    assert b.calls == 0
    assert st.repair_attempts == 0
    assert st.build_passed is True


def test_build_fail_then_repair_passes():
    seq = [VerifyResult(False, "build", "TypeError"), VerifyResult(True, "ok", "")]

    def vf(target, install=True):
        return seq.pop(0)

    b = _FakeBuilder()
    st = _state()
    res = build_and_verify("x", "p", st, b, verify_fn=vf, write_fn=lambda *a: None, max_repairs=1)
    assert res.passed is True
    assert b.calls == 1
    assert st.repair_attempts == 1
    assert st.build_passed is True


def test_build_fail_exhausts_repairs():
    def vf(target, install=True):
        return VerifyResult(False, "build", "still broken")

    b = _FakeBuilder()
    st = _state()
    res = build_and_verify("x", "p", st, b, verify_fn=vf, write_fn=lambda *a: None, max_repairs=1)
    assert res.passed is False
    assert b.calls == 1  # 只修一次
    assert st.repair_attempts == 1
    assert st.build_passed is False


def test_install_fail_no_repair():
    # install 失败是环境问题，不该触发代码自愈
    def vf(target, install=True):
        return VerifyResult(False, "install", "npm ERR network")

    b = _FakeBuilder()
    st = _state()
    res = build_and_verify("x", "p", st, b, verify_fn=vf, write_fn=lambda *a: None, max_repairs=1)
    assert res.passed is False
    assert b.calls == 0
    assert st.repair_attempts == 0


def test_builder_repair_updates_files():
    fixed = '{"files":[{"path":"app/page.tsx","content":"export default function P(){return null}"}]}'
    llm = MockLLM(responses={"[agent:builder]": fixed})
    st = _state()
    Builder(llm).repair(st, "some TS error")
    assert st.generated_files[0].content.startswith("export default")
    assert len(llm.calls) == 1
    assert st.phase != ProjectPhase.FAILED


def test_builder_repair_bad_json_fails():
    llm = MockLLM(responses={"[agent:builder]": "not json at all"})
    st = _state()
    Builder(llm).repair(st, "err")
    assert st.phase == ProjectPhase.FAILED
    assert any("repair" in e for e in st.errors)
