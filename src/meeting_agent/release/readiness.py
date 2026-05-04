from __future__ import annotations

import compileall
import io
import json
import os
import unittest
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

from meeting_agent.core.schemas import utc_now_iso

CheckStatus = Literal["pass", "warn", "fail"]
ReleaseProfile = Literal["portfolio_preview", "public_oss"]

REQUIRED_PUBLIC_FILES = [
    "LICENSE",
    "NOTICE",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "TRADEMARK.md",
    "pyproject.toml",
    "docs/ARCHITECTURE.md",
    "docs/OPEN_CORE_STRATEGY.md",
    "docs/PRIVATE_CORE_BOUNDARIES.md",
    "docs/OSS_COMPLIANCE.md",
    "docs/ROADMAP.md",
]

RECOMMENDED_PUBLIC_FILES = [
    "docs/OSS_RELEASE_CHECKLIST.md",
    "docs/QUALITY_BAR.md",
    "docs/PLUGIN_SYSTEM.md",
    "examples/README.md",
    ".github/workflows/ci.yml",
]

SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"OPENAI_API_KEY\s*=\s*['\"]?sk-[A-Za-z0-9_\-]{20,}", "OpenAI API key assignment"),
    (r"sk-[A-Za-z0-9_\-]{20,}", "OpenAI-style secret key"),
    (r"xox[baprs]-[A-Za-z0-9\-]{20,}", "Slack token"),
    (r"gh[pousr]_[A-Za-z0-9_]{20,}", "GitHub token"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----", "private key block"),
]

TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build", "node_modules"}
SKIP_SUFFIXES = {".zip", ".gz", ".tar", ".png", ".jpg", ".jpeg", ".wav", ".mp3", ".mp4", ".pyc", ".sqlite"}


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    name: str
    status: CheckStatus
    detail: str
    category: str = "general"
    severity: str = "medium"
    remediation: str = ""


@dataclass
class ReleaseReadinessReport:
    project: str
    status: str
    score: float
    generated_at: str = field(default_factory=utc_now_iso)
    profile: ReleaseProfile = "public_oss"
    checks: list[ReadinessCheck] = field(default_factory=list)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            f"# OSS release readiness: {self.project}",
            "",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score:.2f}`",
            f"- Profile: `{self.profile}`",
            f"- Generated at: `{self.generated_at}`",
            f"- Recommendation: {self.recommendation}",
            "",
            "## Checks",
            "",
            "| Status | Severity | Category | ID | Check | Detail | Remediation |",
            "|---|---|---|---|---|---|---|",
        ]
        for check in self.checks:
            lines.append(
                "| "
                + " | ".join(
                    [
                        check.status,
                        check.severity,
                        _escape_md(check.category),
                        _escape_md(check.id),
                        _escape_md(check.name),
                        _escape_md(check.detail),
                        _escape_md(check.remediation),
                    ]
                )
                + " |"
            )
        return "\n".join(lines) + "\n"


# Backward-compatible alias expected by earlier code.
OSSReadinessReport = ReleaseReadinessReport
OSSReadinessCheck = ReadinessCheck


def run_readiness_checks(
    root: str | Path,
    *,
    profile: ReleaseProfile = "public_oss",
    run_tests: bool = False,
) -> ReleaseReadinessReport:
    root_path = Path(root).resolve()
    checks: list[ReadinessCheck] = []
    checks.append(_check_required_files(root_path))
    checks.append(_check_recommended_files(root_path))
    checks.append(_check_required_dirs(root_path))
    checks.append(_check_private_core_boundary(root_path))
    checks.append(_check_private_leakage(root_path))
    checks.append(_check_manifest(root_path))
    checks.append(_check_package_metadata(root_path))
    checks.append(_check_examples(root_path))
    checks.append(_check_compile(root_path))
    if run_tests:
        checks.append(_check_unit_tests(root_path))

    score = _score(checks)
    failures = [c for c in checks if c.status == "fail"]
    warnings = [c for c in checks if c.status == "warn"]
    if failures:
        status = "needs_work"
        recommendation = "Do not publish yet. Fix failed release gates first."
    elif profile == "portfolio_preview" and warnings:
        status = "portfolio_preview_ready"
        recommendation = "Safe for a portfolio/private preview with visible caveats."
    else:
        status = "pass"
        recommendation = "Ready for a controlled OSS publication review."
    return ReleaseReadinessReport(
        project=_project_name(root_path),
        status=status,
        score=score,
        profile=profile,
        checks=checks,
        recommendation=recommendation,
    )


def run_release_readiness(root: str | Path, *, profile: ReleaseProfile = "public_oss", run_tests: bool = False) -> ReleaseReadinessReport:
    return run_readiness_checks(root, profile=profile, run_tests=run_tests)


def assess_oss_readiness(root: str | Path) -> ReleaseReadinessReport:
    return run_readiness_checks(root, profile="public_oss", run_tests=False)


def write_readiness_report(report: ReleaseReadinessReport, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    else:
        path.write_text(report.to_markdown(), encoding="utf-8")

def render_readiness_markdown(report: ReleaseReadinessReport) -> str:
    return report.to_markdown()


def run_oss_readiness_check(root: str | Path) -> ReleaseReadinessReport:
    return run_readiness_checks(root)


def scan_for_secrets(root: str | Path) -> list[ReadinessCheck]:
    return [_check_private_leakage(Path(root).resolve())]


def _check_required_files(root: Path) -> ReadinessCheck:
    missing = [rel for rel in REQUIRED_PUBLIC_FILES if not (root / rel).is_file()]
    return ReadinessCheck(
        id="required_public_files",
        name="Required public repository files",
        status="pass" if not missing else "fail",
        category="release_hygiene",
        severity="high",
        detail="All required files are present." if not missing else "Missing: " + ", ".join(missing),
        remediation="Create the missing files before public OSS release." if missing else "",
    )


def _check_recommended_files(root: Path) -> ReadinessCheck:
    missing = [rel for rel in RECOMMENDED_PUBLIC_FILES if not (root / rel).is_file()]
    return ReadinessCheck(
        id="recommended_public_files",
        name="Recommended public repository files",
        status="pass" if not missing else "warn",
        category="release_hygiene",
        severity="medium",
        detail="All recommended files are present." if not missing else "Missing recommended files: " + ", ".join(missing),
        remediation="Add these before a broad launch announcement." if missing else "",
    )


def _check_required_dirs(root: Path) -> ReadinessCheck:
    required_dirs = ["src/meeting_agent", "tests", "examples", "docs"]
    missing = [rel for rel in required_dirs if not (root / rel).is_dir()]
    return ReadinessCheck(
        id="required_public_dirs",
        name="Required public repository directories",
        status="pass" if not missing else "fail",
        category="release_hygiene",
        severity="high",
        detail="All required directories are present." if not missing else "Missing: " + ", ".join(missing),
        remediation="Create the missing directories before public release." if missing else "",
    )


def _check_private_core_boundary(root: Path) -> ReadinessCheck:
    path = root / "docs" / "PRIVATE_CORE_BOUNDARIES.md"
    if not path.is_file():
        return ReadinessCheck(
            id="private_core_boundary_doc",
            name="Private core boundary documentation",
            status="fail",
            category="commercial_guardrails",
            severity="high",
            detail="docs/PRIVATE_CORE_BOUNDARIES.md is missing.",
            remediation="Document what remains private before opening the repository.",
        )
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    required_terms = ["quality engine", "model router", "verifier", "evaluation"]
    missing = [term for term in required_terms if term not in text]
    return ReadinessCheck(
        id="private_core_boundary_doc",
        name="Private core boundary documentation",
        status="pass" if not missing else "warn",
        category="commercial_guardrails",
        severity="medium",
        detail="Boundary is explicit." if not missing else "Missing concepts: " + ", ".join(missing),
        remediation="Clarify private/commercial boundaries." if missing else "",
    )


def _check_private_leakage(root: Path) -> ReadinessCheck:
    findings: list[str] = []
    private_dirs = ["private", "private_evals", "ai-meeting-agent-pro", "quality_engine_private"]
    for rel in private_dirs:
        if (root / rel).exists():
            findings.append(f"private directory present: {rel}")
    for path in _iter_text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = path.relative_to(root).as_posix()
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, text):
                findings.append(f"{rel}: {label}")
    return ReadinessCheck(
        id="private_leakage_scan",
        name="Private code and secret leakage scan",
        status="pass" if not findings else "fail",
        category="security",
        severity="high",
        detail="No private-looking directories or high-confidence secret patterns found." if not findings else "; ".join(findings[:10]),
        remediation="Remove private code/secrets, rotate credentials, and commit safe examples only." if findings else "",
    )


def _check_manifest(root: Path) -> ReadinessCheck:
    manifest = root / "MANIFEST.txt"
    if not manifest.is_file():
        return ReadinessCheck(
            id="manifest_present",
            name="Source manifest",
            status="warn",
            category="release_hygiene",
            severity="low",
            detail="MANIFEST.txt is missing.",
            remediation="Generate a manifest before release.",
        )
    return ReadinessCheck(
        id="manifest_present",
        name="Source manifest",
        status="pass",
        category="release_hygiene",
        severity="low",
        detail="MANIFEST.txt is present.",
    )


def _check_package_metadata(root: Path) -> ReadinessCheck:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return ReadinessCheck(
            id="package_metadata",
            name="Package metadata",
            status="fail",
            category="packaging",
            severity="high",
            detail="pyproject.toml is missing.",
            remediation="Add package metadata before release.",
        )
    text = pyproject.read_text(encoding="utf-8", errors="ignore")
    missing = []
    for token in ["name", "version", "license", "requires-python"]:
        if token not in text:
            missing.append(token)
    return ReadinessCheck(
        id="package_metadata",
        name="Package metadata",
        status="pass" if not missing else "warn",
        category="packaging",
        severity="medium",
        detail="Core metadata is present." if not missing else "Missing metadata tokens: " + ", ".join(missing),
        remediation="Complete pyproject metadata." if missing else "",
    )


def _check_examples(root: Path) -> ReadinessCheck:
    examples = list((root / "examples").glob("*")) if (root / "examples").is_dir() else []
    return ReadinessCheck(
        id="examples_present",
        name="Examples and sample data",
        status="pass" if examples else "warn",
        category="developer_experience",
        severity="low",
        detail=f"{len(examples)} example files found.",
        remediation="Add a Japanese sample transcript and glossary." if not examples else "",
    )


def _check_compile(root: Path) -> ReadinessCheck:
    if os.environ.get("MEETING_AGENT_SKIP_NESTED_COMPILE") == "1":
        return ReadinessCheck(
            id="python_compile",
            name="Python source compile check",
            status="pass",
            category="verification",
            severity="high",
            detail="compile check skipped in nested release-test subprocess; outer release-check already compiled source.",
        )
    src = root / "src"
    if not src.is_dir():
        return ReadinessCheck(
            id="python_compile",
            name="Python source compile check",
            status="fail",
            category="verification",
            severity="high",
            detail="src directory missing.",
            remediation="Restore source tree.",
        )
    ok = compileall.compile_dir(str(src), quiet=1)
    return ReadinessCheck(
        id="python_compile",
        name="Python source compile check",
        status="pass" if ok else "fail",
        category="verification",
        severity="high",
        detail="compileall passed." if ok else "compileall failed",
        remediation="Fix syntax/import errors." if not ok else "",
    )


def _check_unit_tests(root: Path) -> ReadinessCheck:
    if os.environ.get("MEETING_AGENT_SKIP_NESTED_UNIT_TESTS") == "1":
        return ReadinessCheck(
            id="unit_tests",
            name="Unit tests",
            status="pass",
            category="verification",
            severity="high",
            detail="nested unit-test execution skipped to prevent recursive readiness checks; outer test run covers the suite.",
        )
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return ReadinessCheck(
            id="unit_tests",
            name="Unit tests",
            status="fail",
            category="verification",
            severity="high",
            detail="tests directory missing",
            remediation="Add a test suite before release.",
        )

    old_path = list(sys.path)
    old_skip_demo_aux = os.environ.get("MEETING_AGENT_SKIP_DEMO_AUX")
    old_skip_nested_compile = os.environ.get("MEETING_AGENT_SKIP_NESTED_COMPILE")
    old_skip_nested_unit_tests = os.environ.get("MEETING_AGENT_SKIP_NESTED_UNIT_TESTS")
    old_skip_desktop_smoke = os.environ.get("MEETING_AGENT_SKIP_DESKTOP_SMOKE")
    sys.path.insert(0, str(root / "src"))
    os.environ["MEETING_AGENT_SKIP_DEMO_AUX"] = "1"
    os.environ["MEETING_AGENT_SKIP_NESTED_COMPILE"] = "1"
    os.environ["MEETING_AGENT_SKIP_NESTED_UNIT_TESTS"] = "1"
    os.environ["MEETING_AGENT_SKIP_DESKTOP_SMOKE"] = "1"
    stream = io.StringIO()
    try:
        suite = unittest.defaultTestLoader.discover(str(tests_dir))
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    finally:
        sys.path[:] = old_path
        if old_skip_demo_aux is None:
            os.environ.pop("MEETING_AGENT_SKIP_DEMO_AUX", None)
        else:
            os.environ["MEETING_AGENT_SKIP_DEMO_AUX"] = old_skip_demo_aux
        if old_skip_nested_compile is None:
            os.environ.pop("MEETING_AGENT_SKIP_NESTED_COMPILE", None)
        else:
            os.environ["MEETING_AGENT_SKIP_NESTED_COMPILE"] = old_skip_nested_compile
        if old_skip_nested_unit_tests is None:
            os.environ.pop("MEETING_AGENT_SKIP_NESTED_UNIT_TESTS", None)
        else:
            os.environ["MEETING_AGENT_SKIP_NESTED_UNIT_TESTS"] = old_skip_nested_unit_tests
        if old_skip_desktop_smoke is None:
            os.environ.pop("MEETING_AGENT_SKIP_DESKTOP_SMOKE", None)
        else:
            os.environ["MEETING_AGENT_SKIP_DESKTOP_SMOKE"] = old_skip_desktop_smoke

    output = stream.getvalue().strip()
    ok = result.wasSuccessful()
    detail = f"{result.testsRun} tests passed" if ok else output[-1000:]
    return ReadinessCheck(
        id="unit_tests",
        name="Unit tests",
        status="pass" if ok else "fail",
        category="verification",
        severity="high",
        detail=detail,
        remediation="Fix failing tests before release." if not ok else "",
    )


def _score(checks: Iterable[ReadinessCheck]) -> float:
    earned = 0.0
    total = 0.0
    for check in checks:
        weight = {"low": 0.5, "medium": 1.0, "high": 2.0}.get(check.severity, 1.0)
        total += weight
        if check.status == "pass":
            earned += weight
        elif check.status == "warn":
            earned += weight * 0.65
    return round(earned / total if total else 0.0, 4)


def _project_name(root: Path) -> str:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return root.name
    text = pyproject.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'^name\s*=\s*["\']([^"\']+)["\']', text, flags=re.MULTILINE)
    return match.group(1) if match else root.name


def _iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & SKIP_DIRS:
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.stat().st_size > 1_000_000:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE", "NOTICE", "MANIFEST.txt"}:
            yield path


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")

