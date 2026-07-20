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


def test_builder_injects_matching_l2_template_into_prompt():
    llm = MockLLM(responses={"[agent:builder]": BUILDER_JSON})
    state = _state()
    state.product_spec.core_features = ["用户登录", "数据看板"]

    st = Builder(llm).run(state)

    assert st.phase == ProjectPhase.BUILD_DONE
    assert len(llm.calls) == 1
    prompt = llm.calls[0]["prompt"]
    assert "L2 方案模板" in prompt
    assert "### auth: 认证与会话" in prompt
    assert "### dashboard: Dashboard 与分析" in prompt
    assert st.cache_lookup is not None
    assert st.cache_lookup.source == "l2"
    assert st.cache_lookup.match_ids == ["auth", "dashboard"]
    assert st.cache_lookup.estimated_reused_tokens > 0


def test_builder_keeps_original_prompt_path_when_no_template_matches():
    llm = MockLLM(responses={"[agent:builder]": BUILDER_JSON})

    st = Builder(llm).run(_state())

    assert st.phase == ProjectPhase.BUILD_DONE
    assert "L2 方案模板" not in llm.calls[0]["prompt"]
    assert st.cache_lookup is not None
    assert st.cache_lookup.source == "miss"
    assert st.cache_lookup.estimated_reused_tokens == 0


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
