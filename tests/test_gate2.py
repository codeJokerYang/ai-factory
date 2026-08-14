from orchestration.gate2 import make_gate_2, summarize_build
from orchestration.schemas import GeneratedFile, ProductSpec, UIQualityFinding, UIQualityReport
from orchestration.state import ProjectPhase, ProjectState


def _state():
    return ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(project_name="demo", one_liner="o", target_users="u"),
        generated_files=[GeneratedFile(path="app/page.tsx", content="a\nb\nc")],
        build_passed=True,
        preview_url="http://localhost:3000",
    )


def test_summarize_build():
    state = _state()
    state.ui_quality = UIQualityReport(
        passed=False,
        findings=[
            UIQualityFinding(
                severity="medium",
                code="missing-responsive",
                file="app/page.tsx",
                message="缺少响应式断点",
            )
        ],
    )
    out = summarize_build(state)
    assert "demo" in out
    assert "app/page.tsx" in out
    assert "通过" in out  # build_passed True
    assert "http://localhost:3000" in out
    assert "UI Quality" in out
    assert "missing-responsive" in out


def test_gate_2_approve():
    out = make_gate_2(approver=lambda s: (True, None))(_state())
    assert out.phase == ProjectPhase.GATE_2_APPROVED
    assert out.gate_2_approved is True


def test_gate_2_reject():
    out = make_gate_2(approver=lambda s: (False, "界面丑"))(_state())
    assert out.phase == ProjectPhase.GATE_2_REJECTED
    assert out.gate_2_approved is False
    assert out.gate_2_feedback == "界面丑"


def test_gate_2_skips_when_failed():
    st = _state()
    st.phase = ProjectPhase.FAILED
    out = make_gate_2(approver=lambda s: (True, None))(st)
    assert out.phase == ProjectPhase.FAILED
    assert out.gate_2_approved is False
