import json

from orchestration.agents.builder import Builder
from orchestration.llm import MockLLM
from orchestration.scaffold import write_app
from orchestration.schemas import Architecture, GeneratedFile, ProductSpec
from orchestration.state import ProjectPhase, ProjectState

PAGE = "export default function Page() { return <main>hi</main>; }"
BUILDER_JSON = json.dumps({"files": [{"path": "app/page.tsx", "content": PAGE}]})


def _state():
    return ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(project_name="demo", one_liner="o", target_users="u"),
        architecture=Architecture(stack={"frontend": "Next.js"}, deploy_target="Vercel"),
    )


def test_builder_parses_files():
    llm = MockLLM(responses={"[agent:builder]": BUILDER_JSON})
    st = Builder(llm).run(_state())
    assert st.phase == ProjectPhase.BUILD_DONE
    assert [f.path for f in st.generated_files] == ["app/page.tsx"]


def test_builder_requires_page():
    llm = MockLLM(responses={"[agent:builder]": json.dumps({"files": [{"path": "app/x.tsx", "content": "x"}]})})
    st = Builder(llm).run(_state())
    assert st.phase == ProjectPhase.FAILED


def test_write_app_merges_scaffold_and_features(tmp_path):
    target = tmp_path / "app1"
    write_app(target, "demo", [GeneratedFile(path="app/page.tsx", content=PAGE)])

    assert (target / "package.json").exists()
    assert (target / "tailwind.config.ts").exists()
    assert (target / "app" / "layout.tsx").exists()
    assert (target / "app" / "page.tsx").read_text(encoding="utf-8") == PAGE
    # project name 注入 package.json
    assert '"name": "demo"' in (target / "package.json").read_text(encoding="utf-8")
