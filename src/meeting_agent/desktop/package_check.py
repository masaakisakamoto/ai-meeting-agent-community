from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class DesktopPackageCheckReport:
    status: str
    score: float
    checks: list[dict] = field(default_factory=list)
    recommendation: str = ""
    def to_dict(self): return {"status":self.status,"score":round(self.score,3),"checks":self.checks,"recommendation":self.recommendation}
    def to_json(self): return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    def to_markdown(self):
        lines=["# Desktop Package Check","",f"- Status: `{self.status}`",f"- Score: `{round(self.score,3)}`",f"- Recommendation: {self.recommendation}","","| Check | Status | Message |","|---|---|---|"]
        for c in self.checks: lines.append(f"| {c['name']} | `{c['status']}` | {c['message']} |")
        return "\n".join(lines)+"\n"

def run_desktop_package_check(root: str|Path=".") -> DesktopPackageCheckReport:
    root=Path(root); required=["apps/desktop-lite/README.md","apps/desktop-tauri/README.md","src/meeting_agent/ui/assets/index.html","src/meeting_agent/desktop/bridge.py","src/meeting_agent/desktop/packager.py"]
    checks=[]
    for rel in required:
        path=root/rel; checks.append({"name":rel,"status":"pass" if path.exists() else "warn","message":"present" if path.exists() else "missing optional desktop scaffold"})
    score=sum(1.0 if c['status']=='pass' else 0.5 for c in checks)/len(checks)
    status="pass" if score>=0.95 else "warn"
    return DesktopPackageCheckReport(status,score,checks,"Desktop alpha packaging scaffold is ready for developer preview." if status=="pass" else "Add missing desktop scaffold files before broad preview.")
