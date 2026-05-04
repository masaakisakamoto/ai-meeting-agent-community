from __future__ import annotations

import json
import math
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

_PCM16_MAX = 32768.0

@dataclass(frozen=True)
class AudioLevelFrame:
    index: int
    start_ms: int
    end_ms: int
    rms_linear: float
    peak_linear: float
    rms_dbfs: float
    peak_dbfs: float
    clipping_ratio: float
    is_speech_like: bool
    def to_dict(self) -> dict: return asdict(self)

@dataclass(frozen=True)
class AudioLevelReport:
    path: str
    sample_rate_hz: int
    channels: int
    window_ms: int
    duration_ms: int
    frame_count: int
    speech_like_ratio: float
    average_rms_dbfs: float
    peak_dbfs: float
    frames: list[AudioLevelFrame] = field(default_factory=list)
    def to_dict(self) -> dict:
        payload = asdict(self)
        payload['frames'] = [f.to_dict() for f in self.frames]
        return payload
    def to_json(self) -> str: return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    def to_markdown(self) -> str:
        lines = ['# Audio Level Report','',f'- Path: `{self.path}`',f'- Duration: `{self.duration_ms} ms`',f'- Sample rate: `{self.sample_rate_hz} Hz`',f'- Channels: `{self.channels}`',f'- Window: `{self.window_ms} ms`',f'- Frames: `{self.frame_count}`',f'- Speech-like ratio: `{self.speech_like_ratio}`',f'- Average RMS: `{self.average_rms_dbfs} dBFS`',f'- Peak: `{self.peak_dbfs} dBFS`','','| # | Time | RMS dBFS | Peak dBFS | Clipping | Speech-like |','|---:|---|---:|---:|---:|---|']
        for frame in self.frames[:120]:
            lines.append(f"| {frame.index} | {frame.start_ms}-{frame.end_ms} ms | {frame.rms_dbfs} | {frame.peak_dbfs} | {frame.clipping_ratio} | {'yes' if frame.is_speech_like else 'no'} |")
        if len(self.frames) > 120:
            lines.append(f"| ... | ... | ... | ... | ... | {len(self.frames)-120} more frames |")
        return '\n'.join(lines) + '\n'

def analyze_audio_levels(path: str | Path, *, window_ms: int = 100, speech_rms_threshold_dbfs: float = -45.0) -> AudioLevelReport:
    if window_ms <= 0: raise ValueError('window_ms must be positive')
    wav_path = Path(path)
    frames: list[AudioLevelFrame] = []
    with wave.open(str(wav_path), 'rb') as wav:
        channels = wav.getnchannels(); sample_width = wav.getsampwidth(); sample_rate = wav.getframerate(); total_frames = wav.getnframes()
        if sample_width != 2: raise ValueError('audio level analyzer supports PCM s16le WAV files only')
        frames_per_window = max(1, int(round(sample_rate * window_ms / 1000)))
        current_frame_start = 0; index = 0; rms_values: list[float] = []; peak_overall = 0.0; speech_count = 0
        while current_frame_start < total_frames:
            raw = wav.readframes(frames_per_window)
            if not raw: break
            samples = list(_iter_pcm_s16le(raw))
            if not samples: break
            rms_linear, peak_linear, clipping_ratio = _sample_stats(samples)
            rms_dbfs = _linear_to_dbfs(rms_linear); peak_dbfs = _linear_to_dbfs(peak_linear)
            frame_len = len(samples) // max(1, channels)
            start_ms = int(round(current_frame_start * 1000 / sample_rate)); end_ms = int(round((current_frame_start + frame_len) * 1000 / sample_rate))
            is_speech_like = rms_dbfs >= speech_rms_threshold_dbfs
            speech_count += 1 if is_speech_like else 0; rms_values.append(rms_linear); peak_overall = max(peak_overall, peak_linear)
            frames.append(AudioLevelFrame(index, start_ms, end_ms, round(rms_linear,6), round(peak_linear,6), round(rms_dbfs,2), round(peak_dbfs,2), round(clipping_ratio,6), is_speech_like))
            current_frame_start += frame_len; index += 1
    duration_ms = int(round(total_frames * 1000 / sample_rate)) if sample_rate else 0
    avg_rms = math.sqrt(sum(v*v for v in rms_values)/len(rms_values)) if rms_values else 0.0
    return AudioLevelReport(str(wav_path), sample_rate, channels, window_ms, duration_ms, len(frames), round(speech_count/len(frames),6) if frames else 0.0, round(_linear_to_dbfs(avg_rms),2), round(_linear_to_dbfs(peak_overall),2), frames)

def write_audio_level_report(report: AudioLevelReport, out_json: str | Path, out_md: str | Path | None = None) -> None:
    out_json = Path(out_json); out_json.parent.mkdir(parents=True, exist_ok=True); out_json.write_text(report.to_json()+'\n', encoding='utf-8')
    if out_md:
        out_md = Path(out_md); out_md.parent.mkdir(parents=True, exist_ok=True); out_md.write_text(report.to_markdown(), encoding='utf-8')

def _iter_pcm_s16le(raw: bytes) -> Iterable[int]:
    for i in range(0, len(raw)-1, 2): yield int.from_bytes(raw[i:i+2], byteorder='little', signed=True)

def _sample_stats(samples: list[int]) -> tuple[float,float,float]:
    if not samples: return 0.0,0.0,0.0
    sum_sq=0.0; peak=0; clipped=0
    for s in samples:
        a=abs(s); peak=max(peak,a); sum_sq += float(s)*float(s); clipped += 1 if a >= 32760 else 0
    return min(1.0, math.sqrt(sum_sq/len(samples))/_PCM16_MAX), min(1.0, peak/_PCM16_MAX), clipped/len(samples)

def _linear_to_dbfs(value: float) -> float:
    return -120.0 if value <= 0 else 20.0 * math.log10(value)
