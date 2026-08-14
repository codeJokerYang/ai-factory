"""Local browser console for exercising the AI Factory pipeline without an API key.

The console deliberately uses the production agents and runner boundary with a
deterministic ``MockLLM``.  It is a test surface, not a second orchestration
implementation: Planner, Architect, Decomposer, Gate 1, Builder, Reviewer and
Security all execute their normal code paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .agents.architect import Architect
from .agents.builder import Builder
from .agents.decomposer import Decomposer
from .agents.planner import Planner
from .agents.reviewer import Reviewer
from .agents.security import SecurityAgent
from .config import FIXED_STACK
from .gates import make_gate_1
from .llm import MockLLM
from .runner import run_step_safely
from .state import ProjectPhase, ProjectState

STATIC_DIR = Path(__file__).resolve().parent.parent / "web_console"
MAX_IDEA_LENGTH = 500
MAX_REQUEST_BYTES = 16 * 1024


class ConsoleInputError(ValueError):
    """Raised when a console request cannot safely enter the pipeline."""


def _normalise_idea(idea: Any) -> str:
    if not isinstance(idea, str) or not idea.strip():
        raise ConsoleInputError("请输入一句产品想法。")
    value = " ".join(idea.split())
    if len(value) > MAX_IDEA_LENGTH:
        raise ConsoleInputError(f"产品想法不能超过 {MAX_IDEA_LENGTH} 个字符。")
    return value


def infer_features(idea: str) -> list[str]:
    """Return stable demo features while keeping the user's domain visible."""
    rules = (
        (("简历", "求职", "jd"), ["简历资料管理", "职位匹配评分", "优化建议"]),
        (("记账", "账单", "预算", "财务"), ["快速记账", "分类统计", "预算提醒"]),
        (("任务", "待办", "项目"), ["任务工作台", "进度追踪", "结果复盘"]),
        (("课程", "学习", "教育"), ["学习计划", "进度看板", "学习反馈"]),
    )
    lowered = idea.lower()
    for keywords, features in rules:
        if any(keyword in lowered for keyword in keywords):
            return features
    return ["核心流程工作台", "进度与状态追踪", "结果摘要"]


def _project_name(idea: str) -> str:
    suffix = hashlib.sha1(idea.encode("utf-8")).hexdigest()[:6]
    return f"factory-demo-{suffix}"


def _planner_payload(idea: str, project_name: str, features: list[str]) -> dict[str, Any]:
    return {
        "project_name": project_name,
        "one_liner": idea,
        "target_users": "希望用更少步骤完成核心任务的目标用户",
        "core_features": features,
        "mvp_in_scope": features[:2],
        "mvp_out_of_scope": ["复杂组织权限", "多地区商业化"],
        "user_stories": [
            {"as_a": "首次用户", "i_want": f"使用{features[0]}", "so_that": "快速理解产品价值"},
            {"as_a": "活跃用户", "i_want": f"查看{features[1]}", "so_that": "掌握当前进展"},
            {"as_a": "产品负责人", "i_want": f"获得{features[2]}", "so_that": "做出下一步决策"},
        ],
        "success_metrics": ["核心流程完成率 > 60%", "首次价值时间 < 3 分钟"],
        "risks": ["需求范围继续膨胀", "首版数据不足"],
    }


def _architecture_payload(features: list[str]) -> dict[str, Any]:
    return {
        "stack": FIXED_STACK,
        "data_model": "Workspace(id, name); Item(id, workspace_id, title, status); Activity(id, item_id, kind)",
        "api_design": [
            {"method": "GET", "path": "/api/v1/items", "purpose": f"读取{features[0]}数据"},
            {"method": "POST", "path": "/api/v1/items", "purpose": "创建核心记录"},
            {"method": "PUT", "path": "/api/v1/items/:id", "purpose": "更新进度与状态"},
        ],
        "deploy_target": "Vercel",
        "adrs": [
            {
                "title": "采用 local-first MVP",
                "decision": "首版使用浏览器本地状态并保留 Supabase 接口边界",
                "rationale": "降低首次体验成本，同时不阻塞后续持久化",
            }
        ],
    }


def _dag_payload(project_name: str) -> dict[str, Any]:
    node_specs = [
        ("001-foundation", [], "codex", "low", "脚手架与设计令牌可用", 30),
        ("002-data-model", ["001-foundation"], "claude", "medium", "数据契约通过校验", 45),
        ("003-api-boundary", ["002-data-model"], "claude", "medium", "API 边界可测试", 60),
        ("004-app-shell", ["001-foundation"], "codex", "low", "响应式应用壳完成", 45),
        ("005-dashboard", ["003-api-boundary", "004-app-shell"], "codex", "medium", "核心看板可操作", 75),
        ("006-core-flow", ["003-api-boundary"], "claude", "high", "核心流程端到端完成", 90),
        ("007-ui-states", ["005-dashboard", "006-core-flow"], "codex", "medium", "加载和异常状态完整", 60),
        ("008-accessibility", ["005-dashboard"], "codex", "low", "键盘与读屏检查通过", 45),
        ("009-security", ["003-api-boundary"], "claude", "high", "安全规则扫描通过", 60),
        ("010-tests", ["007-ui-states", "008-accessibility", "009-security"], "codex", "medium", "单元与集成测试通过", 90),
        ("011-documentation", ["010-tests"], "codex", "low", "规格与运行手册同步", 30),
        ("012-release", ["011-documentation"], "claude", "medium", "预览构建可供 Gate 2 审核", 45),
    ]
    return {
        "project": project_name,
        "nodes": [
            {
                "id": node_id,
                "depends": depends,
                "owner": owner,
                "risk": risk,
                "done_criteria": criteria,
                "est_minutes": minutes,
            }
            for node_id, depends, owner, risk, criteria, minutes in node_specs
        ],
    }


def _builder_payload(idea: str, features: list[str]) -> dict[str, Any]:
    idea_literal = json.dumps(idea, ensure_ascii=False)
    feature_literals = ", ".join(json.dumps(feature, ensure_ascii=False) for feature in features)
    page = f'''const features = [{feature_literals}];

export default function Page() {{
  const idea = {idea_literal};
  return (
    <main className="ui-shell">
      <header className="grid gap-6 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <p className="ui-kicker">Generated product</p>
          <h1 className="ui-title mt-3">{{idea}}</h1>
          <p className="ui-copy mt-4">这是 AI Factory 根据产品想法生成的 MVP 界面提案。</p>
        </div>
        <button className="ui-button-primary" type="button">创建第一条记录</button>
      </header>
      <section aria-label="MVP 核心能力" className="mt-8 grid gap-4 md:grid-cols-3">
        {{features.map((feature, index) => (
          <article className="ui-panel p-5" key={{feature}}>
            <span className="text-sm font-semibold text-ui-brand">0{{index + 1}}</span>
            <h2 className="mt-4 text-lg font-semibold">{{feature}}</h2>
            <p className="mt-2 text-sm text-ui-muted">包含清晰状态、反馈与移动端布局。</p>
          </article>
        ))}}
      </section>
      <form className="ui-panel mt-6 grid gap-4 p-5 md:grid-cols-[1fr_auto] md:items-end">
        <div>
          <label className="text-sm font-medium" htmlFor="first-task">第一项任务</label>
          <input className="ui-field mt-2" id="first-task" placeholder="输入需要完成的内容" />
        </div>
        <button className="ui-button-secondary" type="submit">添加任务</button>
      </form>
    </main>
  );
}}
'''
    return {"files": [{"path": "app/page.tsx", "content": page}]}


def _mock_responses(idea: str) -> dict[str, str]:
    project_name = _project_name(idea)
    features = infer_features(idea)
    return {
        "[agent:planner]": json.dumps(
            _planner_payload(idea, project_name, features), ensure_ascii=False
        ),
        "[agent:architect]": json.dumps(_architecture_payload(features), ensure_ascii=False),
        "[agent:decomposer]": json.dumps(_dag_payload(project_name), ensure_ascii=False),
        "[agent:builder]": json.dumps(_builder_payload(idea, features), ensure_ascii=False),
        "[agent:reviewer]": json.dumps(
            {
                "passed": True,
                "summary": "结构、响应式布局和基础可访问性符合当前 UI 基线。",
                "issues": [],
            },
            ensure_ascii=False,
        ),
    }


def _stage_summary(stage_id: str, state: ProjectState) -> str:
    if state.errors:
        return state.errors[-1]
    if stage_id == "planner" and state.product_spec:
        return f"识别 {len(state.product_spec.core_features)} 项核心能力"
    if stage_id == "architect" and state.architecture:
        return f"确定 {len(state.architecture.api_design)} 个 API 边界"
    if stage_id == "decomposer" and state.dag:
        return f"拆分为 {len(state.dag.nodes)} 个 DAG 节点"
    if stage_id == "gate-1":
        return "方向已由本地 Mock Gate 自动批准"
    if stage_id == "builder":
        return f"生成 {len(state.generated_files)} 个特性文件"
    if stage_id == "reviewer" and state.code_review:
        return state.code_review.summary
    if stage_id == "security" and state.security_report:
        return f"规则扫描完成，风险等级 {state.security_report.risk_level}"
    return state.phase.value


def _dump(model: Any) -> Any:
    return model.model_dump(mode="json") if model is not None else None


def run_mock_pipeline(idea: Any) -> dict[str, Any]:
    """Execute the real agent chain with deterministic LLM responses."""
    normalised_idea = _normalise_idea(idea)
    llm = MockLLM(responses=_mock_responses(normalised_idea))
    state = ProjectState(project_id=uuid.uuid4().hex[:8], idea=normalised_idea)
    steps: list[tuple[str, str, Callable[[ProjectState], ProjectState]]] = [
        ("planner", "Planner", Planner(llm).run),
        ("architect", "Architect", Architect(llm).run),
        ("decomposer", "Decomposer", Decomposer(llm).run),
        ("gate-1", "Gate 1", make_gate_1(approver=lambda current: (True, None))),
        ("builder", "Builder", Builder(llm).run),
        ("reviewer", "Reviewer", Reviewer(llm).run),
        ("security", "Security", SecurityAgent(llm).run),
    ]
    stages: list[dict[str, Any]] = []
    started = time.perf_counter()
    terminal = {ProjectPhase.FAILED, ProjectPhase.PLAN_REJECTED}

    for stage_id, label, step in steps:
        stage_started = time.perf_counter()
        state = run_step_safely(step, state)
        stages.append(
            {
                "id": stage_id,
                "label": label,
                "status": "failed" if state.phase == ProjectPhase.FAILED else "passed",
                "phase": state.phase.value,
                "duration_ms": max(1, round((time.perf_counter() - stage_started) * 1000)),
                "summary": _stage_summary(stage_id, state),
            }
        )
        if state.phase in terminal:
            break

    security_passed = state.security_report is None or state.security_report.passed
    status = "completed" if state.phase != ProjectPhase.FAILED and security_passed else "blocked"
    return {
        "run_id": state.project_id,
        "mode": "mock",
        "status": status,
        "phase": state.phase.value,
        "idea": state.idea,
        "duration_ms": max(1, round((time.perf_counter() - started) * 1000)),
        "llm_calls": len(llm.calls),
        "stages": stages,
        "product_spec": _dump(state.product_spec),
        "architecture": _dump(state.architecture),
        "dag": _dump(state.dag),
        "generated_files": [_dump(file) for file in state.generated_files],
        "quality": {
            "ui": _dump(state.ui_quality),
            "review": _dump(state.code_review),
            "security": _dump(state.security_report),
            "warnings": state.warnings,
            "errors": state.errors,
        },
    }


class ConsoleRequestHandler(SimpleHTTPRequestHandler):
    server_version = "AIFactoryConsole/1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'",
        )
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json({"status": "ok", "mode": "mock", "api_key_required": False})
            return
        if path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if urlparse(self.path).path != "/api/runs":
            self._send_json({"error": {"code": "not_found", "message": "接口不存在。"}}, 404)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0:
            self._send_json({"error": {"code": "empty_body", "message": "请求体不能为空。"}}, 400)
            return
        if content_length > MAX_REQUEST_BYTES:
            self._send_json(
                {"error": {"code": "payload_too_large", "message": "请求内容过大。"}}, 413
            )
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            result = run_mock_pipeline(payload.get("idea") if isinstance(payload, dict) else None)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json({"error": {"code": "invalid_json", "message": "JSON 格式无效。"}}, 400)
            return
        except ConsoleInputError as exc:
            self._send_json({"error": {"code": "validation_error", "message": str(exc)}}, 422)
            return
        except Exception:  # noqa: BLE001 - do not leak internals over the local HTTP boundary
            self._send_json(
                {"error": {"code": "internal_error", "message": "流水线运行失败，请查看终端日志。"}},
                500,
            )
            return
        self._send_json(result, 200)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        print(f"[web-console] {self.address_string()} {format % args}")


def create_server(host: str = "127.0.0.1", port: int = 3110) -> ThreadingHTTPServer:
    if not STATIC_DIR.is_dir():
        raise FileNotFoundError(f"缺少控制台静态目录: {STATIC_DIR}")
    return ThreadingHTTPServer((host, port), ConsoleRequestHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Factory 本地可测试控制台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=3110, type=int)
    args = parser.parse_args(argv)
    server = create_server(args.host, args.port)
    print(f"AI Factory Console: http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
