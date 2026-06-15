"""Reviewer 自愈闭环：review_and_revise（注入假 reviewer/builder）+ Builder.revise（MockLLM）。"""
from orchestration.agents.builder import Builder
from orchestration.build_cli import _format_review, review_and_revise
from orchestration.llm import MockLLM
from orchestration.schemas import CodeReview, GeneratedFile, ReviewIssue
from orchestration.state import ProjectPhase, ProjectState


class _FakeReviewer:
    def __init__(self, results):
        self.results = results
        self.calls = 0

    def run(self, state):
        state.code_review = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return state


class _FakeBuilder:
    def __init__(self):
        self.revisions = 0

    def revise(self, state, feedback):
        self.revisions += 1
        state.generated_files = [GeneratedFile(path="app/page.tsx", content="revised")]
        return state


def _state():
    return ProjectState(
        project_id="t",
        idea="i",
        generated_files=[GeneratedFile(path="app/page.tsx", content="orig")],
    )


def _review(passed, sev="high"):
    issues = [] if passed else [ReviewIssue(severity=sev, file="f", message="m")]
    return CodeReview(passed=passed, summary="s", issues=issues)


def test_review_passes_first_no_revise():
    rv, b, st = _FakeReviewer([_review(True)]), _FakeBuilder(), _state()
    review_and_revise(st, "x", "p", b, rv, write_fn=lambda *a: None, max_rounds=1)
    assert st.code_review.passed is True
    assert b.revisions == 0 and st.review_rounds == 0


def test_review_fail_then_revise_pass():
    rv, b, st = _FakeReviewer([_review(False), _review(True)]), _FakeBuilder(), _state()
    review_and_revise(st, "x", "p", b, rv, write_fn=lambda *a: None, max_rounds=1)
    assert st.code_review.passed is True
    assert b.revisions == 1 and st.review_rounds == 1 and rv.calls == 2


def test_review_exhausts_rounds_still_failing():
    rv, b, st = _FakeReviewer([_review(False), _review(False)]), _FakeBuilder(), _state()
    review_and_revise(st, "x", "p", b, rv, write_fn=lambda *a: None, max_rounds=1)
    assert st.code_review.passed is False  # 升级 Gate 2
    assert b.revisions == 1 and st.review_rounds == 1


def test_format_review():
    txt = _format_review(_review(False))
    assert "high" in txt and "m" in txt


def test_builder_revise_updates_files():
    fixed = '{"files":[{"path":"app/page.tsx","content":"export default function P(){return null}"}]}'
    st = _state()
    Builder(MockLLM(responses={"[agent:builder]": fixed})).revise(st, "fix the bug")
    assert st.generated_files[0].content.startswith("export default")
    assert st.phase != ProjectPhase.FAILED


def test_builder_revise_bad_json_fails():
    st = _state()
    Builder(MockLLM(responses={"[agent:builder]": "not json"})).revise(st, "fix")
    assert st.phase == ProjectPhase.FAILED
    assert any("revise" in e for e in st.errors)
