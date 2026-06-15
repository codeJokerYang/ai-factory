"""Agent 独立退化路径：坏 JSON、缺前置产物、非法 DAG。"""
import json

from orchestration.agents.architect import Architect
from orchestration.agents.decomposer import Decomposer
from orchestration.agents.planner import Planner
from orchestration.llm import MockLLM
from orchestration.schemas import Architecture, ProductSpec
from orchestration.state import ProjectPhase, ProjectState


def test_planner_bad_json_fails():
    llm = MockLLM(responses={"[agent:planner]": "这不是 JSON"})
    st = Planner(llm).run(ProjectState(project_id="t", idea="i"))
    assert st.phase == ProjectPhase.FAILED
    assert any("planner" in e for e in st.errors)


def test_architect_missing_spec_fails_without_llm_call():
    llm = MockLLM(responses={"[agent:architect]": "{}"})
    st = Architect(llm).run(ProjectState(project_id="t", idea="i"))  # 无 product_spec
    assert st.phase == ProjectPhase.FAILED
    assert any("architect" in e for e in st.errors)
    assert len(llm.calls) == 0  # 缺前置产物，不应浪费一次 LLM 调用


def test_decomposer_invalid_dag_fails():
    cyclic = json.dumps(
        {"project": "p", "nodes": [
            {"id": "001", "depends": ["002"]},
            {"id": "002", "depends": ["001"]},
        ]}
    )
    llm = MockLLM(responses={"[agent:decomposer]": cyclic})
    st = ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(project_name="p", one_liner="o", target_users="u"),
        architecture=Architecture(stack={}, deploy_target="V"),
    )
    st = Decomposer(llm).run(st)
    assert st.phase == ProjectPhase.FAILED
    assert any("DAG" in e or "decomposer" in e for e in st.errors)


def test_failed_state_short_circuits_downstream():
    # 上游已 FAILED 时，下游 agent 应原样返回、不调用 LLM
    llm = MockLLM(responses={"[agent:architect]": "{}"})
    st = ProjectState(project_id="t", idea="i", phase=ProjectPhase.FAILED)
    out = Architect(llm).run(st)
    assert out.phase == ProjectPhase.FAILED
    assert len(llm.calls) == 0
