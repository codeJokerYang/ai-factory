"""用 MockLLM 跑通 Planner→Architect→Decomposer→Gate1 整条链（无需 API key）。"""
import json

from orchestration.agents.architect import Architect
from orchestration.agents.builder import Builder
from orchestration.agents.decomposer import Decomposer
from orchestration.agents.planner import Planner
from orchestration.config import FIXED_STACK
from orchestration.gates import make_gate_1
from orchestration.knowledge_cache import KnowledgeCase
from orchestration.llm import MockLLM
from orchestration.runner import SequentialRunner
from orchestration.state import ProjectPhase, ProjectState

PLANNER_JSON = json.dumps(
    {
        "project_name": "resume-optimizer",
        "one_liner": "帮大学生按 JD 优化简历",
        "target_users": "求职的大学生",
        "core_features": ["PDF 上传", "JD 匹配打分", "优化建议"],
        "mvp_in_scope": ["上传简历", "按 JD 打分"],
        "mvp_out_of_scope": ["简历代写", "内推"],
        "user_stories": [
            {"as_a": "学生", "i_want": "上传 PDF 简历", "so_that": "拿到分析"},
            {"as_a": "学生", "i_want": "粘贴 JD", "so_that": "得到匹配分"},
            {"as_a": "学生", "i_want": "看到改进建议", "so_that": "改简历"},
        ],
        "success_metrics": ["7 日留存 > 20%"],
        "risks": ["冷启动获客"],
    }
)

ARCHITECT_JSON = json.dumps(
    {
        "stack": FIXED_STACK,
        "data_model": "User(id, email); Resume(id, user_id, pdf_url); Score(id, resume_id, jd, value)",
        "api_design": [
            {"method": "POST", "path": "/api/v1/resumes", "purpose": "上传简历"},
            {"method": "POST", "path": "/api/v1/scores", "purpose": "按 JD 打分"},
        ],
        "deploy_target": "Vercel",
        "adrs": [
            {"title": "使用 Supabase Auth", "decision": "Magic link", "rationale": "v1 最省事"}
        ],
    }
)

DECOMPOSER_JSON = json.dumps(
    {
        "project": "resume-optimizer",
        "nodes": [
            {"id": "001-db-schema", "depends": [], "owner": "claude", "risk": "low", "done_criteria": "迁移可跑", "est_minutes": 60},
            {"id": "002-upload", "depends": ["001-db-schema"], "owner": "codex", "risk": "medium", "done_criteria": "可上传 PDF", "est_minutes": 90},
            {"id": "003-scoring", "depends": ["002-upload"], "owner": "claude", "risk": "high", "done_criteria": "返回分数", "est_minutes": 90},
        ],
    }
)

BUILDER_JSON = json.dumps(
    {"files": [{"path": "app/page.tsx", "content": "export default function Page() { return <main />; }"}]}
)


def test_full_pipeline_with_mock_llm():
    llm = MockLLM(
        responses={
            "[agent:planner]": PLANNER_JSON,
            "[agent:architect]": ARCHITECT_JSON,
            "[agent:decomposer]": DECOMPOSER_JSON,
        }
    )
    state = ProjectState(project_id="t", idea="做一个帮大学生改简历的网站")
    runner = SequentialRunner(
        [
            Planner(llm).run,
            Architect(llm).run,
            Decomposer(llm).run,
            make_gate_1(approver=lambda s: (True, None)),
        ]
    )

    out = runner.run(state)

    assert out.phase == ProjectPhase.PLAN_APPROVED
    assert out.gate_1_approved is True
    assert out.product_spec.project_name == "resume-optimizer"
    assert out.architecture.stack["frontend"].startswith("Next.js")
    assert len(out.dag.nodes) == 3
    assert len(llm.calls) == 3  # 三个 agent 各调一次；gate 不调 LLM
    assert out.errors == []


def test_pipeline_rejected_writes_nothing_terminal():
    llm = MockLLM(
        responses={
            "[agent:planner]": PLANNER_JSON,
            "[agent:architect]": ARCHITECT_JSON,
            "[agent:decomposer]": DECOMPOSER_JSON,
        }
    )
    state = ProjectState(project_id="t", idea="x")
    runner = SequentialRunner(
        [
            Planner(llm).run,
            Architect(llm).run,
            Decomposer(llm).run,
            make_gate_1(approver=lambda s: (False, "方向不对")),
        ]
    )

    out = runner.run(state)

    assert out.phase == ProjectPhase.PLAN_REJECTED
    assert out.gate_1_approved is False
    assert out.gate_1_feedback == "方向不对"


def test_full_build_pipeline_injects_l2_template_context():
    planner_data = json.loads(PLANNER_JSON)
    planner_data["core_features"] = ["用户登录", "Dashboard"]
    llm = MockLLM(
        responses={
            "[agent:planner]": json.dumps(planner_data),
            "[agent:architect]": ARCHITECT_JSON,
            "[agent:decomposer]": DECOMPOSER_JSON,
            "[agent:builder]": BUILDER_JSON,
        }
    )
    runner = SequentialRunner(
        [
            Planner(llm).run,
            Architect(llm).run,
            Decomposer(llm).run,
            make_gate_1(approver=lambda state: (True, None)),
            Builder(llm).run,
        ]
    )

    out = runner.run(ProjectState(project_id="t", idea="做一个会员数据看板"))

    assert out.phase == ProjectPhase.BUILD_DONE
    assert len(llm.calls) == 4
    builder_prompt = llm.calls[-1]["prompt"]
    assert "### auth: 认证与会话" in builder_prompt
    assert "### dashboard: Dashboard 与分析" in builder_prompt
    assert out.cache_lookup is not None
    assert out.cache_lookup.source == "l2"
    assert out.cache_lookup.match_ids == ["auth", "dashboard"]


def test_full_build_pipeline_falls_back_to_l3_case(tmp_path):
    case = KnowledgeCase(
        project_name="past-resume-project",
        one_liner="上传 PDF 简历并计算职位匹配度",
        core_features=["PDF 简历解析", "JD 匹配评分"],
        stack={"frontend": "Next.js"},
        data_model="Resume; MatchScore",
        api_design=["POST /api/v1/matches — 计算匹配分"],
        deploy_target="Vercel",
    )
    (tmp_path / "case-past.json").write_text(case.model_dump_json(), encoding="utf-8")
    llm = MockLLM(
        responses={
            "[agent:planner]": PLANNER_JSON,
            "[agent:architect]": ARCHITECT_JSON,
            "[agent:decomposer]": DECOMPOSER_JSON,
            "[agent:builder]": BUILDER_JSON,
        }
    )
    runner = SequentialRunner(
        [
            Planner(llm).run,
            Architect(llm).run,
            Decomposer(llm).run,
            make_gate_1(approver=lambda state: (True, None)),
            Builder(llm, knowledge_dir=tmp_path).run,
        ]
    )

    out = runner.run(ProjectState(project_id="t", idea="做一个简历优化工具"))

    assert out.phase == ProjectPhase.BUILD_DONE
    builder_prompt = llm.calls[-1]["prompt"]
    assert "L3 已验证跨项目案例" in builder_prompt
    assert "已验证案例: past-resume-project" in builder_prompt
    assert out.cache_lookup is not None
    assert out.cache_lookup.source == "l3"
    assert out.cache_lookup.estimated_reused_tokens > 0
