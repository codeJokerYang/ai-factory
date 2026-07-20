"""L3 跨项目知识缓存：保存已验证案例，并为新项目检索一个相关架构参考。

缓存只保存脱敏后的 Product Spec 摘要与 Architecture 摘要，不保存生成代码、用户故事、
目标用户或凭据。只有通过 build、Reviewer、Security 与 Gate 2 的项目才可写入。
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import config
from .schemas import ProductSpec
from .state import ProjectPhase, ProjectState

SCHEMA_VERSION = 1
MAX_CASE_BYTES = 64 * 1024
MAX_KNOWLEDGE_MATCHES = 1
MAX_CONTEXT_CHARS = 4000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?(?:-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|$)",
    re.DOTALL,
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|secret|passwd|password|access[_-]?token|auth[_-]?token)\b"
    r"(\s*[:=]\s*)([\"']?)[^\s,;\"']{8,}\3"
)
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~-]{8,}")
_LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{32,}(?![A-Za-z0-9_-])")
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CN_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_LATIN_TERM = re.compile(r"[a-z0-9][a-z0-9_-]+")
_CJK_SEQUENCE = re.compile(r"[\u3400-\u9fff]+")

_LATIN_STOP_WORDS = {
    "and",
    "app",
    "for",
    "from",
    "project",
    "system",
    "the",
    "tool",
    "user",
    "users",
    "with",
}
_CJK_STOP_TERMS = {"一个", "功能", "可以", "支持", "用户", "系统", "工具", "项目", "数据"}


class KnowledgeCase(BaseModel):
    """可持久化、可版本校验的最小案例格式。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    project_name: str = Field(min_length=1, max_length=160)
    one_liner: str = Field(default="", max_length=600)
    core_features: List[str] = Field(default_factory=list, max_length=12)
    stack: Dict[str, str] = Field(default_factory=dict)
    data_model: str = Field(default="", max_length=1600)
    api_design: List[str] = Field(default_factory=list, max_length=20)
    deploy_target: str = Field(default="", max_length=240)
    adrs: List[str] = Field(default_factory=list, max_length=12)


@dataclass(frozen=True)
class KnowledgeMatch:
    case: KnowledgeCase
    score: float
    shared_terms: Tuple[str, ...]


def cache_ineligibility_reasons(state: ProjectState) -> list[str]:
    """返回不能沉淀为可信案例的原因；空列表表示满足全部质量门。"""
    reasons = []
    if state.product_spec is None or state.architecture is None:
        reasons.append("缺少 Product Spec 或 Architecture")
    if not state.generated_files:
        reasons.append("没有生成文件")
    if state.build_passed is not True:
        reasons.append("构建验证未通过")
    if state.code_review is None or not state.code_review.passed:
        reasons.append("Reviewer 未通过")
    if state.security_report is None or not state.security_report.passed:
        reasons.append("Security 未通过")
    if state.phase != ProjectPhase.GATE_2_APPROVED or not state.gate_2_approved:
        reasons.append("Gate 2 未通过")
    if state.errors:
        reasons.append("流水线仍有错误")
    return reasons


def _sanitize_text(value: str, max_chars: int) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = _CONTROL_CHARS.sub("", text)
    text = _PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", text)
    text = _BEARER_TOKEN.sub("Bearer [REDACTED]", text)
    text = _EMAIL.sub("[REDACTED_EMAIL]", text)
    text = _CN_PHONE.sub("[REDACTED_PHONE]", text)
    text = _LONG_TOKEN.sub("[REDACTED]", text)
    return text.strip()[:max_chars]


def _sanitize_list(values: Sequence[str], *, limit: int, item_chars: int) -> list[str]:
    cleaned = []
    for value in values:
        item = _sanitize_text(value, item_chars)
        if item and item not in cleaned:
            cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _case_from_state(state: ProjectState) -> KnowledgeCase:
    spec = state.product_spec
    arch = state.architecture
    if spec is None or arch is None:  # 调用方通常已走质量门；保留明确异常供直接调用者诊断。
        raise ValueError("knowledge cache: 缺少 Product Spec 或 Architecture")

    stack = {}
    for key, value in list(arch.stack.items())[:12]:
        clean_key = _sanitize_text(key, 80)
        clean_value = _sanitize_text(value, 240)
        if clean_key and clean_value:
            stack[clean_key] = clean_value

    api_design = _sanitize_list(
        [f"{endpoint.method.upper()} {endpoint.path} — {endpoint.purpose}" for endpoint in arch.api_design],
        limit=20,
        item_chars=320,
    )
    adrs = _sanitize_list(
        [f"{adr.title}: {adr.decision}（{adr.rationale}）" for adr in arch.adrs],
        limit=12,
        item_chars=600,
    )
    return KnowledgeCase(
        project_name=_sanitize_text(spec.project_name, 160) or "redacted-project",
        one_liner=_sanitize_text(spec.one_liner, 600),
        core_features=_sanitize_list(spec.core_features, limit=12, item_chars=300),
        stack=stack,
        data_model=_sanitize_text(arch.data_model, 1600),
        api_design=api_design,
        deploy_target=_sanitize_text(arch.deploy_target, 240),
        adrs=adrs,
    )


def _sanitize_loaded_case(case: KnowledgeCase) -> KnowledgeCase:
    """缓存文件可能被人工编辑；读取侧再次脱敏，不能只信任写入路径。"""
    stack = {}
    for key, value in list(case.stack.items())[:12]:
        clean_key = _sanitize_text(key, 80)
        clean_value = _sanitize_text(value, 240)
        if clean_key and clean_value:
            stack[clean_key] = clean_value
    return KnowledgeCase(
        project_name=_sanitize_text(case.project_name, 160) or "redacted-project",
        one_liner=_sanitize_text(case.one_liner, 600),
        core_features=_sanitize_list(case.core_features, limit=12, item_chars=300),
        stack=stack,
        data_model=_sanitize_text(case.data_model, 1600),
        api_design=_sanitize_list(case.api_design, limit=20, item_chars=320),
        deploy_target=_sanitize_text(case.deploy_target, 240),
        adrs=_sanitize_list(case.adrs, limit=12, item_chars=600),
    )


def _case_filename(project_name: str) -> str:
    digest = hashlib.sha256(project_name.encode("utf-8")).hexdigest()[:16]
    return f"case-{digest}.json"


def save_knowledge_case(state: ProjectState, directory: Path | None = None) -> Path:
    """通过全部质量门后原子写入案例；不合格时抛 ValueError，绝不静默污染缓存。"""
    reasons = cache_ineligibility_reasons(state)
    if reasons:
        raise ValueError("knowledge cache: " + "；".join(reasons))

    case = _case_from_state(state)
    root = Path(directory or config.KNOWLEDGE_CACHE_DIR)
    if root.exists() and root.is_symlink():
        raise ValueError("knowledge cache: 缓存目录不能是符号链接")
    root.mkdir(parents=True, exist_ok=True)
    target = root / _case_filename(state.product_spec.project_name)
    payload = case.model_dump_json(indent=2)

    temp_path = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".knowledge-", suffix=".tmp", dir=root)
        os.close(fd)
        temp_path = Path(temp_name)
        temp_path.write_text(payload, encoding="utf-8")
        os.replace(temp_path, target)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return target


def load_knowledge_cases(directory: Path | None = None) -> list[KnowledgeCase]:
    """容错读取可信格式；损坏、超限、版本不兼容或符号链接案例全部跳过。"""
    root = Path(directory or config.KNOWLEDGE_CACHE_DIR)
    if not root.exists() or root.is_symlink() or not root.is_dir():
        return []

    cases = []
    for path in sorted(root.glob("case-*.json")):
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CASE_BYTES:
                continue
            case = KnowledgeCase.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValidationError):
            continue
        cases.append(_sanitize_loaded_case(case))
    return cases


def _normalise(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").casefold()


def _terms(values: Sequence[str]) -> set[str]:
    text = _normalise("\n".join(values))
    terms = {term for term in _LATIN_TERM.findall(text) if term not in _LATIN_STOP_WORDS}
    for sequence in _CJK_SEQUENCE.findall(text):
        for width in (2, 3):
            terms.update(sequence[i : i + width] for i in range(len(sequence) - width + 1))
    return {term for term in terms if term not in _CJK_STOP_TERMS}


def _spec_terms(spec: ProductSpec) -> set[str]:
    return _terms([spec.project_name, spec.one_liner, *spec.core_features, *spec.mvp_in_scope])


def _case_terms(case: KnowledgeCase) -> set[str]:
    return _terms([case.project_name, case.one_liner, *case.core_features])


def match_knowledge_cases(
    spec: ProductSpec | None,
    directory: Path | None = None,
    *,
    limit: int = MAX_KNOWLEDGE_MATCHES,
    min_shared_terms: int = 2,
) -> list[KnowledgeMatch]:
    """按二元/三元中文片段和英文词的余弦相似度检索，结果稳定且最多返回一个案例。"""
    if spec is None or limit <= 0:
        return []
    target_terms = _spec_terms(spec)
    if not target_terms:
        return []

    current_name = _normalise(spec.project_name).strip()
    ranked = []
    for case in load_knowledge_cases(directory):
        if _normalise(case.project_name).strip() == current_name:
            continue
        case_terms = _case_terms(case)
        shared = tuple(sorted(target_terms & case_terms))
        if len(shared) < max(2, min_shared_terms):
            continue
        score = len(shared) / math.sqrt(len(target_terms) * len(case_terms))
        match = KnowledgeMatch(case=case, score=score, shared_terms=shared)
        ranked.append((-score, -len(shared), _normalise(case.project_name), match))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    capped = min(limit, MAX_KNOWLEDGE_MATCHES)
    return [item[3] for item in ranked[:capped]]


def render_knowledge_context(matches: Sequence[KnowledgeMatch]) -> str:
    """渲染固定结构的精简参考，不把缓存内容解释为可执行指令。"""
    sections = []
    for match in matches[:MAX_KNOWLEDGE_MATCHES]:
        case = match.case
        lines = [
            f"### 已验证案例: {case.project_name}",
            f"- 产品摘要: {case.one_liner}",
            f"- 核心功能: {'；'.join(case.core_features)}",
            f"- 技术栈: {'；'.join(f'{key}={value}' for key, value in case.stack.items())}",
            f"- 数据模型: {case.data_model}",
            f"- API: {'；'.join(case.api_design)}",
            f"- 部署: {case.deploy_target}",
            f"- ADR: {'；'.join(case.adrs)}",
        ]
        sections.append("\n".join(line for line in lines if not line.endswith(": ")))
    return "\n\n".join(sections)[:MAX_CONTEXT_CHARS].rstrip()
