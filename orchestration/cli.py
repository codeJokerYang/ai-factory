"""CLI 入口。

    python -m orchestration.cli "做一个帮大学生改简历的网站，支持 PDF 上传，按 JD 打分"

跑 Planner → Architect → Decomposer → Gate 1，落盘 spec / architecture / tasks.json。
"""
from __future__ import annotations

import sys
import uuid
from typing import List, Optional

from . import config
from .agents.architect import Architect
from .agents.decomposer import Decomposer
from .agents.planner import Planner
from .gates import make_gate_1
from .io_writers import write_outputs
from .runner import SequentialRunner
from .state import ProjectPhase, ProjectState


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or not argv[0].strip():
        print('用法: python -m orchestration.cli "<一句话 idea>"')
        return 2
    idea = argv[0].strip()

    try:
        from dotenv import load_dotenv

        load_dotenv(config.PROJECT_ROOT / ".env")
    except ImportError:
        pass

    if not config.get_api_key():
        print(f"❌ 未设置 {config.API_KEY_ENV}。复制 .env.example 为 .env 并填入，或设置环境变量。")
        return 1

    from .llm import AnthropicLLM

    llm = AnthropicLLM()
    state = ProjectState(project_id=uuid.uuid4().hex[:8], idea=idea)
    runner = SequentialRunner(
        [
            Planner(llm).run,
            Architect(llm).run,
            Decomposer(llm).run,
            make_gate_1(),
        ]
    )
    state = runner.run(state)

    if state.phase == ProjectPhase.FAILED:
        print("\n❌ Plan 阶段失败:")
        for err in state.errors:
            print("  -", err)
        return 1

    draft = state.phase != ProjectPhase.PLAN_APPROVED
    paths = write_outputs(state, draft=draft)
    print("\n产物:")
    for key, path in paths.items():
        print(f"  {key:13}: {path}")
    if state.gate_1_approved:
        print("\n✅ Gate 1 通过 — Plan 阶段完成。")
    else:
        print("\n↩️  Gate 1 驳回 — 已存为 draft。")
        if state.gate_1_feedback:
            print(f"   反馈: {state.gate_1_feedback}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
