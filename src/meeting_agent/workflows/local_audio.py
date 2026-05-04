from __future__ import annotations

import json
import math
import struct
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from meeting_agent.audio import analyze_audio_levels, analyze_wav_quality, assess_capture_readiness, read_wav_info, write_wav_from_chunks
from meeting_agent.core.transcript import save_transcript
from meeting_agent.exporters.csv_exporter import ActionItemCSVExporter
from meeting_agent.exporters.html import HTMLExporter
from meeting_agent.exporters.json_exporter import write_json
from meeting_agent.exporters.markdown import MarkdownExporter
from meeting_agent.intelligence.rule_minutes import RuleBasedMinutesGenerator
from meeting_agent.intelligence.verifier import MinutesVerifier
from meeting_agent.providers.asr import SidecarTranscriptProvider
from meeting_agent.providers.asr.doctor import run_asr_doctor
from meeting_agent.providers.audio import AudioCaptureConfig, SimulatedAudioCaptureProvider
from meeting_agent.quality.gates import run_minutes_quality_gate, write_quality_gate_result
from meeting_agent.ui.demo_bundle import build_desktop_lite_bundle

@dataclass(frozen=True)
class LocalAudioWorkflowResult:
    status: str
    out_dir: str
    artifacts: dict[str, str] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    @property
    def score(self) -> float:
        if self.status == "pass":
            return 1.0
        if self.status == "warn":
            return 0.75
        return 0.0
    def to_dict(self) -> dict: return {**asdict(self), "score": self.score}
    def to_json(self) -> str: return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    def to_markdown(self) -> str:
        lines = ['# Local Audio Workflow Report','',f'- Status: `{self.status}`',f'- Output directory: `{self.out_dir}`','','## Summary']
        for k,v in self.summary.items(): lines.append(f'- {k}: `{v}`')
        lines.extend(['','## Artifacts','','| Name | Path |','|---|---|'])
        for k,v in sorted(self.artifacts.items()): lines.append(f'| {k} | `{v}` |')
        return '\n'.join(lines)+'\n'

def run_local_audio_workflow(out_dir: str | Path, *, session_id: str='desktop_alpha_simulated', total_ms: int=3000, chunk_ms: int=250, sample_rate_hz: int=16000, channels: int=1, sidecar_text: str | None=None, meeting_id: str='mtg_desktop_alpha_audio', title: str='Desktop Alpha Local Audio Workflow') -> LocalAudioWorkflowResult:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True); artifacts: dict[str,str] = {}
    wav_path = out/'audio.wav'; session_path = out/'audio_session.json'; info_path = out/'audio_info.json'; diag_path = out/'audio_diagnostics.json'; diag_md_path = out/'audio_diagnostics.md'; levels_path = out/'audio_levels.json'; levels_md_path = out/'audio_levels.md'; readiness_path = out/'capture_readiness.json'; doctor_path = out/'asr_doctor.json'; smoke_path = out/'asr_smoke.json'; sidecar_path = out/'audio.transcript.txt'; transcript_path = out/'meeting_from_audio.json'; minutes_json_path = out/'minutes.json'; minutes_md_path = out/'minutes.md'; minutes_html_path = out/'minutes.html'; verification_path = out/'verification.json'; quality_path = out/'quality_gate.json'; actions_path = out/'action_items.csv'; ui_dir = out/'desktop_lite'
    provider = SimulatedAudioCaptureProvider(total_ms=total_ms)
    config = AudioCaptureConfig(device_id='simulated:microphone', sample_rate_hz=sample_rate_hz, channels=channels, chunk_ms=chunk_ms, metadata={'duration_ms': total_ms, 'workflow': 'desktop_alpha'})
    chunks = list(provider.capture(config, session_id=session_id))
    info = write_wav_from_chunks(chunks, wav_path)
    manifest_payload = {
        'session_id': session_id,
        'provider_id': provider.id,
        'provider_name': provider.name,
        'config': config.to_dict(),
        'wav': info.to_dict(),
        'chunk_count': len(chunks),
        'duration_ms': info.duration_ms,
        'chunks': [chunk.to_public_dict() for chunk in chunks],
        'metadata': {'source': 'local_audio_workflow_precomputed_chunks', 'private_core_included': False},
    }
    session_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    artifacts.update({'audio_wav': str(wav_path), 'audio_session': str(session_path)})
    info_path.write_text(info.to_json()+'\n', encoding='utf-8'); artifacts['audio_info']=str(info_path)
    diag = analyze_wav_quality(wav_path); diag_path.write_text(diag.to_json()+'\n', encoding='utf-8'); diag_md_path.write_text(_diag_md(diag.to_dict()), encoding='utf-8'); artifacts['audio_diagnostics_json']=str(diag_path); artifacts['audio_diagnostics_md']=str(diag_md_path)
    levels = analyze_audio_levels(wav_path, window_ms=100); levels_path.write_text(levels.to_json()+'\n', encoding='utf-8'); levels_md_path.write_text(levels.to_markdown(), encoding='utf-8'); artifacts['audio_levels_json']=str(levels_path); artifacts['audio_levels_md']=str(levels_md_path)
    readiness = assess_capture_readiness(provider, config); readiness_path.write_text(readiness.to_json()+'\n', encoding='utf-8'); artifacts['capture_readiness']=str(readiness_path)
    doctor = run_asr_doctor('faster-whisper'); doctor_path.write_text(doctor.to_json()+'\n', encoding='utf-8'); artifacts['asr_doctor']=str(doctor_path)
    sidecar_text = sidecar_text or default_sidecar_text('v0.7'); sidecar_path.write_text(sidecar_text.rstrip()+'\n', encoding='utf-8'); artifacts['sidecar_transcript']=str(sidecar_path)
    transcript = SidecarTranscriptProvider(sidecar_path=sidecar_path).transcribe_file(str(wav_path), meeting_id=meeting_id, title=title); save_transcript(transcript, transcript_path); artifacts['transcript']=str(transcript_path)
    smoke = {'provider': 'sidecar_transcript', 'status': 'pass' if transcript.segments else 'fail', 'score': 1.0 if transcript.segments else 0.0, 'segments': len(transcript.segments), 'audio_path': str(wav_path), 'sidecar': str(sidecar_path), 'note': 'Deterministic Community smoke test. Production ASR providers plug into the same interface.'}
    smoke_path.write_text(json.dumps(smoke, ensure_ascii=False, indent=2)+'\n', encoding='utf-8'); artifacts['asr_smoke']=str(smoke_path)
    minutes = RuleBasedMinutesGenerator().generate(transcript); verification = MinutesVerifier().verify(transcript, minutes); gate = run_minutes_quality_gate(transcript, minutes, verification)
    write_json(minutes, minutes_json_path); MarkdownExporter().export(transcript, minutes, minutes_md_path); HTMLExporter().export(transcript, minutes, minutes_html_path); ActionItemCSVExporter().export(transcript, minutes, actions_path); write_json(verification, verification_path); write_quality_gate_result(gate, quality_path)
    artifacts.update({'minutes_json': str(minutes_json_path), 'minutes_md': str(minutes_md_path), 'minutes_html': str(minutes_html_path), 'verification': str(verification_path), 'minutes_quality_gate': str(quality_path), 'action_items_csv': str(actions_path)})
    extra = {'audio_info': info.to_dict(), 'audio_diagnostics': diag.to_dict(), 'audio_levels': levels.to_dict(), 'capture_readiness': readiness.to_dict(), 'asr_smoke': smoke, 'workflow': {'id': 'local_audio_workflow', 'status': 'pass' if gate.status == 'pass' and diag.status in {'pass','warn'} else 'warn', 'session_id': session_id, 'audio_session': manifest_payload, 'artifacts': artifacts}}
    build_desktop_lite_bundle(transcript, ui_dir, minutes=minutes, extra_payload=extra, bridge_enabled=True, bridge_url='http://127.0.0.1:8765'); artifacts['desktop_lite'] = str(ui_dir/'index.html')
    status = 'pass'
    if diag.status == 'fail' or gate.status == 'fail' or not transcript.segments: status = 'fail'
    elif diag.status == 'warn' or gate.status != 'pass': status = 'warn'
    summary = {'audio_duration_ms': info.duration_ms, 'audio_quality_status': diag.status, 'audio_level_frames': levels.frame_count, 'capture_readiness_status': readiness.status, 'transcript_segments': len(transcript.segments), 'action_items': len(minutes.action_items), 'decisions': len(minutes.decisions), 'quality_gate': gate.status}
    result = LocalAudioWorkflowResult(status, str(out), artifacts, summary); (out/'workflow_report.json').write_text(result.to_json()+'\n', encoding='utf-8'); (out/'workflow_report.md').write_text(result.to_markdown(), encoding='utf-8')
    return result


def _write_tone_wav(path: str | Path, *, duration_ms: int = 3000, sample_rate_hz: int = 16000, frequency_hz: float = 440.0) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(sample_rate_hz * max(1, duration_ms) / 1000)
    frames = bytearray()
    amplitude = 2500
    for i in range(total_samples):
        sample = int(amplitude * math.sin(2 * math.pi * frequency_hz * i / sample_rate_hz))
        frames.extend(struct.pack('<h', sample))
    with wave.open(str(out), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate_hz)
        wav.writeframes(bytes(frames))

def default_sidecar_text(version_label: str='v0.7') -> str:
    return '\n'.join([f'[00:00:00 - 00:00:01] 佐藤: {version_label}ではDesktop Alphaとして録音から議事録までのローカルワークフローを確認します。', '[00:00:01 - 00:00:02] 鈴木: 山田さん、金曜までにTauriブリッジの検証をお願いします。', '[00:00:02 - 00:00:03] 田中: PC内部音声取得はWindows、macOS、Linuxで方式が違うため継続調査が必要です。'])

def _diag_md(d: dict) -> str:
    warnings = d.get('warnings') or []
    return '\n'.join(['# Audio Diagnostics','',f"- Status: `{d.get('status')}`",f"- Score: `{d.get('score')}`",f"- Duration: `{d.get('duration_ms')} ms`",f"- RMS: `{d.get('rms_dbfs')} dBFS`",f"- Peak: `{d.get('peak_dbfs')} dBFS`",f"- Silence ratio: `{d.get('silence_ratio')}`",f"- Clipping ratio: `{d.get('clipping_ratio')}`",'','## Warnings'] + ([f'- {w}' for w in warnings] if warnings else ['- No warnings.']))+'\n'
