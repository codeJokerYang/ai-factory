"""Security：规则扫描（0 token）+ SecurityAgent（高危才调 LLM，一票否决）+ Gate 2 摘要。"""
from orchestration.agents.security import SecurityAgent
from orchestration.gate2 import summarize_build
from orchestration.llm import MockLLM
from orchestration.schemas import GeneratedFile, ProductSpec, SecurityFinding, SecurityReport
from orchestration.security import is_blocking, max_severity, scan_files
from orchestration.state import ProjectState


def test_scan_detects_hardcoded_secret():
    findings = scan_files([("app/page.tsx", 'const apiKey = "sk_live_abcdef1234567890"')])
    assert any(x.kind == "hardcoded-secret" and x.severity == "high" for x in findings)


def test_scan_detects_private_key_critical():
    findings = scan_files([("lib/x.ts", "-----BEGIN PRIVATE KEY-----\nABC")])
    assert any(x.severity == "critical" for x in findings)


def test_scan_detects_dangerous_usage():
    findings = scan_files([("app/page.tsx", "<div dangerouslySetInnerHTML={{__html:x}}/>; eval(y)")])
    kinds = {x.kind for x in findings}
    assert "xss-risk" in kinds and "eval" in kinds


def test_scan_detects_next_public_secret_leak():
    findings = scan_files([("lib/sb.ts", "process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE")])
    assert any(x.kind == "client-secret-leak" for x in findings)


def test_scan_clean_code_no_findings():
    assert scan_files([("app/page.tsx", "export default function P(){return <main>hi</main>}")]) == []


def test_max_severity_and_blocking():
    findings = [SecurityFinding(severity="medium", kind="eval"), SecurityFinding(severity="high", kind="x")]
    assert max_severity(findings) == "high"
    assert is_blocking(findings) is True
    assert is_blocking([SecurityFinding(severity="medium", kind="eval")]) is False


def _state(content):
    return ProjectState(
        project_id="t",
        idea="i",
        product_spec=ProductSpec(project_name="p", one_liner="o", target_users="u"),
        generated_files=[GeneratedFile(path="app/page.tsx", content=content)],
    )


def test_security_agent_clean_passes_no_llm():
    llm = MockLLM()
    st = _state("export default function P(){return <main>hi</main>}")
    SecurityAgent(llm).run(st)
    assert st.security_report.passed is True
    assert st.security_report.risk_level == "none"
    assert llm.calls == []  # 零 token 路径：无高危不调 LLM


def test_security_agent_high_blocks_and_calls_llm():
    llm = MockLLM(responses={"[agent:security]": "硬编码密钥，风险高，应改用环境变量。"})
    st = _state('const apiKey = "sk_live_abcdefghijklmnop"')
    SecurityAgent(llm).run(st)
    assert st.security_report.passed is False
    assert st.security_report.risk_level in ("high", "critical")
    assert len(llm.calls) == 1
    assert "环境变量" in st.security_report.summary


def test_security_agent_no_files_skips():
    llm = MockLLM()
    st = ProjectState(project_id="t", idea="i")
    SecurityAgent(llm).run(st)
    assert st.security_report is None
    assert llm.calls == []


def test_gate2_summary_includes_security():
    st = _state("clean")
    st.security_report = SecurityReport(
        passed=False,
        risk_level="high",
        findings=[SecurityFinding(severity="high", file="app/page.tsx", kind="hardcoded-secret", message="m")],
    )
    out = summarize_build(st)
    assert "Security" in out and "一票否决" in out and "hardcoded-secret" in out
