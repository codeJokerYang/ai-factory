"""Unit, HTTP integration and boundary coverage for the local web console."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from orchestration.web_console import (
    ConsoleInputError,
    MAX_IDEA_LENGTH,
    create_server,
    infer_features,
    run_mock_pipeline,
)


@pytest.fixture
def console_url():
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _post_json(url: str, payload: bytes):
    request = Request(
        f"{url}/api/runs",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urlopen(request, timeout=5)  # noqa: S310 - fixture binds to loopback only


def test_mock_pipeline_runs_real_agents_through_builder_and_quality_gates():
    result = run_mock_pipeline("做一个帮助自由职业者管理预算的记账工具")

    assert result["status"] == "completed"
    assert [stage["id"] for stage in result["stages"]] == [
        "planner",
        "architect",
        "decomposer",
        "gate-1",
        "builder",
        "reviewer",
        "security",
    ]
    assert result["product_spec"]["one_liner"] == "做一个帮助自由职业者管理预算的记账工具"
    assert result["product_spec"]["core_features"] == ["快速记账", "分类统计", "预算提醒"]
    assert len(result["dag"]["nodes"]) == 12
    assert result["generated_files"][0]["path"] == "app/page.tsx"
    assert result["quality"]["ui"]["passed"] is True
    assert result["quality"]["review"]["passed"] is True
    assert result["quality"]["security"]["passed"] is True
    assert result["llm_calls"] == 5


def test_feature_inference_has_domain_specific_and_fallback_paths():
    assert infer_features("大学生简历优化") == ["简历资料管理", "职位匹配评分", "优化建议"]
    assert infer_features("一个从未见过的创意") == ["核心流程工作台", "进度与状态追踪", "结果摘要"]


@pytest.mark.parametrize("idea", [None, "", "   ", 42])
def test_mock_pipeline_rejects_empty_or_non_string_ideas(idea):
    with pytest.raises(ConsoleInputError, match="请输入"):
        run_mock_pipeline(idea)


def test_mock_pipeline_rejects_oversized_idea():
    with pytest.raises(ConsoleInputError, match=str(MAX_IDEA_LENGTH)):
        run_mock_pipeline("想" * (MAX_IDEA_LENGTH + 1))


def test_health_endpoint_and_pipeline_http_integration(console_url):
    with urlopen(f"{console_url}/api/health", timeout=5) as response:  # noqa: S310
        health = json.load(response)
        assert response.status == 200
        assert response.headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert health == {"status": "ok", "mode": "mock", "api_key_required": False}

    with _post_json(
        console_url,
        json.dumps({"idea": "做一个小团队任务看板"}, ensure_ascii=False).encode("utf-8"),
    ) as response:
        result = json.load(response)
        assert response.status == 200
    assert result["status"] == "completed"
    assert result["product_spec"]["core_features"][0] == "任务工作台"


def test_http_endpoint_returns_structured_validation_error(console_url):
    with pytest.raises(HTTPError) as exc_info:
        _post_json(console_url, b'{"idea":""}')

    assert exc_info.value.code == 422
    payload = json.load(exc_info.value)
    assert payload["error"]["code"] == "validation_error"
    assert "请输入" in payload["error"]["message"]


def test_http_endpoint_rejects_invalid_json(console_url):
    with pytest.raises(HTTPError) as exc_info:
        _post_json(console_url, b"not-json")

    assert exc_info.value.code == 400
    assert json.load(exc_info.value)["error"]["code"] == "invalid_json"


def test_frontend_exposes_operable_and_accessible_controls():
    root = Path(__file__).resolve().parents[1] / "web_console"
    html = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "app.js").read_text(encoding="utf-8")
    styles = (root / "styles.css").read_text(encoding="utf-8")

    assert 'id="run-form"' in html
    assert 'id="idea"' in html
    assert 'role="tablist"' in html
    assert 'aria-live="polite"' in html
    assert 'fetch("/api/runs"' in script
    assert 'fetch("/api/health"' in script
    assert "[hidden] { display: none !important; }" in styles
    assert ".timeline li { min-width: 104px; }" in styles
    assert "@media (max-width: 620px)" in styles
    assert ":focus-visible" in styles
