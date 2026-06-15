"""Build CLI（Week 3 v1）：一句话 idea → Plan → Builder → 可跑的 Next.js app。

    python -m orchestration.build_cli "<idea>" [--verify]

Plan 阶段 Gate 1 在 build 流程里自动通过（Gate 1 已在 Plan pipeline 单独验证）；
真正的人工关卡是 Gate 2（preview 审核），在 app 跑起来后人工进行。
--verify: 生成后自动跑 npm install && npm run build（自动构建门），编译不过即失败。
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
from .gates import make_gate_1
from .io_writers import write_outputs
from .runner import SequentialRunner
from .scaffold import write_app
from .state import ProjectPhase, ProjectState


def build_and_verify(target, project, state, builder, *, verify_fn=None, write_fn=None, max_repairs=1):
    """构建门 + 自愈：verify 失败（build 阶段）时把编译器报错回灌 Builder 修复 → 重写 → 复验。

    verify_fn / write_fn 可注入便于离线测试（默认用真实的 verify_app / write_app）。
    install 只在第一次跑（依赖装一次），修复后的复验跳过 install。
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
        result = verify_fn(target, install=False)
    state.build_passed = result.passed
    state.build_log = result.log
    return result


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    verify = "--verify" in argv
    gate2 = "--gate2" in argv
    positional = [a for a in argv if not a.startswith("--")]
    if not positional or not positional[0].strip():
        print('用法: python -m orchestration.build_cli "<一句话 idea>" [--verify] [--gate2]')
        return 2
    idea = positional[0].strip()

    try:
        from dotenv import load_dotenv

        load_dotenv(config.PROJECT_ROOT / ".env")
    except ImportError:
        pass

    if not config.get_api_key():
        print(f"❌ 未设置 {config.API_KEY_ENV}/{config.AUTH_TOKEN_ENV}。见 .env.example。")
        return 1

    from .llm import AnthropicLLM

    llm = AnthropicLLM()
    state = ProjectState(project_id=uuid.uuid4().hex[:8], idea=idea)

    # Plan + Build 一条龙；Gate 1 自动通过（build 演示），Gate 2 留给人工 preview 审核。
    builder = Builder(llm)
    runner = SequentialRunner(
        [
            Planner(llm).run,
            Architect(llm).run,
            Decomposer(llm).run,
            make_gate_1(approver=lambda s: (True, None)),
            builder.run,
        ]
    )
    state = runner.run(state)

    if state.phase == ProjectPhase.FAILED:
        print("\n❌ 构建失败:")
        for err in state.errors:
            print("  -", err)
        return 1

    for w in state.warnings:
        print(f"⚠️  {w}")

    # 持久化 Plan 产物（spec / architecture / tasks.json）—— 与 orchestration.cli 一致
    plan_paths = write_outputs(state)

    project = state.product_spec.project_name
    target = config.GENERATED_DIR / project
    written = write_app(target, project, state.generated_files, state.extra_dependencies)
    state.build_dir = str(target)

    print("\nPlan 产物:")
    for key, path in plan_paths.items():
        print(f"   {key:13}: {path}")

    print(f"\n✅ 已生成 app: {target}")
    print(f"   特性文件（Builder）: {len(state.generated_files)}  | 总文件: {len(written)}")
    for f in state.generated_files:
        print(f"     - {f.path}")

    if verify:
        print("\n🔧 自动构建门: npm install && npm run build（失败自动修复一次）...")
        result = build_and_verify(target, project, state, builder, max_repairs=1)
        if not result.passed:
            state.phase = ProjectPhase.FAILED
            print(f"❌ 构建门未通过（{result.step}，已尝试修复 {state.repair_attempts} 次）:\n")
            print(result.log)
            return 1
        state.phase = ProjectPhase.BUILD_VERIFIED
        if state.repair_attempts:
            print(f"✅ 构建门通过（Builder 自愈 {state.repair_attempts} 次后 next build 成功）")
        else:
            print("✅ 构建门通过（next build 成功）")

    # Gate 2 前自动代码审查（advisory：写入 state.code_review，高危问题进 warnings）
    from .agents.reviewer import Reviewer

    Reviewer(llm).run(state)
    cr = state.code_review
    if cr is not None:
        print(f"\n🔍 Reviewer: {'✅ 通过' if cr.passed else '⚠️  有问题'} — {cr.summary}")
        for issue in cr.issues:
            print(f"   [{issue.severity}] {issue.file}: {issue.message}")

    if gate2:
        from .gate2 import make_gate_2
        from .preview import dev_server, screenshot

        # --gate2 需要依赖已安装；未走 --verify 时先装一次
        if not verify:
            from .verify import verify_app

            print("\n🔧 安装依赖中（npm install）...")
            verify_app(target, install=True, timeout=600)

        print("\n🚀 启动 dev server 进行 Gate 2 预览...")
        with dev_server(target) as (url, ready):
            state.preview_url = url
            if not ready:
                print(f"⚠️  dev server 未在超时内就绪：{url}（可手动打开确认）")
            else:
                shot = config.GENERATED_DIR / f"{project}.preview.png"
                if screenshot(url, shot):
                    state.screenshot_path = str(shot)
                    print(f"📸 截图: {shot}")
                else:
                    print("（未安装 playwright，跳过自动截图；可手动打开预览）")
            state = make_gate_2()(state)

        if state.gate_2_approved:
            print("\n✅ Gate 2 通过 — 可合并。")
            return 0
        print("\n↩️  Gate 2 驳回。")
        if state.gate_2_feedback:
            print(f"   反馈: {state.gate_2_feedback}")
        return 1

    print("\n下一步（本地 preview，Gate 2）:")
    print(f"   cd {target}")
    if not verify:
        print("   npm install")
    print("   npm run dev   # 然后浏览器打开 http://localhost:3000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
