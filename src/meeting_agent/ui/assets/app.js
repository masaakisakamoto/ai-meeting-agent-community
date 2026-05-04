(() => {
  const fallback = {
    transcript: {
      meeting_id: 'mtg_fallback',
      title: 'Fallback Demo',
      segments: [
        { id: 'seg_0001', speaker_name: '佐藤', start_ms: 1000, end_ms: 5000, text: 'v2.0ではReal Mac Evidence Collectionと公開保留を確認します。' },
        { id: 'seg_0002', speaker_name: '田中', start_ms: 6000, end_ms: 10000, text: '山田さん、金曜までにスクリーンショット導線を確認お願いします。' }
      ]
    },
    minutes: { summary: '', decisions: [], action_items: [], open_questions: [], risks: [] },
    replay: { events: [] },
    desktop_workflow: { status: 'preview', artifacts: [] }
  };

  const data = window.MEETING_AGENT_DEMO || fallback;
  const bridge = window.MEETING_AGENT_BRIDGE || { enabled: false, url: 'http://127.0.0.1:8765' };
  const transcript = data.transcript || fallback.transcript;
  const minutes = data.minutes || fallback.minutes;
  const workflow = data.desktop_workflow || data.workflow || data.desktop_alpha || fallback.desktop_workflow;
  const audioDiagnostics = data.audio_diagnostics || workflow.audio_quality || {};
  const captureReadiness = data.preflight || data.capture_readiness || workflow.readiness || {};
  const asrSmoke = data.asr_smoke || workflow.asr_smoke || {};
  const audioLevels = data.audio_levels || workflow.audio_levels || {};
  const replayEvents = (data.replay && data.replay.events && data.replay.events.length)
    ? data.replay.events
    : buildReplayEvents(transcript.segments || []);

  const state = { running: false, workflowRunning: false, timer: null, eventIndex: 0, speed: 1, segments: new Map() };
  const el = (id) => document.getElementById(id);
  const transcriptList = el('transcript-list');
  el('meeting-title').textContent = transcript.title || transcript.meeting_id || 'Meeting';

  renderIntelligence();
  renderReadiness();
  renderMicrophoneReadiness();
  renderLevelMeter();
  renderWorkflowSteps();
  wireControls();
  updateProgress();

  function wireControls() {
    el('start-btn').addEventListener('click', startReplay);
    el('pause-btn').addEventListener('click', pauseReplay);
    el('reset-btn').addEventListener('click', resetReplay);
    el('workflow-run-btn').addEventListener('click', runWorkflowPreview);
    el('speed-select').addEventListener('change', (event) => { state.speed = Number(event.target.value || 1); });
    el('download-transcript').addEventListener('click', () => downloadJson('transcript.json', transcript));
    el('download-events').addEventListener('click', () => downloadJson('replay_events.json', replayEvents));
    el('download-minutes').addEventListener('click', () => downloadText('minutes.md', buildMarkdown()));
    el('download-workflow').addEventListener('click', () => downloadJson('desktop_workflow.json', workflow));
    el('bridge-health').addEventListener('click', () => bridgeRequest('GET', '/api/health'));
    el('bridge-devices').addEventListener('click', () => bridgeRequest('GET', '/api/audio/devices'));
    el('bridge-workflow').addEventListener('click', () => bridgeRequest('POST', '/api/workflows/simulated-record', { session_id: 'ui_sim', total_ms: 3000, chunk_ms: 250 }));
    el('bridge-mic-doctor').addEventListener('click', () => bridgeRequest('GET', '/api/microphone/doctor?duration_ms=3000'));
    el('bridge-mic-alpha').addEventListener('click', () => bridgeRequest('POST', '/api/workflows/microphone-alpha', { duration_ms: 3000, device_id: 'microphone:default' }));
    const safetyButton = el('bridge-safety-gate');
    if (safetyButton) safetyButton.addEventListener('click', () => bridgeRequest('POST', '/api/recording/safety-gate', { duration_ms: 3000, live_requested: false }));
    const envButton = el('bridge-env-doctor');
    if (envButton) envButton.addEventListener('click', () => bridgeRequest('GET', '/api/dev/environment'));
    const alphaButton = el('bridge-private-alpha');
    if (alphaButton) alphaButton.addEventListener('click', () => bridgeRequest('GET', '/api/private-alpha/gate'));
    const publicAlphaButton = el('bridge-public-alpha');
    if (publicAlphaButton) publicAlphaButton.addEventListener('click', () => bridgeRequest('GET', '/api/public-alpha/readiness'));
    const publicPlanButton = el('bridge-public-plan');
    if (publicPlanButton) publicPlanButton.addEventListener('click', () => bridgeRequest('GET', '/api/public-alpha/plan'));
    const publicCandidatePackButton = el('bridge-public-candidate-pack');
    if (publicCandidatePackButton) publicCandidatePackButton.addEventListener('click', () => bridgeRequest('GET', '/api/public-alpha/candidate-pack'));
    const publicCandidateGateButton = el('bridge-public-candidate-gate');
    if (publicCandidateGateButton) publicCandidateGateButton.addEventListener('click', () => bridgeRequest('GET', '/api/public-alpha/candidate-gate'));
    const maintainerPackButton = el('bridge-maintainer-pack');
    if (maintainerPackButton) maintainerPackButton.addEventListener('click', () => bridgeRequest('GET', '/api/maintainer/review-pack'));
    const maintainerDashboardButton = el('bridge-maintainer-dashboard');
    if (maintainerDashboardButton) maintainerDashboardButton.addEventListener('click', () => bridgeRequest('GET', '/api/maintainer/dashboard'));
    const launchAssetsButton = el('bridge-launch-assets');
    if (launchAssetsButton) launchAssetsButton.addEventListener('click', () => bridgeRequest('GET', '/api/launch/assets-pack'));
    const launchPolishButton = el('bridge-launch-polish');
    if (launchPolishButton) launchPolishButton.addEventListener('click', () => bridgeRequest('GET', '/api/launch/polish-check'));
    const evidencePackButton = el('bridge-evidence-pack');
    if (evidencePackButton) evidencePackButton.addEventListener('click', () => bridgeRequest('GET', '/api/evidence/real-mac-pack'));
    const evidenceCollectButton = el('bridge-evidence-collect');
    if (evidenceCollectButton) evidenceCollectButton.addEventListener('click', () => bridgeRequest('POST', '/api/evidence/real-mac-collect', { run_id: 'ui_real_mac_evidence' }));
    const screenshotPackButton = el('bridge-screenshot-pack');
    if (screenshotPackButton) screenshotPackButton.addEventListener('click', () => bridgeRequest('GET', '/api/screenshots/automation-pack'));
    const screenshotGateButton = el('bridge-screenshot-gate');
    if (screenshotGateButton) screenshotGateButton.addEventListener('click', () => bridgeRequest('GET', '/api/screenshots/readiness-gate'));
    const evidenceExportPackButton = el('bridge-evidence-export-pack');
    if (evidenceExportPackButton) evidenceExportPackButton.addEventListener('click', () => bridgeRequest('GET', '/api/evidence/export-pack'));
    const evidenceExportRunButton = el('bridge-evidence-export-run');
    if (evidenceExportRunButton) evidenceExportRunButton.addEventListener('click', () => bridgeRequest('POST', '/api/evidence/export-run', { run_id: 'ui_evidence_export' }));
    const evidenceExportGateButton = el('bridge-evidence-export-gate');
    if (evidenceExportGateButton) evidenceExportGateButton.addEventListener('click', () => bridgeRequest('GET', '/api/evidence/export-gate'));
    const realCapturePackButton = el('bridge-real-capture-pack');
    if (realCapturePackButton) realCapturePackButton.addEventListener('click', () => bridgeRequest('GET', '/api/real-capture/execution-pack?duration_ms=3000'));
    const realCaptureGateButton = el('bridge-real-capture-gate');
    if (realCaptureGateButton) realCaptureGateButton.addEventListener('click', () => bridgeRequest('GET', '/api/real-capture/execution-gate?allow_dry_run=1'));
    const capturePlanButton = el('bridge-capture-plan');
    if (capturePlanButton) capturePlanButton.addEventListener('click', () => bridgeRequest('GET', '/api/capture/plan?duration_ms=3000'));
    const postCaptureButton = el('bridge-post-capture-gate');
    if (postCaptureButton) postCaptureButton.addEventListener('click', () => bridgeRequest('GET', '/api/post-capture/gate'));
    const micToMinutesButton = el('bridge-mic-to-minutes');
    if (micToMinutesButton) micToMinutesButton.addEventListener('click', () => bridgeRequest('POST', '/api/workflows/microphone-to-minutes', { run_id: 'ui_mic_minutes', provider: 'sidecar' }));
    const validationPackButton = el('bridge-validation-pack');
    if (validationPackButton) validationPackButton.addEventListener('click', () => bridgeRequest('GET', '/api/capture/validation-pack?duration_ms=3000'));
    const validationRunButton = el('bridge-validation-run');
    if (validationRunButton) validationRunButton.addEventListener('click', () => bridgeRequest('GET', '/api/capture/validation-run?provider=sidecar'));
    const asrPackButton = el('bridge-asr-pack');
    if (asrPackButton) asrPackButton.addEventListener('click', () => bridgeRequest('GET', '/api/asr/validation-pack?provider=sidecar'));
    const asrRunButton = el('bridge-asr-run');
    if (asrRunButton) asrRunButton.addEventListener('click', () => bridgeRequest('POST', '/api/asr/validation-run', { run_id: 'ui_asr_validation', provider: 'sidecar' }));
    const asrMinutesButton = el('bridge-asr-minutes');
    if (asrMinutesButton) asrMinutesButton.addEventListener('click', () => bridgeRequest('POST', '/api/workflows/asr-to-minutes', { run_id: 'ui_asr_minutes', provider: 'sidecar' }));
    const localAsrPackButton = el('bridge-local-asr-pack');
    if (localAsrPackButton) localAsrPackButton.addEventListener('click', () => bridgeRequest('GET', '/api/local-asr/smoke-pack'));
    const localAsrRunButton = el('bridge-local-asr-run');
    if (localAsrRunButton) localAsrRunButton.addEventListener('click', () => bridgeRequest('POST', '/api/local-asr/smoke-run', { run_id: 'ui_local_asr_smoke', mode: 'sidecar' }));
    const localAsrGateButton = el('bridge-local-asr-gate');
    if (localAsrGateButton) localAsrGateButton.addEventListener('click', () => bridgeRequest('GET', '/api/local-asr/smoke-gate'));
        document.querySelectorAll('.tab').forEach((button) => button.addEventListener('click', () => selectTab(button.dataset.tab)));
  }

  function startReplay() {
    if (state.running) return;
    state.running = true;
    setStatus('Recording demo', 'Rendering simulated realtime transcript');
    scheduleNext(80);
  }

  function pauseReplay() {
    state.running = false;
    clearTimeout(state.timer);
    setStatus('Paused', 'Replay can resume from current point');
  }

  function resetReplay() {
    pauseReplay();
    state.eventIndex = 0;
    state.segments.clear();
    transcriptList.innerHTML = '';
    el('transcript-count').textContent = '0 segments';
    el('evidence-preview').textContent = '抽出候補または発言を選択すると、根拠発言がここに表示されます。';
    updateProgress();
    setStatus('Ready', 'Static UI with optional local bridge');
  }

  function scheduleNext(delay) {
    clearTimeout(state.timer);
    state.timer = setTimeout(stepReplay, Math.max(20, delay / state.speed));
  }

  function stepReplay() {
    if (!state.running) return;
    if (state.eventIndex >= replayEvents.length) {
      state.running = false;
      setStatus('Complete', 'Minutes are ready for export');
      updateProgress();
      return;
    }
    const event = replayEvents[state.eventIndex++];
    handleReplayEvent(event);
    updateProgress();
    const next = replayEvents[state.eventIndex];
    const currentOffset = Number(event.offset_ms || 0);
    const nextOffset = next ? Number(next.offset_ms || currentOffset + 200) : currentOffset + 200;
    scheduleNext(Math.max(80, nextOffset - currentOffset));
  }

  function handleReplayEvent(event) {
    if (event.type === 'segment_start') {
      state.segments.set(event.segment_id, { ...event, text: '' });
      upsertSegment(event.segment_id);
    } else if (event.type === 'segment_delta') {
      const seg = state.segments.get(event.segment_id) || { ...event, text: '' };
      seg.text = (seg.text || '') + (event.delta || '');
      state.segments.set(event.segment_id, seg);
      upsertSegment(event.segment_id);
    } else if (event.type === 'segment_final') {
      const source = findSegment(event.segment_id) || event;
      state.segments.set(event.segment_id, { ...source, ...event, text: event.text || source.text || '' });
      upsertSegment(event.segment_id, true);
    }
    el('transcript-count').textContent = `${state.segments.size} segments`;
  }

  function upsertSegment(segmentId, final = false) {
    const seg = state.segments.get(segmentId);
    if (!seg) return;
    let node = document.querySelector(`[data-segment-id="${attrEscape(segmentId)}"]`);
    if (!node) {
      node = document.createElement('article');
      node.className = 'segment';
      node.dataset.segmentId = segmentId;
      node.innerHTML = '<div class="segment-head"><span></span><span></span></div><p class="segment-text"></p>';
      node.addEventListener('click', () => selectEvidenceBySegment(segmentId));
      transcriptList.appendChild(node);
    }
    node.querySelector('.segment-head span:first-child').textContent = `${formatTime(seg.start_ms)} ${seg.speaker_name || 'Unknown'}`;
    node.querySelector('.segment-head span:last-child').textContent = final ? 'final' : 'live';
    node.querySelector('.segment-text').textContent = seg.text || '';
    node.scrollIntoView({ block: 'nearest' });
  }

  function renderWorkflowSteps() {
    const labels = ['capture preflight', 'WAV recording', 'audio diagnostics', 'ASR smoke', 'transcript', 'minutes', 'desktop bundle'];
    const completed = Array.isArray(workflow.steps) ? new Set(workflow.steps.map((step) => String(step.name || '').replace(/_/g, ' '))) : new Set();
    el('workflow-steps').innerHTML = labels.map((label) => {
      const done = Array.from(completed).some((step) => step.includes(label.split(' ')[0]));
      return `<div class="workflow-step ${done ? 'done' : ''}"><span></span><strong>${escapeHtml(label)}</strong><small>${done ? 'complete' : 'pending'}</small></div>`;
    }).join('');
    el('workflow-status').textContent = workflow.status || 'preview';
  }

  function runWorkflowPreview() {
    if (state.workflowRunning) return;
    state.workflowRunning = true;
    el('workflow-status').textContent = 'running preview';
    const steps = Array.from(document.querySelectorAll('.workflow-step'));
    steps.forEach((step) => { step.classList.remove('done'); step.querySelector('small').textContent = 'pending'; });
    let i = 0;
    const tick = () => {
      if (i > 0) { steps[i - 1].classList.add('done'); steps[i - 1].querySelector('small').textContent = 'complete'; }
      if (i >= steps.length) { el('workflow-status').textContent = workflow.status || 'complete'; state.workflowRunning = false; return; }
      steps[i].querySelector('small').textContent = 'running';
      i += 1;
      setTimeout(tick, 260);
    };
    tick();
  }

  function renderReadiness() {
    const cards = [
      ['Audio quality', audioDiagnostics.status || 'unknown', `score ${audioDiagnostics.score ?? '-'} / RMS ${audioDiagnostics.rms_dbfs ?? '-'} dBFS`],
      ['Capture preflight', captureReadiness.status || 'unknown', captureReadiness.recommendation || 'simulated provider'],
      ['ASR smoke', asrSmoke.status || 'unknown', `provider ${asrSmoke.provider_id || asrSmoke.provider || '-'} / segments ${asrSmoke.segment_count ?? asrSmoke.segments ?? '-'}`],
      ['Workflow', workflow.status || 'preview', workflow.workflow_id || workflow.id || 'desktop_alpha']
    ];
    el('readiness-grid').innerHTML = cards.map(([title, status, detail]) => `<div class="readiness-card ${escapeHtml(String(status))}"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(String(status))}</span><small>${escapeHtml(String(detail))}</small></div>`).join('');
  }

  function renderMicrophoneReadiness(report) {
    const target = el('mic-readiness-grid');
    if (!target) return;
    const source = report || (workflow.microphone || workflow.microphone_alpha || {});
    const status = source.status || 'standby';
    const detail = source.recommendation || 'BridgeのMic DoctorまたはMic Alpha Dry Runで確認';
    target.innerHTML = `<div class="readiness-card ${escapeHtml(String(status))}"><strong>Mic alpha</strong><span>${escapeHtml(String(status))}</span><small>${escapeHtml(detail)}</small></div>`;
  }

  function renderMicrophoneResult(payload) {
    const report = payload.microphone || payload.recording_safety_gate || payload.private_alpha_gate || payload.environment || payload.capture_plan || payload.post_capture_gate || payload.microphone_minutes || payload.public_alpha_readiness || payload.public_alpha_plan || payload.asr_validation_pack || payload.asr_validation || payload.asr_minutes || payload.local_asr_smoke_pack || payload.local_asr_smoke || payload.local_asr_smoke_gate || payload.launch_assets_pack || payload.launch_assets_gate || payload.screenshot_automation_pack || payload.screenshot_readiness || payload.evidence_export_pack || payload.evidence_export || payload.evidence_export_gate || (payload.workflow && (payload.workflow.microphone || payload.workflow.microphone_minutes || payload.workflow.asr_minutes)) || payload;
    renderMicrophoneReadiness(report);
    const target = el('bridge-mic-result');
    if (!target) return;
    const checks = report.checks || [];
    target.innerHTML = `<strong>Mic/Safety: ${escapeHtml(report.status || payload.status || 'unknown')}</strong><span>score ${escapeHtml(report.score ?? '-')} / mode ${escapeHtml(report.mode || (report.live_requested ? 'live-gate' : 'dry-run-gate') || '-')}</span><small>${escapeHtml(report.recommendation || 'Safe microphone alpha check completed.')}</small><div class="check-list">${checks.slice(0, 8).map((check) => `<span class="check-pill ${escapeHtml(check.status || 'unknown')}">${escapeHtml(check.id || 'check')}: ${escapeHtml(check.status || '-')}</span>`).join('')}</div>`;
  }

  function renderLevelMeter() {
    const frames = audioLevels.frames || [];
    el('level-summary').textContent = frames.length ? `${frames.length} frames / peak ${audioLevels.peak_dbfs ?? '-'} dBFS` : 'no level data';
    if (!frames.length) { el('level-meter').innerHTML = '<div class="empty">音声レベルデータがありません。</div>'; return; }
    el('level-meter').innerHTML = frames.slice(0, 120).map((frame) => {
      const height = Math.max(4, Math.min(100, Math.round((frame.peak_linear || frame.rms_linear || 0) * 100)));
      const cls = frame.clipping_ratio > 0 ? 'clip' : frame.is_speech_like ? 'speech' : 'quiet';
      return `<span class="level-bar ${cls}" title="${frame.start_ms}-${frame.end_ms}ms / RMS ${frame.rms_dbfs} dBFS" style="height:${height}%"></span>`;
    }).join('');
  }

  function renderIntelligence() {
    renderCards('tab-decisions', minutes.decisions || [], (item) => item.text, 'decision');
    renderCards('tab-actions', minutes.action_items || [], (item) => `${item.owner || '未定'}: ${item.task}`, 'action');
    renderCards('tab-questions', minutes.open_questions || [], (item) => item.text, 'question');
  }

  function renderCards(containerId, items, labelFn, kind) {
    const root = el(containerId);
    root.innerHTML = '';
    if (!items.length) { root.innerHTML = '<div class="empty">このカテゴリの候補はまだありません。</div>'; return; }
    items.forEach((item) => {
      const card = document.createElement('div');
      card.className = 'card';
      const evidence = item.evidence_segment_ids || [];
      card.innerHTML = `<strong>${escapeHtml(labelFn(item))}</strong><small>${kind} / confidence ${item.confidence ?? '-'} / evidence ${evidence.join(', ') || 'none'}</small>`;
      card.addEventListener('click', () => selectEvidence(item));
      root.appendChild(card);
    });
  }

  function selectTab(tab) {
    document.querySelectorAll('.tab').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab));
    document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.remove('active'));
    el(`tab-${tab}`).classList.add('active');
  }

  function selectEvidence(item) {
    const ids = item.evidence_segment_ids || [];
    const evidence = ids.map(findSegment).filter(Boolean);
    el('evidence-preview').innerHTML = evidence.length ? evidence.map(renderEvidenceLine).join('') : '<p>根拠発言がありません。Verifierで要確認です。</p>';
    highlightSegments(ids);
  }

  function selectEvidenceBySegment(segmentId) {
    const seg = findSegment(segmentId) || state.segments.get(segmentId);
    el('evidence-preview').innerHTML = seg ? renderEvidenceLine(seg) : '発言が見つかりません。';
    highlightSegments([segmentId]);
  }

  function renderEvidenceLine(seg) {
    return `<p><strong>${escapeHtml(formatTime(seg.start_ms))} ${escapeHtml(seg.speaker_name || 'Unknown')}</strong><br>${escapeHtml(seg.text || '')}</p>`;
  }

  function highlightSegments(ids) {
    document.querySelectorAll('.segment').forEach((node) => node.classList.toggle('active', ids.includes(node.dataset.segmentId)));
  }

  function updateProgress() {
    const pct = replayEvents.length ? Math.round((state.eventIndex / replayEvents.length) * 100) : 0;
    el('progress-text').textContent = `${pct}%`;
    el('progress-bar').style.width = `${pct}%`;
  }

  function setStatus(title, subtitle) {
    const status = el('system-status');
    status.querySelector('strong').textContent = title;
    status.querySelector('small').textContent = subtitle;
  }

  async function bridgeRequest(method, route, body) {
    const output = el('bridge-output');
    el('bridge-status-label').textContent = 'running';
    output.textContent = JSON.stringify({ status: 'running', route }, null, 2);
    try {
      const base = (bridge.enabled && bridge.url) ? String(bridge.url).replace(/\/$/, '') : '';
      const response = await fetch(`${base}${route}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'POST' ? JSON.stringify(body || {}) : undefined,
      });
      const text = await response.text();
      const payload = text ? JSON.parse(text) : {};
      el('bridge-status-label').textContent = response.ok ? 'connected' : 'warning';
      output.textContent = JSON.stringify(payload, null, 2);
      if (route.includes('/microphone') || route.includes('/recording/safety-gate') || route.includes('/capture/plan') || route.includes('/capture/validation') || route.includes('/private-alpha/gate') || route.includes('/public-alpha') || route.includes('/dev/environment') || route.includes('/post-capture') || route.includes('/microphone-to-minutes') || route.includes('/asr/validation') || route.includes('/asr-to-minutes') || route.includes('/local-asr') || route.includes('/api/launch') || route.includes('/launch') || route.includes('/launch/') || route.includes('/api/evidence') || route.includes('/evidence') || route.includes('/api/maintainer') || route.includes('/maintainer') || (payload.workflow && payload.workflow.microphone)) renderMicrophoneResult(payload);
    } catch (error) {
      el('bridge-status-label').textContent = 'offline';
      output.textContent = `Bridge offline or blocked.\n${error.message}\n\nStatic Desktop Alpha features still work.`;
    }
  }

  function findSegment(id) { return (transcript.segments || []).find((seg) => seg.id === id) || null; }
  function buildReplayEvents(segments) {
    const events = []; let offset = 0; let sequence = 0;
    segments.forEach((seg) => {
      events.push({ type: 'segment_start', segment_id: seg.id, speaker_name: seg.speaker_name, start_ms: seg.start_ms, end_ms: seg.end_ms, offset_ms: offset, sequence: ++sequence });
      const text = seg.text || '';
      for (let i = 0; i < text.length; i += 24) { offset += 120; events.push({ type: 'segment_delta', segment_id: seg.id, speaker_name: seg.speaker_name, delta: text.slice(i, i + 24), start_ms: seg.start_ms, end_ms: seg.end_ms, offset_ms: offset, sequence: ++sequence }); }
      offset += 120;
      events.push({ type: 'segment_final', segment_id: seg.id, speaker_name: seg.speaker_name, text, start_ms: seg.start_ms, end_ms: seg.end_ms, offset_ms: offset, sequence: ++sequence });
    });
    events.push({ type: 'meeting_end', offset_ms: offset + 120, sequence: ++sequence });
    return events;
  }
  function buildMarkdown() {
    const lines = [`# ${transcript.title || 'Meeting Minutes'}`, '', '## Summary', minutes.summary || '', '', '## Decisions'];
    (minutes.decisions || []).forEach((item) => lines.push(`- ${item.text}`));
    lines.push('', '## Action Items');
    (minutes.action_items || []).forEach((item) => lines.push(`- ${item.owner || '未定'}: ${item.task} / ${item.due_date || '未定'}`));
    lines.push('', '## Open Questions');
    (minutes.open_questions || []).forEach((item) => lines.push(`- ${item.text}`));
    return lines.join('\n');
  }
  function downloadJson(filename, obj) { downloadText(filename, JSON.stringify(obj, null, 2)); }
  function downloadText(filename, text) {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
  }
  function formatTime(ms) { const total = Math.max(0, Math.floor(Number(ms || 0) / 1000)); const m = Math.floor(total / 60); const s = total % 60; return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`; }
  function escapeHtml(value) { return String(value || '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function attrEscape(value) { return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&'); }
})();
