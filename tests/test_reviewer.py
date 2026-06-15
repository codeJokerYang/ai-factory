"""Reviewer agent（Gate 2 前代码审查，advisory）+ Gate 2 摘要含审查结果。"""
from orchestration.agents.reviewer import Reviewer
from orchestration.gate2 import summarize_build
from orchestration.llm import MockLLM
from orchestration.schemas import (
    Architecture,
    CodeReview,
    GeneratedFile,
    ProductSpec,
    ReviewIssue,
)
from orchestration.state import ProjectPhase, ProjectState


def _state_with_files():
    return ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(project_name="p", one_liner="o", target_users="u"),
        architecture=Architecture(),
        generated_files=[
            GeneratedFile(path="app/page.tsx", content="export default function P(){return null}")
        ],
    )


def test_reviewer_pass():
    review = '{"passed":true,"summary":"looks good","issues":[]}'
    st = _state_with_files()
    Reviewer(MockLLM(responses={"[agent:reviewer]": review})).run(st)
    assert st.code_review is not None and st.code_review.passed is True
    assert st.code_review.summary == "looks good"
    assert st.phase != ProjectPhase.FAILED


def test_reviewer_flags_high_issue_as_warning():
    review = (
        '{"passed":false,"summary":"issues","issues":'
        '[{"severity":"high","file":"app/page.tsx","message":"hardcoded api key"}]}'
    )
    st = _state_with_files()
    Reviewer(MockLLM(responses={"[agent:reviewer]": review})).run(st)
    assert st.code_review.passed is False
    assert any("reviewer[high]" in w for w in st.warnings)
    assert st.phase != ProjectPhase.FAILED  # advisory：不阻塞


def test_reviewer_no_files_skips_without_llm():
    llm = MockLLM()
    st = ProjectState(project_id="t", idea="i")
    Reviewer(llm).run(st)
    assert st.code_review is None
    assert llm.calls == []
    assert st.phase != ProjectPhase.FAILED


def test_reviewer_bad_json_is_advisory():
    st = _state_with_files()
    Reviewer(MockLLM(responses={"[agent:reviewer]": "not json"})).run(st)
    assert st.code_review is None
    assert st.phase != ProjectPhase.FAILED
    assert any("reviewer" in w for w in st.warnings)


def test_reviewer_skips_when_failed():
    llm = MockLLM()
    st = _state_with_files()
    st.phase = ProjectPhase.FAILED
    Reviewer(llm).run(st)
    assert llm.calls == []


def test_gate2_summary_includes_review():
    st = _state_with_files()
    st.code_review = CodeReview(
        passed=False,
        summary="needs work",
        issues=[ReviewIssue(severity="high", file="app/page.tsx", message="bug")],
    )
    out = summarize_build(st)
    assert "Reviewer" in out and "high" in out and "bug" in out
