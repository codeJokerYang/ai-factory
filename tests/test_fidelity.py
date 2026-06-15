"""保真度：Builder 依赖白名单过滤 + scaffold 合并 extra deps + Supabase env 示例。"""
import json

from orchestration import config
from orchestration.agents.builder import Builder
from orchestration.llm import MockLLM
from orchestration.scaffold import scaffold_files, write_app
from orchestration.schemas import Architecture, GeneratedFile, ProductSpec
from orchestration.state import ProjectPhase, ProjectState


def _state():
    return ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(project_name="p", one_liner="o", target_users="u"),
        architecture=Architecture(),
    )


def test_builder_keeps_allowed_deps_drops_others():
    out = (
        '{"files":[{"path":"app/page.tsx","content":"x"}],'
        '"dependencies":{"pdfjs-dist":"^9.9.9","evil-pkg":"1.0.0"}}'
    )
    st = _state()
    Builder(MockLLM(responses={"[agent:builder]": out})).run(st)
    assert st.phase != ProjectPhase.FAILED
    # 白名单内：保留，且用固定版本（忽略 LLM 给的 ^9.9.9）
    assert st.extra_dependencies.get("pdfjs-dist") == config.ALLOWED_EXTRA_DEPS["pdfjs-dist"]
    # 白名单外：丢弃 + 警告
    assert "evil-pkg" not in st.extra_dependencies
    assert any("evil-pkg" in w for w in st.warnings)


def test_builder_no_deps_ok():
    out = '{"files":[{"path":"app/page.tsx","content":"x"}]}'
    st = _state()
    Builder(MockLLM(responses={"[agent:builder]": out})).run(st)
    assert st.extra_dependencies == {}
    assert st.phase != ProjectPhase.FAILED


def test_scaffold_merges_extra_deps():
    files = scaffold_files("demo", {"pdfjs-dist": "4.7.76"})
    pkg = json.loads(files["package.json"])
    assert pkg["dependencies"]["pdfjs-dist"] == "4.7.76"
    assert pkg["dependencies"]["next"]  # 原有依赖保留


def test_scaffold_supabase_env_example_conditional():
    assert ".env.local.example" in scaffold_files("demo", {"@supabase/supabase-js": "2.45.0"})
    assert ".env.local.example" not in scaffold_files("demo", {})


def test_write_app_with_extra_deps(tmp_path):
    write_app(
        tmp_path,
        "demo",
        [GeneratedFile(path="app/page.tsx", content="x")],
        {"pdfjs-dist": "4.7.76"},
    )
    pkg = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
    assert pkg["dependencies"]["pdfjs-dist"] == "4.7.76"
