"""Instruction-driven CLI and shared web workflow.

Build validation is the default. --generate-only explicitly skips execution.
Plan and preview approvals are separate; all final quality checks must pass.
"""
from __future__ import annotations

import sys
import uuid
from typing import List, Optional

from . import config
from .agents.architect import Architect
from .agents.builder import Builder
from .agents.decomposer import Decomposer
from .agents.planner import Planner
from .cache_metrics import record_cache_lookup, record_case_saved
from .gates import make_gate_1
from .scaffold import write_app
from .state import ProjectPhase, ProjectState
from .util import safe_path_component


def build_and_verify(target, project, state, builder, *, verify_fn=None, write_fn=None, max_repairs=1):
    """构建门 + 自愈：verify 失败（build 阶段）时把编译器报错回灌 Builder 修复 → 重写 → 复验。

    verify_fn / write_fn 可注入便于离线测试（默认用真实的 verify_app / write_app）。
    修复可能改变依赖，因此复验重新安装白名单依赖。
    """
    from .verify import verify_app

    verify_fn = verify_fn or verify_app
    write_fn = write_fn or write_app

    result = verify_fn(target, install=True)
    while (not result.passed) and result.step == "build" and state.repair_attempts < max_repairs:
        state.repair_attempts += 1
        builder.repair(state, result.log)
        if state.phase == ProjectPhase.FAILED:  # repair 自身解析失败
            break
        write_fn(target, project, state.generated_files, state.extra_dependencies)
        result = verify_fn(target, install=True)
    state.build_passed = result.passed
    state.build_log = result.log
    return result


def _format_review(review) -> str:
    lines = [review.summary] if review.summary else []
    for issue in review.issues:
        lines.append(f"- [{issue.severity}] {issue.file}: {issue.message}")
    return "\n".join(lines)


def review_and_revise(state, target, project, builder, reviewer, *, write_fn=None, max_rounds=1):
    """Reviewer 否决 → Builder 按审查意见修订 → 复审，最多 max_rounds 轮；仍不过则升级 Gate 2。

    write_fn 可注入便于离线测试（默认 write_app）。
    """
    write_fn = write_fn or write_app

    reviewer.run(state)
    while (
        state.code_review is not None
        and not state.code_review.passed
        and state.review_rounds < max_rounds
        and state.phase != ProjectPhase.FAILED
    ):
        state.review_rounds += 1
        builder.revise(state, _format_review(state.code_review))
        if state.phase == ProjectPhase.FAILED:  # revise 自身解析失败
            break
        write_fn(target, project, state.generated_files, state.extra_dependencies)
        reviewer.run(state)
    return state.code_review


def execute(state, llm, *, approver, preview_approver=None, generate_only=False, emit=print, checkpoint=None):
    """Shared CLI/web workflow. Reports are local; no automatic publish or merge."""
    from .agents.reviewer import Reviewer
    from .agents.security import SecurityAgent
    from .acceptance import check_acceptance
    from .runner import run_step_safely
    from .security import scan_files, is_blocking, validate_feature_files
    from .verify import VerifyResult

    builder = Builder(llm)
    report_dir = config.PROJECT_ROOT / '.factory' / 'runs' / state.project_id
    report_dir.mkdir(parents=True, exist_ok=True)

    def save():
        import json
        from .history import redact
        temp = report_dir / 'report.json.tmp'
        temp.write_text(json.dumps(redact(state.model_dump(mode='json')), ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(report_dir / 'report.json')
        if checkpoint:
            checkpoint(state)

    def step(label, fn):
        nonlocal state
        emit(label)
        state = run_step_safely(fn, state)
        save()
        if state.phase == ProjectPhase.FAILED:
            raise RuntimeError('; '.join(state.errors))

    def safe_verify(target, install=True):
        from .verify import verify_app
        validate_feature_files(state.generated_files)
        if is_blocking(scan_files([(f.path, f.content) for f in state.generated_files])):
            return VerifyResult(False, 'security', '安全扫描阻止执行生成代码')
        return verify_app(target, install=install)

    try:
        for name, agent in [('分析需求', Planner(llm)), ('设计方案', Architect(llm)), ('拆解任务', Decomposer(llm))]:
            step(name, agent.run)
        step('等待方案审批', make_gate_1(approver))
        if not state.gate_1_approved:
            return state
        step('生成代码', builder.run)
        if state.cache_lookup is not None:
            try:
                record_cache_lookup(state.cache_lookup)
            except (OSError, ValueError) as exc:
                state.warnings.append(f'缓存指标未记录: {exc}')
        project = state.product_spec.project_name
        project_dir = safe_path_component(project, fallback='app') + '-' + state.project_id
        target = config.GENERATED_DIR / project_dir
        # A fresh directory prevents previous generated files surviving repairs.
        state.build_dir = str(target)
        write_app(target, project, state.generated_files, state.extra_dependencies)
        save()
        if generate_only:
            emit('仅生成完成，未执行验证；不能视为交付通过')
            return state
        reviewer = Reviewer(llm)
        step('代码审查与修订', lambda s: (review_and_revise(s, target, project, builder, reviewer), s)[1])
        step('安全扫描', SecurityAgent(llm).run)
        if state.security_report is None or not state.security_report.passed:
            raise ValueError('安全扫描未通过，禁止安装、构建或预览')
        emit('安装依赖与构建，失败时尝试修复一次')
        result = build_and_verify(target, project, state, builder, verify_fn=safe_verify)
        save()
        if not result.passed or state.phase == ProjectPhase.FAILED:
            raise ValueError('构建未通过: ' + result.log)
        state.phase = ProjectPhase.BUILD_VERIFIED
        # Always review the final files, including compiler repairs.
        step('最终代码复审', reviewer.run)
        if state.code_review is None or not state.code_review.passed:
            raise ValueError('最终代码审查未通过')
        step('最终安全检查', SecurityAgent(llm).run)
        if state.security_report is None or not state.security_report.passed:
            raise ValueError('最终安全检查未通过')
        step('逐项核对原始指令', lambda s: check_acceptance(s, llm, reviewer.model))
        if not state.acceptance_report.passed:
            raise ValueError('指令核对未通过：请查看缺失或不确定项；代码核对不等于业务测试')
        if preview_approver:
            from .preview import dev_server
            from .gate2 import make_gate_2
            emit('启动预览')
            with dev_server(target) as (url, ready):
                state.preview_url = url
                state.preview_ready = ready
                save()
                if not ready:
                    raise ValueError('预览服务未就绪，不能批准交付')
                step('等待预览验收', make_gate_2(preview_approver))
            if state.gate_2_approved:
                from .knowledge_cache import save_knowledge_case
                try:
                    save_knowledge_case(state)
                    record_case_saved(state)
                except (OSError, ValueError) as exc:
                    state.warnings.append(f'案例或指标未保存: {exc}')
        else:
            emit('构建与代码核对通过，尚未进行人工预览验收')
        return state
    except Exception as exc:
        message = str(exc)
        if message not in state.errors:
            state.errors.append(message)
        state.phase = ProjectPhase.FAILED
        emit('失败: ' + message)
        return state
    finally:
        save()
        emit('本地报告: ' + str(report_dir / 'report.json'))


def main(argv: Optional[List[str]] = None) -> int:
    from .instructions import parse_request
    from .gates import _cli_approver
    from .gate2 import _cli_approver as preview_approver
    from .llm import AnthropicLLM
    from dotenv import load_dotenv
    args = parse_request(argv, build=True)
    load_dotenv(config.PROJECT_ROOT / '.env')
    if not config.get_api_key():
        print('未配置模型 API 凭据；请在本地 .env 或环境变量中配置。')
        return 1
    state = ProjectState(project_id=uuid.uuid4().hex[:12], idea=args.idea, requirements=args.requirements)
    state = execute(state, AnthropicLLM(),
                    approver=(lambda s: (True, None)) if args.approve_plan else _cli_approver,
                    preview_approver=preview_approver if args.gate2 else None,
                    generate_only=args.generate_only)
    return 1 if state.phase in {ProjectPhase.FAILED, ProjectPhase.PLAN_REJECTED, ProjectPhase.GATE_2_REJECTED} else 0


if __name__ == '__main__':
    raise SystemExit(main())
