import json

from orchestration.agents.builder import Builder
from orchestration.llm import MockLLM
from orchestration.prompts.builder import SYSTEM as BUILDER_SYSTEM
from orchestration.prompts.reviewer import SYSTEM as REVIEWER_SYSTEM
from orchestration.scaffold import scaffold_files
from orchestration.schemas import Architecture, GeneratedFile, ProductSpec
from orchestration.state import ProjectPhase, ProjectState
from orchestration.ui_quality import audit_ui_quality

POLISHED_PAGE = """'use client';

export default function Page() {
  return (
    <main className="ui-shell">
      <section className="grid gap-6 md:grid-cols-2">
        <div>
          <p className="ui-kicker">Workspace</p>
          <h1 className="ui-title">清晰完成今天的工作</h1>
        </div>
        <form className="ui-panel p-6">
          <label htmlFor="task">任务名称</label>
          <input id="task" className="ui-field" />
          <button className="ui-button-primary" type="submit">添加任务</button>
        </form>
      </section>
    </main>
  );
}
"""


def _state():
    return ProjectState(
        project_id="t",
        idea="做一个任务工作台",
        product_spec=ProductSpec(
            project_name="focus-workspace",
            one_liner="帮助个人聚焦当天最重要的任务",
            target_users="独立工作者",
        ),
        architecture=Architecture(stack={"frontend": "Next.js"}, deploy_target="Vercel"),
    )


def test_scaffold_provides_visual_tokens_primitives_and_accessible_layout():
    files = scaffold_files("focus-workspace")

    assert "ui-canvas" in files["tailwind.config.ts"]
    assert "boxShadow" in files["tailwind.config.ts"]
    assert ".ui-shell" in files["app/globals.css"]
    assert ".ui-button-primary" in files["app/globals.css"]
    assert "prefers-reduced-motion" in files["app/globals.css"]
    assert 'lang="zh-CN"' in files["app/layout.tsx"]
    assert "export const viewport" in files["app/layout.tsx"]


def test_builder_and_reviewer_prompts_share_ui_quality_contract():
    assert "UI 质量契约" in BUILDER_SYSTEM
    assert "移动优先" in BUILDER_SYSTEM
    assert "ui-button-primary" in BUILDER_SYSTEM
    assert "无障碍" in REVIEWER_SYSTEM
    assert "响应式" in REVIEWER_SYSTEM


def test_ui_audit_accepts_semantic_responsive_accessible_page():
    report = audit_ui_quality([GeneratedFile(path="app/page.tsx", content=POLISHED_PAGE)])

    assert report.passed is True
    assert report.findings == []


def test_ui_audit_reports_visual_and_accessibility_regressions():
    weak_page = """'use client';
export default function Page() {
  return <div onClick={() => null}><img src="/hero.png" /><input className="outline-none" /></div>;
}
"""

    report = audit_ui_quality([GeneratedFile(path="app/page.tsx", content=weak_page)])
    codes = {finding.code for finding in report.findings}

    assert report.passed is False
    assert {"missing-main", "missing-h1", "missing-responsive", "clickable-static"} <= codes
    assert {"image-alt", "form-label", "focus-visible"} <= codes


def test_ui_audit_handles_none_and_missing_page_without_throwing():
    for files in (None, [], [GeneratedFile(path="components/Card.tsx", content="export const Card = () => null")]):
        report = audit_ui_quality(files)
        assert report.passed is False
        assert [finding.code for finding in report.findings] == ["missing-page"]


def test_builder_records_ui_report_without_extra_llm_call():
    payload = json.dumps({"files": [{"path": "app/page.tsx", "content": POLISHED_PAGE}]})
    llm = MockLLM(responses={"[agent:builder]": payload})

    state = Builder(llm).run(_state())

    assert state.phase == ProjectPhase.BUILD_DONE
    assert len(llm.calls) == 1
    assert state.ui_quality is not None
    assert state.ui_quality.passed is True


def test_builder_repair_refreshes_stale_ui_findings():
    weak_payload = json.dumps(
        {"files": [{"path": "app/page.tsx", "content": "export default function Page(){return <div />;}"}]}
    )
    polished_payload = json.dumps(
        {"files": [{"path": "app/page.tsx", "content": POLISHED_PAGE}]}
    )
    llm = MockLLM(responses={"[agent:builder]": weak_payload})
    builder = Builder(llm)
    state = builder.run(_state())
    assert state.ui_quality is not None and state.ui_quality.passed is False
    assert any(warning.startswith("ui-quality[") for warning in state.warnings)

    llm.responses["[agent:builder]"] = polished_payload
    builder.repair(state, "type error")

    assert state.ui_quality is not None and state.ui_quality.passed is True
    assert not any(warning.startswith("ui-quality[") for warning in state.warnings)
