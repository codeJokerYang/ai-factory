import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orchestration.cache_metrics import (
    CacheCaseSavedEvent,
    CacheLookupEvent,
    append_metric_event,
    estimate_context_tokens,
    format_cache_lookup,
    load_metric_events,
    record_case_saved,
    summarize_cache_metrics,
)
from orchestration.schemas import (
    Architecture,
    CacheLookup,
    CodeReview,
    GeneratedFile,
    ProductSpec,
    SecurityReport,
)
from orchestration.state import ProjectPhase, ProjectState

NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _lookup_event(source="miss", tokens=0):
    return CacheLookupEvent(
        recorded_at=NOW,
        source=source,
        match_ids=["auth"] if source == "l2" else [],
        context_chars=tokens * 4,
        estimated_reused_tokens=tokens,
    )


def _case_event(repairs=0, reviews=0, warnings=0):
    return CacheCaseSavedEvent(
        recorded_at=NOW,
        repair_attempts=repairs,
        review_rounds=reviews,
        warning_count=warnings,
    )


def _approved_state():
    return ProjectState(
        project_id="p1",
        idea="idea",
        phase=ProjectPhase.GATE_2_APPROVED,
        product_spec=ProductSpec(project_name="demo", one_liner="x", target_users="u"),
        architecture=Architecture(stack={"frontend": "Next.js"}, deploy_target="Vercel"),
        generated_files=[GeneratedFile(path="app/page.tsx", content="ok")],
        build_passed=True,
        code_review=CodeReview(passed=True),
        security_report=SecurityReport(passed=True),
        gate_2_approved=True,
        repair_attempts=1,
        review_rounds=2,
        warnings=["advisory"],
    )


def test_estimates_reused_context_tokens_and_formats_lookup():
    assert estimate_context_tokens("abcd中文") == 3
    lookup = CacheLookup(
        source="l2",
        match_ids=["auth", "dashboard"],
        context_chars=24,
        estimated_reused_tokens=8,
    )

    rendered = format_cache_lookup(lookup)

    assert "L2 命中" in rendered
    assert "auth, dashboard" in rendered
    assert "≈8" in rendered


def test_append_and_load_skips_corrupt_unknown_and_oversized_lines(tmp_path):
    path = tmp_path / "cache-metrics.jsonl"
    append_metric_event(_lookup_event("l2", 12), path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("{\n")
        handle.write(json.dumps({"schema_version": 99, "event_type": "lookup"}) + "\n")
        handle.write("x" * (17 * 1024) + "\n")

    events = load_metric_events(path)

    assert len(events) == 1
    assert isinstance(events[0], CacheLookupEvent)
    assert events[0].source == "l2"


def test_summary_reports_hit_rates_reuse_and_quality_trend():
    events = [
        _lookup_event("l2", 12),
        _lookup_event("l3", 20),
        _lookup_event("miss"),
        _lookup_event("miss"),
        _case_event(repairs=2, reviews=1, warnings=1),
        _case_event(repairs=0, reviews=0, warnings=0),
    ]

    summary = summarize_cache_metrics(events)

    assert summary.lookups == 4
    assert summary.hit_rate == pytest.approx(0.5)
    assert summary.l3_fallback_hit_rate == pytest.approx(1 / 3)
    assert summary.estimated_reused_tokens == 32
    assert summary.saved_cases == 2
    assert summary.avg_repair_attempts == pytest.approx(1.0)
    assert summary.remediation_trend == "improving"


def test_record_case_saved_captures_quality_counters(tmp_path):
    path = tmp_path / "cache-metrics.jsonl"

    event = record_case_saved(_approved_state(), path, recorded_at=NOW)

    assert event.repair_attempts == 1
    assert event.review_rounds == 2
    assert event.warning_count == 1
    assert load_metric_events(path) == [event]


def test_record_case_saved_rejects_ineligible_state_without_writing(tmp_path):
    state = _approved_state()
    state.security_report.passed = False
    path = tmp_path / "cache-metrics.jsonl"

    with pytest.raises(ValueError, match="Security"):
        record_case_saved(state, path, recorded_at=NOW)

    assert not path.exists()


def test_missing_empty_and_symlink_metric_files_fail_safe(tmp_path, monkeypatch):
    assert load_metric_events(tmp_path / "missing.jsonl") == []
    empty = tmp_path / "empty.jsonl"
    empty.touch()
    assert load_metric_events(empty) == []

    target = tmp_path / "target.jsonl"
    target.touch()
    link = tmp_path / "link.jsonl"
    try:
        link.symlink_to(target)
    except OSError:
        # Windows 未启用开发者模式时不能创建 symlink；保留同一读写分支的行为验证。
        link.touch()
        original_is_symlink = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda self: self == link or original_is_symlink(self),
        )

    assert load_metric_events(link) == []
    with pytest.raises(ValueError, match="符号链接"):
        append_metric_event(_lookup_event(), link)
