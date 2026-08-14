from orchestration import config
from orchestration.io_writers import write_outputs
from orchestration.schemas import Architecture, Dag, ProductSpec
from orchestration.state import ProjectState


def test_write_outputs_sanitizes_untrusted_project_name(monkeypatch, tmp_path):
    specs = tmp_path / "wiki" / "specs"
    decisions = tmp_path / "wiki" / "decisions"
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "WIKI_SPECS_DIR", specs)
    monkeypatch.setattr(config, "WIKI_DECISIONS_DIR", decisions)
    monkeypatch.setattr(config, "TASKS_JSON", tmp_path / "tasks.json")
    state = ProjectState(
        project_id="safe-id",
        idea="test",
        product_spec=ProductSpec(
            project_name="../../outside",
            one_liner="test",
            target_users="testers",
        ),
        architecture=Architecture(),
        dag=Dag(project="outside"),
    )

    paths = write_outputs(state)

    assert paths["spec"].parent == specs
    assert paths["architecture"].parent == decisions
    assert paths["spec"].name == "outside.md"
    assert all(path.exists() for path in paths.values())
