from orchestration.schemas import Architecture, Dag, DagNode, ProductSpec, Risk, UserStory
from orchestration.state import ProjectPhase, ProjectState


def test_project_state_roundtrip():
    state = ProjectState(
        project_id="abc123",
        idea="test idea",
        product_spec=ProductSpec(
            project_name="demo",
            one_liner="x",
            target_users="y",
            core_features=["a"],
            user_stories=[UserStory(as_a="u", i_want="w", so_that="s")],
        ),
        architecture=Architecture(
            stack={"frontend": "Next.js"}, data_model="m", deploy_target="Vercel"
        ),
        dag=Dag(project="demo", nodes=[DagNode(id="001", risk=Risk.high)]),
    )

    restored = ProjectState.model_validate_json(state.model_dump_json())

    assert restored == state
    assert restored.dag.nodes[0].risk == Risk.high
    assert restored.phase == ProjectPhase.INIT
