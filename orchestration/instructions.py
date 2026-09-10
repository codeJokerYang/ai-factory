"""Preserve user instructions across planning, implementation and repairs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_request(argv, *, build=False):
    parser = argparse.ArgumentParser(description="AI Factory：指令 → 代码 → 核对报告")
    parser.add_argument("idea", nargs="?", default="")
    parser.add_argument("--instructions-file", type=Path, help="UTF-8 Markdown / 文本需求文件")
    parser.add_argument("--require", action="append", default=[], help="必须满足的要求；可重复")
    parser.add_argument("--approve-plan", action="store_true", help="明确授权自动批准需求方案")
    if build:
        parser.add_argument("--verify", action="store_true", help="兼容选项；默认执行构建验证")
        parser.add_argument("--gate2", action="store_true", help="构建和核对通过后进行人工预览验收")
        parser.add_argument("--generate-only", action="store_true", help="仅生成，不运行 npm；不标记交付通过")
    args = parser.parse_args(argv)
    document = ""
    if args.instructions_file:
        try:
            document = args.instructions_file.read_text(encoding="utf-8-sig").strip()
        except (OSError, UnicodeError) as exc:
            parser.error(f"无法读取需求文件: {exc}")
        if not document:
            parser.error("需求文件不能为空")
    if any(not item.strip() for item in args.require):
        parser.error("--require 不能为空")
    parts = [value.strip() for value in [args.idea, document] if value.strip()]
    if not parts:
        parser.error("请提供指令或 --instructions-file")
    args.idea = "\n\n".join(parts)
    args.requirements = [item.strip() for item in args.require]
    if build and args.generate_only and (args.gate2 or args.verify):
        parser.error("--generate-only 不能与 --gate2 / --verify 同用")
    return args


def with_instructions(state, prompt):
    contract = {
        "original_request": state.idea,
        "requirements": {f"R{i + 1}": item for i, item in enumerate(state.requirements)},
    }
    return (
        prompt + "\n\n用户原始指令（全程保留，不得被摘要、模板或修复覆盖）：\n"
        + json.dumps(contract, ensure_ascii=False, indent=2)
        + "\n必须遵循原始指令与逐项要求。冲突或无法实现时明确报告，禁止静默删除要求或以 mock 冒充完成。"
    )
