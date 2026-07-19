"""Builder L2 方案模板缓存。

v1 使用内置、只读模板：从 Product Spec 中确定性匹配常见实现模式，再把精简的工程约束
注入 Builder prompt。匹配过程不调用 LLM，也不复用历史项目代码，避免把错误或敏感数据
带入新项目。跨项目案例与成功产物回写属于 L3，后续单独实现。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence, Tuple

from .schemas import ProductSpec

MAX_TEMPLATE_MATCHES = 2


@dataclass(frozen=True)
class SolutionTemplate:
    id: str
    title: str
    keywords: Tuple[str, ...]
    guidance: Tuple[str, ...]


@dataclass(frozen=True)
class TemplateMatch:
    template: SolutionTemplate
    matched_keywords: Tuple[str, ...]

    @property
    def score(self) -> int:
        return len(self.matched_keywords)


BUILTIN_TEMPLATES: Tuple[SolutionTemplate, ...] = (
    SolutionTemplate(
        id="auth",
        title="认证与会话",
        keywords=("auth", "authentication", "login", "sign in", "sign up", "登录", "注册", "认证"),
        guidance=(
            "集中管理登录态，并为加载中、未登录、已登录三种状态提供明确 UI。",
            "受保护操作必须再次检查会话；Supabase env 缺失时使用标注清楚的本地 mock。",
            "不要在客户端代码或持久化数据中放置服务端密钥。",
        ),
    ),
    SolutionTemplate(
        id="payment",
        title="支付与订阅",
        keywords=("payment", "checkout", "billing", "subscription", "支付", "结算", "订阅", "账单"),
        guidance=(
            "把支付状态建模为 pending/succeeded/failed，并在 UI 中处理重复提交与失败重试。",
            "金额与支付结果不得只信任客户端；v1 无支付服务时使用明确标注的 mock 流程。",
            "不要在客户端暴露密钥，也不要把前端跳转当作支付成功凭据。",
        ),
    ),
    SolutionTemplate(
        id="crud",
        title="CRUD 数据管理",
        keywords=("crud", "create edit delete", "增删改查", "新增编辑删除", "创建编辑删除"),
        guidance=(
            "使用稳定 id 和显式 TypeScript 类型管理记录，派生列表不要复制为第二份状态。",
            "创建/编辑表单需要必填校验与可见错误；删除使用内联确认 UI，不调用 confirm()。",
            "覆盖空列表、无搜索结果、保存中和操作失败状态。",
        ),
    ),
    SolutionTemplate(
        id="dashboard",
        title="Dashboard 与分析",
        keywords=("dashboard", "analytics", "仪表盘", "数据看板", "分析看板", "统计报表"),
        guidance=(
            "先展示关键指标与口径，再提供筛选、列表或图表；筛选应驱动同一份派生数据。",
            "指标卡、趋势区和明细区需具备空数据与加载状态，并保持移动端可读。",
            "mock 数据必须自洽且标注为演示数据，避免暗示实时生产指标。",
        ),
    ),
)


def _normalise(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _search_text(spec: ProductSpec) -> str:
    values = [
        spec.project_name,
        spec.one_liner,
        spec.target_users,
        *spec.core_features,
        *spec.mvp_in_scope,
    ]
    for story in spec.user_stories:
        values.extend((story.as_a, story.i_want, story.so_that))
    return _normalise("\n".join(value for value in values if value))


def _contains_keyword(text: str, keyword: str) -> bool:
    needle = _normalise(keyword)
    if needle.isascii():
        # 英文关键词必须按完整词/短语命中，避免 auth 误中 authoring。
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text) is not None
    return needle in text


def match_templates(
    spec: ProductSpec | None,
    *,
    templates: Sequence[SolutionTemplate] = BUILTIN_TEMPLATES,
    limit: int = MAX_TEMPLATE_MATCHES,
) -> list[TemplateMatch]:
    """按命中关键词数排序；同分保持注册表顺序，保证测试和生成结果稳定。"""
    if spec is None or limit <= 0:
        return []

    text = _search_text(spec)
    ranked: list[tuple[int, int, TemplateMatch]] = []
    for index, template in enumerate(templates):
        matched = tuple(keyword for keyword in template.keywords if _contains_keyword(text, keyword))
        if matched:
            match = TemplateMatch(template=template, matched_keywords=matched)
            ranked.append((-match.score, index, match))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked[: min(limit, MAX_TEMPLATE_MATCHES)]]


def render_template_context(matches: Sequence[TemplateMatch]) -> str:
    """把命中模板渲染成短 prompt；只含受控注册表内容，不回显用户输入。"""
    sections = []
    for match in matches:
        guidance = "\n".join(f"- {item}" for item in match.template.guidance)
        sections.append(f"### {match.template.id}: {match.template.title}\n{guidance}")
    return "\n\n".join(sections)
