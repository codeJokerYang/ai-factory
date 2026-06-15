"""Build CLI（Week 3 v1）：一句话 idea → Plan → Builder → 可跑的 Next.js app。

    python -m orchestration.build_cli "<idea>"

Plan 阶段 Gate 1 在 build 流程里自动通过（Gate 1 已在 Plan pipeline 单独验证）；
真正的人工关卡是 Gate 2（preview 审核），在 app 跑起来后人工进行。
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


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or not argv[0].strip():
        print('用法: python -m orchestration.build_cli "<一句话 idea>"')
        return 2
    idea = argv[0].strip()

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
    runner = SequentialRunner(
        [
            Planner(llm).run,
            Architect(llm).run,
            Decomposer(llm).run,
            make_gate_1(approver=lambda s: (True, None)),
            Builder(llm).run,
        ]
    )
    state = runner.run(state)

    if state.phase == ProjectPhase.FAILED:
        print("\n❌ 构建失败:")
        for err in state.errors:
            print("  -", err)
        return 1

    # 持久化 Plan 产物（spec / architecture / tasks.json）—— 与 orchestration.cli 一致
    plan_paths = write_outputs(state)

    project = state.product_spec.project_name
    target = config.GENERATED_DIR / project
    written = write_app(target, project, state.generated_files)
    state.build_dir = str(target)

    print("\nPlan 产物:")
    for key, path in plan_paths.items():
        print(f"   {key:13}: {path}")

    print(f"\n✅ 已生成 app: {target}")
    print(f"   特性文件（Builder）: {len(state.generated_files)}  | 总文件: {len(written)}")
    for f in state.generated_files:
        print(f"     - {f.path}")
    print("\n下一步（本地 preview，Gate 2）:")
    print(f"   cd {target}")
    print("   npm install")
    print("   npm run dev   # 然后浏览器打开 http://localhost:3000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
