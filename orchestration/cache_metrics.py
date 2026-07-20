"""L2/L3 缓存可观测性：无额外 LLM 调用的命中、复用量与案例质量统计。"""
from __future__ import annotations

import hashlib
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Iterable, List, Literal, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from . import config
from .schemas import CacheLookup
from .state import ProjectState

METRIC_SCHEMA_VERSION = 1
MAX_METRIC_LINE_BYTES = 16 * 1024


class CacheLookupEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[METRIC_SCHEMA_VERSION] = METRIC_SCHEMA_VERSION
    event_type: Literal["lookup"] = "lookup"
    recorded_at: datetime
    source: Literal["l2", "l3", "miss"]
    match_ids: List[str] = Field(default_factory=list, max_length=2)
    context_chars: int = Field(default=0, ge=0)
    estimated_reused_tokens: int = Field(default=0, ge=0)


class CacheCaseSavedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[METRIC_SCHEMA_VERSION] = METRIC_SCHEMA_VERSION
    event_type: Literal["case_saved"] = "case_saved"
    recorded_at: datetime
    repair_attempts: int = Field(default=0, ge=0)
    review_rounds: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)


CacheMetricEvent = Annotated[
    Union[CacheLookupEvent, CacheCaseSavedEvent],
    Field(discriminator="event_type"),
]
_EVENT_ADAPTER = TypeAdapter(CacheMetricEvent)


class CacheMetricsSummary(BaseModel):
    lookups: int = 0
    l2_hits: int = 0
    l3_hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    l3_fallback_hit_rate: float = 0.0
    estimated_reused_tokens: int = 0
    saved_cases: int = 0
    avg_repair_attempts: float = 0.0
    avg_review_rounds: float = 0.0
    avg_warning_count: float = 0.0
    remediation_trend: Literal["improving", "stable", "declining", "insufficient_data"] = (
        "insufficient_data"
    )


def estimate_context_tokens(text: str) -> int:
    """粗估 context token：非 ASCII 字符按 1，ASCII 字符按每 4 个 1 token。

    该值用于比较缓存复用量，不是供应商账单数据。
    """
    if not text:
        return 0
    non_ascii = sum(not char.isascii() for char in text)
    ascii_chars = len(text) - non_ascii
    return non_ascii + math.ceil(ascii_chars / 4)


def make_cache_lookup(
    *,
    template_matches: Sequence[object] = (),
    knowledge_matches: Sequence[object] = (),
    context: str = "",
) -> CacheLookup:
    """从已完成的确定性匹配构造无业务文本的单次观测。"""
    if template_matches:
        source = "l2"
        match_ids = [match.template.id for match in template_matches[:2]]
    elif knowledge_matches:
        source = "l3"
        match_ids = []
        for match in knowledge_matches[:2]:
            name = match.case.project_name.casefold().encode("utf-8")
            match_ids.append(f"case-{hashlib.sha256(name).hexdigest()[:12]}")
    else:
        source = "miss"
        match_ids = []
    return CacheLookup(
        source=source,
        match_ids=match_ids,
        context_chars=len(context),
        estimated_reused_tokens=estimate_context_tokens(context),
    )


def append_metric_event(
    event: CacheLookupEvent | CacheCaseSavedEvent,
    path: Path | None = None,
) -> Path:
    """追加一条有版本的 JSONL 事件；拒绝符号链接与异常超长事件。"""
    target = Path(path or config.CACHE_METRICS_FILE)
    if target.is_symlink() or (target.parent.exists() and target.parent.is_symlink()):
        raise ValueError("cache metrics: 指标路径不能是符号链接")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = event.model_dump_json()
    if len(payload.encode("utf-8")) > MAX_METRIC_LINE_BYTES:
        raise ValueError("cache metrics: 单条指标事件过大")
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(payload + "\n")
    return target


def record_cache_lookup(
    lookup: CacheLookup,
    path: Path | None = None,
    *,
    recorded_at: datetime | None = None,
) -> CacheLookupEvent:
    event = CacheLookupEvent(
        recorded_at=recorded_at or datetime.now(timezone.utc),
        source=lookup.source,
        match_ids=lookup.match_ids,
        context_chars=lookup.context_chars,
        estimated_reused_tokens=lookup.estimated_reused_tokens,
    )
    append_metric_event(event, path)
    return event


def record_case_saved(
    state: ProjectState,
    path: Path | None = None,
    *,
    recorded_at: datetime | None = None,
) -> CacheCaseSavedEvent:
    """记录成功案例的修复负担；与案例本身共用同一质量门。"""
    from .knowledge_cache import cache_ineligibility_reasons

    reasons = cache_ineligibility_reasons(state)
    if reasons:
        raise ValueError("cache metrics: " + "；".join(reasons))
    event = CacheCaseSavedEvent(
        recorded_at=recorded_at or datetime.now(timezone.utc),
        repair_attempts=state.repair_attempts,
        review_rounds=state.review_rounds,
        warning_count=len(state.warnings),
    )
    append_metric_event(event, path)
    return event


def load_metric_events(path: Path | None = None) -> list[CacheLookupEvent | CacheCaseSavedEvent]:
    """逐行容错读取；损坏、未知版本、超长行和符号链接全部跳过。"""
    target = Path(path or config.CACHE_METRICS_FILE)
    if not target.exists() or target.is_symlink() or not target.is_file():
        return []

    events = []
    try:
        with target.open("rb") as handle:
            for raw_line in handle:
                if not raw_line.strip() or len(raw_line) > MAX_METRIC_LINE_BYTES:
                    continue
                try:
                    events.append(_EVENT_ADAPTER.validate_json(raw_line))
                except ValidationError:
                    continue
    except OSError:
        return []
    return events


def _average(values: Sequence[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def _remediation_trend(events: Sequence[CacheCaseSavedEvent]) -> str:
    if len(events) < 2:
        return "insufficient_data"
    midpoint = len(events) // 2
    previous = events[:midpoint][-10:]
    recent = events[midpoint:][-10:]

    def burden(items: Sequence[CacheCaseSavedEvent]) -> float:
        return _average(
            [item.repair_attempts + item.review_rounds + item.warning_count for item in items]
        )

    delta = burden(recent) - burden(previous)
    if abs(delta) < 1e-9:
        return "stable"
    return "improving" if delta < 0 else "declining"


def summarize_cache_metrics(events: Iterable[CacheMetricEvent]) -> CacheMetricsSummary:
    event_list = list(events)
    lookups = [event for event in event_list if isinstance(event, CacheLookupEvent)]
    cases = [event for event in event_list if isinstance(event, CacheCaseSavedEvent)]
    l2_hits = sum(event.source == "l2" for event in lookups)
    l3_hits = sum(event.source == "l3" for event in lookups)
    misses = sum(event.source == "miss" for event in lookups)
    hit_count = l2_hits + l3_hits
    fallback_count = l3_hits + misses
    return CacheMetricsSummary(
        lookups=len(lookups),
        l2_hits=l2_hits,
        l3_hits=l3_hits,
        misses=misses,
        hit_rate=hit_count / len(lookups) if lookups else 0.0,
        l3_fallback_hit_rate=l3_hits / fallback_count if fallback_count else 0.0,
        estimated_reused_tokens=sum(event.estimated_reused_tokens for event in lookups),
        saved_cases=len(cases),
        avg_repair_attempts=_average([event.repair_attempts for event in cases]),
        avg_review_rounds=_average([event.review_rounds for event in cases]),
        avg_warning_count=_average([event.warning_count for event in cases]),
        remediation_trend=_remediation_trend(cases),
    )


def format_cache_lookup(lookup: CacheLookup) -> str:
    if lookup.source == "miss":
        return "缓存未命中（L2 未命中，L3 回退也无匹配）"
    ids = ", ".join(lookup.match_ids)
    return (
        f"{lookup.source.upper()} 命中: {ids}；"
        f"复用 context ≈{lookup.estimated_reused_tokens} tokens（估算，非账单值）"
    )


def format_cache_metrics(summary: CacheMetricsSummary) -> str:
    trend_labels = {
        "improving": "改善",
        "stable": "持平",
        "declining": "恶化",
        "insufficient_data": "样本不足",
    }
    return "\n".join(
        [
            "缓存观测:",
            (
                f"- lookup {summary.lookups} 次；命中率 {summary.hit_rate:.1%} "
                f"(L2={summary.l2_hits}, L3={summary.l3_hits}, miss={summary.misses})"
            ),
            f"- L3 回退命中率 {summary.l3_fallback_hit_rate:.1%}",
            f"- 复用 context ≈{summary.estimated_reused_tokens} tokens（估算，非账单值）",
            (
                f"- 成功案例 {summary.saved_cases} 个；平均 repair={summary.avg_repair_attempts:.2f}, "
                f"review={summary.avg_review_rounds:.2f}, warnings={summary.avg_warning_count:.2f}；"
                f"修复负担趋势={trend_labels[summary.remediation_trend]}"
            ),
        ]
    )


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    as_json = "--json" in argv
    positional = [arg for arg in argv if not arg.startswith("--")]
    unknown = [arg for arg in argv if arg.startswith("--") and arg != "--json"]
    if unknown or len(positional) > 1:
        print("用法: python -m orchestration.cache_metrics [metrics.jsonl] [--json]")
        return 2
    path = Path(positional[0]) if positional else None
    summary = summarize_cache_metrics(load_metric_events(path))
    print(summary.model_dump_json(indent=2) if as_json else format_cache_metrics(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
