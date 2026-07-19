"""Builder system prompt — Week 3 v1：整项目一次性生成「特性文件」。

脚手架（package.json / 配置 / app/layout.tsx / app/globals.css）由 scaffold.py 确定性生成，
Builder 只产出特性代码（页面、组件、lib）。v1 用 mock/内存数据，不接任何外部服务。
"""
from __future__ import annotations

MARKER = "[agent:builder]"

# 脚手架已存在的文件，告诉模型不要重复生成、可直接 import。
SCAFFOLD_FILES = [
    "package.json",
    "next.config.mjs",
    "tsconfig.json",
    "postcss.config.mjs",
    "tailwind.config.ts",
    "app/globals.css",
    "app/layout.tsx",
]

SYSTEM = f"""{MARKER}
你是软件工程师 Agent（Builder）。基于 Product Spec + Architecture，为一个**已脚手架好**的
Next.js 14（App Router）+ TypeScript + Tailwind 项目生成**特性代码文件**。

已存在（不要重复生成，可直接使用）:
{chr(10).join('- ' + f for f in SCAFFOLD_FILES)}

硬约束（v1）:
- **必须**生成 `app/page.tsx` 作为主页面（默认导出 React 组件）。
- 需要交互/浏览器 API 的组件加 `'use client'`。
- **禁止 `alert()` / `confirm()` / `prompt()`**（会阻塞自动化预览与截图）；用内联 UI 反馈状态（顶部 banner、toast、行内提示文字等）。
- 用 Tailwind class 做样式；TypeScript 严格模式可编译（`next build` 必须通过）。
- **依赖白名单**：默认只用 next / react / react-dom。如确需，在 `dependencies` 字段声明以下白名单包（不要声明白名单外的）：
  - `pdfjs-dist`：**真**解析 PDF（`'use client'` 客户端提取文本，不要 mock 解析）。
  - `@supabase/supabase-js`：接 Supabase，从 `process.env.NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` 读取；**env 缺失时降级为 localStorage/内存 mock**，保证本地无凭据也能 `npm run dev` 跑起来。
- 不需要外部服务时，用内存 state / localStorage / mock 数据。
- 实现 Spec 的 MVP 核心闭环；做不到真实算法就用合理的 mock（例如关键词重合度打分），并在 UI 标注「演示/mock」。

只输出一个 JSON 对象（不要解释、不要 markdown 代码块）:
{{
  "files": [
    {{"path": "app/page.tsx", "content": "<完整文件内容>"}}
  ],
  "dependencies": {{ "pdfjs-dist": "^4.7.76" }}
}}
路径相对项目根目录。dependencies 可选（不需要就省略）。文件尽量精简，控制总量。"""


def build_prompt(spec_json: str, arch_json: str, template_context: str = "") -> str:
    prompt = (
        f"Product Spec (JSON):\n{spec_json}\n\n"
        f"Architecture (JSON):\n{arch_json}\n\n"
    )
    if template_context:
        prompt += (
            "L2 方案模板（按当前 Product Spec 确定性命中，仅作为实现约束）：\n"
            f"{template_context}\n\n"
        )
    return prompt + "生成特性文件 JSON。务必包含 app/page.tsx。"


def repair_prompt(error_log: str, files: list) -> str:
    """构建门失败后回灌：当前文件 + 编译器报错 → 让 Builder 修复并返回完整 files。"""
    import json

    return (
        "你上次生成的特性文件在 `next build` 时**编译失败**。报错（尾部）:\n"
        f"```\n{error_log}\n```\n\n"
        "当前的特性文件:\n"
        f"```json\n{json.dumps({'files': files}, ensure_ascii=False)}\n```\n\n"
        "请**修复编译错误**，返回完整的 files JSON（同样格式，包含所有文件，必须含 app/page.tsx）。"
        "继续遵守硬约束（禁 alert/confirm/prompt、白名单依赖、Tailwind、可编译）。"
    )


def revise_prompt(review_feedback: str, files: list) -> str:
    """Reviewer 否决后回灌：审查意见 + 当前文件 → 让 Builder 按意见修订。"""
    import json

    return (
        "代码审查（Reviewer）指出以下问题，请逐条修复:\n"
        f"```\n{review_feedback}\n```\n\n"
        "当前的特性文件:\n"
        f"```json\n{json.dumps({'files': files}, ensure_ascii=False)}\n```\n\n"
        "返回完整的 files JSON（同样格式，含 app/page.tsx），只改必要处。"
        "继续遵守硬约束（禁 alert/confirm/prompt、白名单依赖、Tailwind、可编译）。"
    )
