"""Decomposer 粒度约束：check_granularity 软校验 + Decomposer 越界给非阻塞 warning。"""
from orchestration.agents.decomposer import Decomposer
from orchestration.dag_validator import check_granularity
from orchestration.llm import MockLLM
from orchestration.schemas import Architecture, Dag, DagNode, ProductSpec
from orchestration.state import ProjectPhase, ProjectState


def _dag(n):
    return Dag(project="p", nodes=[DagNode(id=f"{i:03d}") for i in range(n)])


def test_granularity_in_range():
    assert check_granularity(_dag(15)) is None  # 默认 12–18


def test_granularity_too_few():
    msg = check_granularity(_dag(5))
    assert msg is not None and "下限" in msg


def test_granularity_too_many():
    msg = check_granularity(_dag(30))
    assert msg is not None and "上限" in msg


def test_granularity_custom_bounds():
    assert check_granularity(_dag(5), lo=1, hi=10) is None


def test_decomposer_warns_but_succeeds_on_out_of_range():
    nodes = ",".join(f'{{"id":"{i:03d}","depends":[]}}' for i in range(3))
    dag_json = f'{{"project":"p","nodes":[{nodes}]}}'
    llm = MockLLM(responses={"[agent:decomposer]": dag_json})
    st = ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(project_name="p", one_liner="o", target_users="u"),
        architecture=Architecture(),
    )
    out = Decomposer(llm).run(st)
    # 粒度越界是非阻塞的：DAG 仍合法、不 FAILED，只是带 warning
    assert out.phase != ProjectPhase.FAILED
    assert out.dag is not None and len(out.dag.nodes) == 3
    assert any("下限" in w for w in out.warnings)
