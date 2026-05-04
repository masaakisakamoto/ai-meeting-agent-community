from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal, Sequence

ReleaseProfile = Literal["developer-preview", "community-product"]
GateSeverity = Literal["blocker", "required", "recommended", "advisory"]
GateStatus = Literal["pass", "fail", "warning", "skip"]


@dataclass(frozen=True)
class GateCheck:
    id: str
    title: str
    severity: GateSeverity
    status: GateStatus
    message: str
    details: list[str] = field(default_factory=list)
    score_weight: float = 1.0

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def failed(self) -> bool:
        return self.status == "fail"


@dataclass(frozen=True)
class ReleaseGateReport:
    profile: ReleaseProfile
    repo_root: str
    status: str
    score: float
    summary: str
    checks: list[GateCheck]
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# OSS Release Gate Report",
            "",
            f"- Profile: `{self.profile}`",
            f"- Status: `{self.status}`",
            f"- Score: `{self.score:.1f}`",
            f"- Repository: `{self.repo_root}`",
            "",
            "## Summary",
            "",
            self.summary,
            "",
            "## Checks",
            "",
            "| ID | Severity | Status | Check | Message |",
            "|---|---|---|---|---|",
        ]
        for check in self.checks:
            lines.append(
                f"| `{check.id}` | {check.severity} | {check.status} | {check.title} | {check.message} |"
            )
            for detail in check.details[:8]:
                lines.append(f"|  |  |  |  | ↳ {detail} |")
            if len(check.details) > 8:
                lines.append(f"|  |  |  |  | ↳ ... and {len(check.details) - 8} more |")
        lines.extend(["", "## Next actions", ""])
        if self.next_actions:
            lines.extend(f"- {action}" for action in self.next_actions)
        else:
            lines.append("- None. This profile is release-ready.")
        return "\n".join(lines).rstrip() + "\n"


class ReleaseGateRunner:
    """Checks whether the public Community repository is ready to publish.

    The goal is intentionally conservative: this tool does not decide whether the
    commercial product is complete. It decides whether the current source bundle is
    safe, coherent, and honest enough for a specific release profile.
    """

    REQUIRED_DEV_PREVIEW_FILES = (
        "README.md",
        "LICENSE",
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "TRADEMARK.md",
        "pyproject.toml",
        "src/meeting_agent/core/schemas.py",
        "src/meeting_agent/core/plugins.py",
        "src/meeting_agent/core/transcript.py",
        "src/meeting_agent/intelligence/rule_minutes.py",
        "src/meeting_agent/intelligence/verifier.py",
        "src/meeting_agent/exporters/markdown.py",
        "src/meeting_agent/providers/asr/base.py",
        "src/meeting_agent/providers/llm/base.py",
        "examples/sample_meeting_ja.txt",
        "docs/ARCHITECTURE.md",
        "docs/OPEN_CORE_STRATEGY.md",
        "docs/OSS_COMPLIANCE.md",
        "docs/PRIVATE_CORE_BOUNDARIES.md",
        "docs/ROADMAP.md",
    )

    REQUIRED_PRODUCT_FILES = REQUIRED_DEV_PREVIEW_FILES + (
        "docs/OSS_RELEASE_CRITERIA.md",
        "docs/QUALITY_BAR.md",
    )

    PRODUCT_CAPABILITY_SENTINELS = (
        "src/meeting_agent/providers/asr/faster_whisper_provider.py",
        "src/meeting_agent/streaming/rolling_buffer.py",
    )

    EXCLUDED_DIRS = {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "dist",
        "build",
        "node_modules",
        "demo_out",
    }
    TEXT_EXTENSIONS = {
        "",
        ".cfg",
        ".css",
        ".csv",
        ".env",
        ".example",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".lock",
        ".md",
        ".py",
        ".rst",
        ".sh",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".yaml",
        ".yml",
    }
    SECRET_PATTERNS = (
        ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{20,}\b")),
        ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
        ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}\b")),
        ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----")),
    )

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()

    def run(self, profile: ReleaseProfile = "developer-preview", run_tests: bool = True) -> ReleaseGateReport:
        checks: list[GateCheck] = []
        checks.append(self._check_repo_root())
        checks.append(self._check_required_files(profile))
        checks.append(self._check_version_consistency())
        checks.append(self._check_secret_scan())
        checks.append(self._check_private_boundary())
        checks.append(self._check_demo_inputs())
        checks.append(self._check_tests_present())
        if run_tests:
            checks.append(self._check_unit_tests())
        else:
            checks.append(
                GateCheck(
                    id="tests.run",
                    title="Unit tests executed",
                    severity="required",
                    status="skip",
                    message="Skipped by caller.",
                )
            )
        if profile == "community-product":
            checks.append(self._check_product_capabilities())
            checks.append(self._check_product_honesty())

        score = _score(checks)
        status, summary = _classify(profile, checks, score)
        next_actions = _next_actions(profile, checks, status)
        return ReleaseGateReport(
            profile=profile,
            repo_root=str(self.repo_root),
            status=status,
            score=score,
            summary=summary,
            checks=checks,
            next_actions=next_actions,
        )

    def _check_repo_root(self) -> GateCheck:
        ok = (self.repo_root / "pyproject.toml").exists() and (self.repo_root / "src" / "meeting_agent").exists()
        return GateCheck(
            id="repo.root",
            title="Repository root detected",
            severity="blocker",
            status="pass" if ok else "fail",
            message="Repository root is valid." if ok else "pyproject.toml or src/meeting_agent is missing.",
        )

    def _check_required_files(self, profile: ReleaseProfile) -> GateCheck:
        required = self.REQUIRED_PRODUCT_FILES if profile == "community-product" else self.REQUIRED_DEV_PREVIEW_FILES
        missing = [path for path in required if not (self.repo_root / path).exists()]
        return GateCheck(
            id="repo.required_files",
            title="Required public repository files",
            severity="required",
            status="pass" if not missing else "fail",
            message="All required files are present." if not missing else f"Missing {len(missing)} required files.",
            details=missing,
            score_weight=2.0,
        )

    def _check_version_consistency(self) -> GateCheck:
        pyproject = self.repo_root / "pyproject.toml"
        init_py = self.repo_root / "src" / "meeting_agent" / "__init__.py"
        if not pyproject.exists() or not init_py.exists():
            return GateCheck(
                id="repo.version",
                title="Version consistency",
                severity="required",
                status="fail",
                message="Version files are missing.",
            )
        pyproject_text = pyproject.read_text(encoding="utf-8")
        init_text = init_py.read_text(encoding="utf-8")
        p_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE)
        i_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
        if not p_match or not i_match:
            return GateCheck(
                id="repo.version",
                title="Version consistency",
                severity="required",
                status="fail",
                message="Could not parse versions.",
            )
        ok = p_match.group(1) == i_match.group(1)
        return GateCheck(
            id="repo.version",
            title="Version consistency",
            severity="required",
            status="pass" if ok else "fail",
            message=(
                f"Version is consistent: {p_match.group(1)}."
                if ok
                else f"pyproject={p_match.group(1)} __init__={i_match.group(1)}"
            ),
        )

    def _check_secret_scan(self) -> GateCheck:
        findings: list[str] = []
        for path in self._iter_text_files():
            rel = path.relative_to(self.repo_root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for name, pattern in self.SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    # Keep reports safe: expose only file and pattern, not the value.
                    line_no = text.count("\n", 0, match.start()) + 1
                    findings.append(f"{rel}:{line_no} matched {name}")
        return GateCheck(
            id="security.secret_scan",
            title="No obvious secrets in public source",
            severity="blocker",
            status="pass" if not findings else "fail",
            message="No obvious secrets found." if not findings else f"Found {len(findings)} potential secret(s).",
            details=findings,
            score_weight=3.0,
        )

    def _check_private_boundary(self) -> GateCheck:
        forbidden_paths = []
        forbidden_names = {
            "private_evals",
            "private-evals",
            "quality-engine-private",
            "ai-meeting-agent-pro",
            "enterprise-secrets",
        }
        for path in self.repo_root.rglob("*"):
            if any(part in self.EXCLUDED_DIRS for part in path.parts):
                continue
            rel_parts = {part.lower() for part in path.relative_to(self.repo_root).parts}
            if rel_parts & forbidden_names:
                forbidden_paths.append(path.relative_to(self.repo_root).as_posix())
        return GateCheck(
            id="security.private_boundary",
            title="Private core not included in public repository",
            severity="blocker",
            status="pass" if not forbidden_paths else "fail",
            message=(
                "No private-core directories detected."
                if not forbidden_paths
                else f"Found {len(forbidden_paths)} private-core path(s)."
            ),
            details=forbidden_paths,
            score_weight=3.0,
        )

    def _check_demo_inputs(self) -> GateCheck:
        sample = self.repo_root / "examples" / "sample_meeting_ja.txt"
        if not sample.exists():
            return GateCheck(
                id="demo.input",
                title="Japanese demo transcript",
                severity="required",
                status="fail",
                message="examples/sample_meeting_ja.txt is missing.",
            )
        text = sample.read_text(encoding="utf-8")
        enough = len(text.strip()) >= 120 and "[00:" in text
        return GateCheck(
            id="demo.input",
            title="Japanese demo transcript",
            severity="required",
            status="pass" if enough else "warning",
            message="Demo transcript is present." if enough else "Demo transcript exists but looks too small.",
            score_weight=1.5,
        )

    def _check_tests_present(self) -> GateCheck:
        tests = sorted((self.repo_root / "tests").glob("test_*.py")) if (self.repo_root / "tests").exists() else []
        return GateCheck(
            id="tests.present",
            title="Unit tests committed",
            severity="required",
            status="pass" if tests else "fail",
            message=f"Found {len(tests)} test file(s)." if tests else "No tests/test_*.py files found.",
            details=[p.relative_to(self.repo_root).as_posix() for p in tests],
            score_weight=2.0,
        )

    def _check_unit_tests(self) -> GateCheck:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo_root / "src")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=self.repo_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
        output = proc.stdout.strip().splitlines()
        details = output[-12:]
        return GateCheck(
            id="tests.run",
            title="Unit tests executed",
            severity="required",
            status="pass" if proc.returncode == 0 else "fail",
            message="Unit tests passed." if proc.returncode == 0 else f"Unit tests failed with exit code {proc.returncode}.",
            details=details,
            score_weight=3.0,
        )

    def _check_product_capabilities(self) -> GateCheck:
        missing = [path for path in self.PRODUCT_CAPABILITY_SENTINELS if not (self.repo_root / path).exists()]
        # These files are sentinels, not proof that product UX is complete. Product profile remains conservative.
        return GateCheck(
            id="product.capability_sentinels",
            title="Product capability extension points",
            severity="recommended",
            status="pass" if not missing else "warning",
            message=(
                "Core product extension points are present."
                if not missing
                else f"Missing {len(missing)} product extension point(s)."
            ),
            details=missing,
            score_weight=1.5,
        )

    def _check_product_honesty(self) -> GateCheck:
        readme = self.repo_root / "README.md"
        if not readme.exists():
            return GateCheck(
                id="product.honesty",
                title="README accurately scopes current implementation",
                severity="required",
                status="fail",
                message="README is missing.",
            )
        text = readme.read_text(encoding="utf-8").lower()
        required_phrases = ["prototype", "live audio capture", "extension points"]
        missing = [phrase for phrase in required_phrases if phrase not in text]
        return GateCheck(
            id="product.honesty",
            title="README accurately scopes current implementation",
            severity="required",
            status="pass" if not missing else "fail",
            message=(
                "README clearly states prototype/extension-point status."
                if not missing
                else "README may overstate product readiness."
            ),
            details=missing,
            score_weight=2.0,
        )

    def _iter_text_files(self) -> Iterable[Path]:
        for path in self.repo_root.rglob("*"):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(self.repo_root).parts
            if any(part in self.EXCLUDED_DIRS for part in rel_parts):
                continue
            if path.suffix.lower() not in self.TEXT_EXTENSIONS:
                continue
            if path.stat().st_size > 750_000:
                continue
            yield path


def _score(checks: Sequence[GateCheck]) -> float:
    weighted_total = 0.0
    weighted_score = 0.0
    for check in checks:
        if check.status == "skip":
            continue
        weight = check.score_weight
        weighted_total += weight
        if check.status == "pass":
            weighted_score += weight
        elif check.status == "warning":
            weighted_score += weight * 0.5
        elif check.status == "fail":
            weighted_score += 0.0
    if weighted_total == 0:
        return 0.0
    return round(100.0 * weighted_score / weighted_total, 1)


def _classify(profile: ReleaseProfile, checks: Sequence[GateCheck], score: float) -> tuple[str, str]:
    blocker_failures = [c for c in checks if c.severity == "blocker" and c.failed]
    required_failures = [c for c in checks if c.severity == "required" and c.failed]
    warnings = [c for c in checks if c.status == "warning"]
    if blocker_failures:
        return "blocked", "Blocker checks failed. Do not publish this source bundle."
    if required_failures:
        return "not_ready", "Required checks failed. Keep this internal until they are fixed."
    if profile == "developer-preview":
        if score >= 90:
            return "developer_preview_ready", "Ready for a clearly labeled developer-preview OSS release."
        if score >= 75:
            return "developer_preview_candidate", "Close to developer-preview readiness; review warnings first."
        return "internal_alpha", "Useful internally, but not yet strong enough for public preview."
    # community-product is intentionally stricter; warnings keep it out of product-ready status.
    if score >= 92 and not warnings:
        return "community_product_ready", "Ready for a broader Community product OSS release."
    if score >= 82:
        return "community_product_candidate", "Close, but not yet polished enough for broad product-style OSS release."
    return "internal_alpha", "Architecture is useful, but product-style OSS release should wait."


def _next_actions(profile: ReleaseProfile, checks: Sequence[GateCheck], status: str) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check.status in {"fail", "warning"}:
            if check.id == "security.secret_scan":
                actions.append("Remove or rotate any detected credentials before any public release.")
            elif check.id == "security.private_boundary":
                actions.append("Move private-core directories/files out of the public repository.")
            elif check.id == "tests.run":
                actions.append("Fix failing tests and make the one-command demo pass on a clean machine.")
            elif check.id == "repo.required_files":
                actions.append("Add missing repository governance/docs files listed in the report.")
            elif check.id == "product.honesty":
                actions.append("Adjust README so current limitations are explicit and not marketed as complete.")
            elif check.id == "product.capability_sentinels":
                actions.append("Add or document the missing product extension points.")
            else:
                actions.append(f"Resolve check `{check.id}`: {check.message}")
    if profile == "developer-preview" and status == "developer_preview_ready":
        actions.append("Publish only as `developer preview` or `pre-alpha`; avoid claiming full product readiness.")
        actions.append("Before pushing to GitHub, create a fresh repo, run this gate again, and verify git history contains no secrets.")
    if profile == "community-product" and status != "community_product_ready":
        actions.append("Do not market this as a finished OSS product yet; continue with live audio, local ASR, and UX hardening.")
    # Dedupe while preserving order.
    deduped = []
    seen = set()
    for action in actions:
        if action not in seen:
            deduped.append(action)
            seen.add(action)
    return deduped


def write_report(report: ReleaseGateReport, out_json: str | Path | None = None, out_md: str | Path | None = None) -> None:
    if out_json:
        path = Path(out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_json() + "\n", encoding="utf-8")
    if out_md:
        path = Path(out_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")
