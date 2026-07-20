from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ai-code-guard.yml"


def test_ci_actions_use_node24_runtime_majors():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert workflow.count("actions/checkout@v6") == 2
    assert workflow.count("actions/setup-python@v6") == 1
    assert "actions/checkout@v4" not in workflow
    assert "actions/setup-python@v5" not in workflow


def test_ci_workflow_declares_read_only_repository_permission():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read\n" in workflow
