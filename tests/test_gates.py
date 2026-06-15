from orchestration.gates import make_gate_1, summarize
from orchestration.schemas import Architecture, DagNode, Dag, ProductSpec, Risk
from orchestration.state import ProjectPhase, ProjectState


def _state_with_dag(nodes):
    return ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(
            project_name="demo",
            one_liner="ol",
            target_users="u",
            mvp_in_scope=["a"],
            mvp_out_of_scope=["b"],
        ),
        architecture=Architecture(
            stack={"frontend": "Next.js", "database": "PG", "deploy": "Vercel"},
            deploy_target="Vercel",
        ),
        dag=Dag(project="demo", nodes=nodes),
    )


def test_summarize_with_deps():
    st = _state_with_dag([DagNode(id="001"), DagNode(id="002", depends=["001"], risk=Risk.high)])
    out = summarize(st)
    assert "demo" in out
    assert "001" in out and "002" in out
    assert "<- 001" in out  # 依赖渲染
    assert "2 个节点" in out


def test_summarize_without_deps():
    st = _state_with_dag([DagNode(id="001")])
    out = summarize(st)
    assert "001" in out
    assert "<-" not in out  # 无依赖时不渲染箭头


def test_gate_1_approve():
    st = _state_with_dag([DagNode(id="001")])
    out = make_gate_1(approver=lambda s: (True, None))(st)
    assert out.phase == ProjectPhase.PLAN_APPROVED
    assert out.gate_1_approved is True


def test_gate_1_reject():
    st = _state_with_dag([DagNode(id="001")])
    out = make_gate_1(approver=lambda s: (False, "方向不对"))(st)
    assert out.phase == ProjectPhase.PLAN_REJECTED
    assert out.gate_1_approved is False
    assert out.gate_1_feedback == "方向不对"
