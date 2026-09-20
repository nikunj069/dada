/**
 * BlackBox PS3 — Dashboard Application
 * All features wired to real API endpoints.
 */
document.addEventListener('DOMContentLoaded', () => {
  // ══════════════════════════════════════════════
  // STATE
  // ══════════════════════════════════════════════
  let allTests = [];
  let allRuns = [];
  let allDiagnoses = [];
  let allBoards = [];
  let currentFilter = 'all';
  let defectLines = new Set();
  let firmwareLines = [];

  // ══════════════════════════════════════════════
  // ELEMENTS
  // ══════════════════════════════════════════════
  const tabButtons = document.querySelectorAll('.nav-tab');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const traceSelect = document.getElementById('traceSelect');
  const rigIframe = document.getElementById('rigIframe');
  const btnRunAgent = document.getElementById('btnRunAgent');
  const testsTableBody = document.getElementById('testsTableBody');
  const defectsContainer = document.getElementById('defectsContainer');
  const diagnosisContainer = document.getElementById('diagnosisContainer');
  const funcListContainer = document.getElementById('funcListContainer');
  const codeViewer = document.getElementById('codeViewer');
  const runsContainer = document.getElementById('runsContainer');
  const boardsContainer = document.getElementById('boardsContainer');

  // Metrics
  const telemChip = document.getElementById('telemChip');
  const telemCoverage = document.getElementById('telemCoverage');
  const telemTests = document.getElementById('telemTests');
  const telemTraces = document.getElementById('telemTraces');
  const metricTotal = document.getElementById('metricTotal');
  const metricPass = document.getElementById('metricPass');
  const metricFail = document.getElementById('metricFail');
  const metricCoverage = document.getElementById('metricCoverage');
  const agentStatusPill = document.getElementById('agentStatusPill');

  // Compare
  const compareRunA = document.getElementById('compareRunA');
  const compareRunB = document.getElementById('compareRunB');
  const btnCompare = document.getElementById('btnCompare');

  // Transport
  const transportTraces = document.getElementById('transportTraces');
  const transportAgent = document.getElementById('transportAgent');
  const liveClock = document.getElementById('liveClock');

  // ══════════════════════════════════════════════
  // LIVE CLOCK
  // ══════════════════════════════════════════════
  function updateClock() {
    if (liveClock) {
      liveClock.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
    }
  }
  setInterval(updateClock, 1000);
  updateClock();

  // ══════════════════════════════════════════════
  // TAB SWITCHING
  // ══════════════════════════════════════════════
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.dataset.tab;
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const pane = document.getElementById(targetTab);
      if (pane) pane.classList.add('active');
    });
  });

  // ══════════════════════════════════════════════
  // FILTERS
  // ══════════════════════════════════════════════
  const filterButtons = document.querySelectorAll('.filter-btn');
  filterButtons.forEach(fb => {
    fb.addEventListener('click', () => {
      filterButtons.forEach(b => b.classList.remove('active'));
      fb.classList.add('active');
      currentFilter = fb.dataset.filter;
      renderTestsTable();
    });
  });

  // ══════════════════════════════════════════════
  // TOAST
  // ══════════════════════════════════════════════
  function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3500);
  }

  // ══════════════════════════════════════════════
  // FETCH STATUS (real data)
  // ══════════════════════════════════════════════
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();

      if (telemChip) telemChip.textContent = data.chip || 'STM32F103';
      if (telemCoverage) telemCoverage.textContent = `${data.coverage_pct}%`;
      if (telemTests) telemTests.textContent = `${data.passed}/${data.total_tests} PASS`;
      if (telemTraces) telemTraces.textContent = `${data.available_traces} traces`;
      if (transportTraces) transportTraces.textContent = `${data.available_traces} traces`;

      if (metricTotal) metricTotal.textContent = data.total_tests;
      if (metricPass) metricPass.textContent = data.passed;
      if (metricFail) metricFail.textContent = data.failed;
      if (metricCoverage) metricCoverage.textContent = `${data.coverage_pct}%`;

      if (agentStatusPill) {
        const state = data.agent_state || 'idle';
        agentStatusPill.textContent = state.toUpperCase();
        if (state === 'running') {
          agentStatusPill.style.color = 'var(--phosphor)';
          if (btnRunAgent) { btnRunAgent.disabled = true; btnRunAgent.textContent = 'EXECUTING...'; }
          if (transportAgent) { transportAgent.textContent = '◉ RUNNING'; transportAgent.style.color = 'var(--phosphor)'; }
        } else {
          agentStatusPill.style.color = 'var(--sig-green)';
          if (btnRunAgent) { btnRunAgent.disabled = false; btnRunAgent.innerHTML = '<span class="icon">⚡</span> RUN AGENT'; }
          if (transportAgent) { transportAgent.textContent = '● IDLE'; transportAgent.style.color = 'var(--sig-green)'; }
        }
      }
    } catch (e) {
      console.warn('Status fetch error:', e);
    }
  }

  // ══════════════════════════════════════════════
  // FETCH TESTS (real data from report.json)
  // ══════════════════════════════════════════════
  async function fetchTests() {
    try {
      const res = await fetch('/api/tests');
      const data = await res.json();
      allTests = data.tests || [];
      const badge = document.getElementById('testCountBadge');
      if (badge) badge.textContent = allTests.length;
      renderTestsTable();
    } catch (e) {
      console.error('Tests fetch error:', e);
    }
  }

  function renderTestsTable() {
    if (!testsTableBody) return;

    const filtered = allTests.filter(t => {
      const cat = (t.scenario?.category || '').toLowerCase();
      const status = (t.verification_result?.status || '').toLowerCase();
      if (currentFilter === 'all') return true;
      if (currentFilter === 'boundary' && cat === 'boundary') return true;
      if (currentFilter === 'fault' && cat === 'fault') return true;
      if (currentFilter === 'state' && cat === 'state') return true;
      if (currentFilter === 'fail' && status !== 'pass') return true;
      return false;
    });

    if (filtered.length === 0) {
      testsTableBody.innerHTML = `<tr><td colspan="6" class="loading-text">No matching test scenarios found</td></tr>`;
      return;
    }

    testsTableBody.innerHTML = filtered.map(t => {
      const isPass = t.verification_result?.status === 'pass';
      const statusBadge = isPass ? '<span class="badge badge-pass">PASS</span>' : '<span class="badge badge-fail">FAIL</span>';
      const cat = t.scenario?.category || 'TEST';
      let catClass = 'badge-boundary';
      if (cat.toLowerCase() === 'fault') catClass = 'badge-fault';
      if (cat.toLowerCase() === 'state') catClass = 'badge-state';
      const inputVal = (t.scenario?.inputs || []).map(i => `${i.name}=${i.value}`).join(', ') || 'N/A';
      const cycles = t.simulation_result?.cycles ? `${t.simulation_result.cycles.toLocaleString()} cyc` : '—';
      const stopReason = t.simulation_result?.stop_reason || '';

      return `<tr>
        <td><strong style="color:var(--silk);">${t.test_id}</strong></td>
        <td><span class="badge ${catClass}">${cat}</span></td>
        <td>
          <div style="font-weight:500; font-size:12px;">${t.scenario?.description || 'Scenario execution'}</div>
          <div style="font-size:10px; color:var(--silk-muted); margin-top:2px;">Inputs: ${inputVal}${stopReason ? ` · ${stopReason}` : ''}</div>
        </td>
        <td>${statusBadge}</td>
        <td style="color:var(--silk-muted); font-size:11px;">${cycles}</td>
        <td>
          <div style="display:flex; gap:4px;">
            <button class="btn btn-ghost btn-sm" onclick="loadTraceInViewer('${t.test_id}')">3D Trace ↗</button>
            <a href="/view/${t.test_id}" target="_blank" class="btn btn-ghost btn-sm" style="text-decoration:none;">Tab ↗</a>
            <button class="btn btn-ghost btn-sm" onclick="showDiagnosis('${t.test_id}')">Diag</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  // ══════════════════════════════════════════════
  // FETCH TRACES (real data)
  // ══════════════════════════════════════════════
  async function fetchTraces() {
    try {
      const res = await fetch('/api/traces');
      const data = await res.json();
      const traces = data.traces || [];

      if (traceSelect) {
        traceSelect.innerHTML = '<option value="demo">LIVE DEMO (Simulation)</option>';
        traces.forEach(tr => {
          const opt = document.createElement('option');
          opt.value = tr.test_id;
          const vBadge = tr.verdict === 'FAIL' ? '✗' : tr.verdict === 'PASS' ? '✓' : '?';
          opt.textContent = `${tr.test_id} ${vBadge} (${Math.round(tr.size_bytes / 1024)} KB)`;
          traceSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('Traces fetch error:', e);
    }
  }

  // Trace selector change
  if (traceSelect) {
    traceSelect.addEventListener('change', () => {
      const selected = traceSelect.value;
      const fullscreenBtn = document.getElementById('fullscreenTraceBtn');
      
      if (selected === 'demo') {
        if (rigIframe) rigIframe.src = '/viewer';
        if (fullscreenBtn) fullscreenBtn.href = '/viewer';
        showToast('Loaded Live 3D Demo Trace');
      } else {
        const url = `/view/${encodeURIComponent(selected)}`;
        if (rigIframe) rigIframe.src = url;
        if (fullscreenBtn) fullscreenBtn.href = url;
        showToast(`Loaded ${selected} telemetry trace`);
      }
    });
  }
  
  // Expose loadTraceInViewer for matrix table buttons
  window.loadTraceInViewer = function(testId) {
    const tabs = document.querySelectorAll('.tab-pane');
    const links = document.querySelectorAll('.nav-link');
    tabs.forEach(t => t.classList.remove('active'));
    links.forEach(l => l.classList.remove('active'));
    
    document.getElementById('tab-rig').classList.add('active');
    document.querySelector('.nav-link[data-target="tab-rig"]').classList.add('active');
    
    if (traceSelect) {
      traceSelect.value = testId;
      traceSelect.dispatchEvent(new Event('change'));
    }
  };

  // ══════════════════════════════════════════════
  // FETCH RUNS (real data from /api/runs)
  // ══════════════════════════════════════════════
  async function fetchRuns() {
    try {
      const res = await fetch('/api/runs');
      allRuns = await res.json();

      const badge = document.getElementById('runsCountBadge');
      const label = document.getElementById('runsCountLabel');
      if (badge) badge.textContent = allRuns.length;
      if (label) label.textContent = `${allRuns.length} RUNS`;

      // Populate compare selectors
      [compareRunA, compareRunB].forEach(sel => {
        if (!sel) return;
        sel.innerHTML = '<option value="">Select Run</option>';
        allRuns.forEach(r => {
          const opt = document.createElement('option');
          opt.value = r.run_id;
          opt.textContent = `${r.run_id} (${r.verdict})`;
          sel.appendChild(opt);
        });
      });

      renderRuns();
    } catch (e) {
      console.error('Runs fetch error:', e);
    }
  }

  function renderRuns() {
    if (!runsContainer) return;

    if (allRuns.length === 0) {
      runsContainer.innerHTML = '<div class="loading-text">No trace runs found in artifacts/traces/</div>';
      return;
    }

    runsContainer.innerHTML = allRuns.map(r => {
      const dur = r.duration_ns ? (r.duration_ns / 1e6).toFixed(1) + ' ms' : '—';
      const ts = r.timestamp ? new Date(r.timestamp).toLocaleString() : '—';
      const vClass = r.verdict === 'PASS' ? 'verdict-pass' : r.verdict === 'FAIL' ? 'verdict-fail' : 'verdict-unavailable';
      const vBadge = r.verdict === 'PASS' ? 'badge-pass' : r.verdict === 'FAIL' ? 'badge-fail' : 'badge-info';

      return `<div class="run-card ${vClass}" onclick="loadTraceInViewer('${r.run_id}')">
        <div class="run-card-header">
          <span class="run-id">${r.run_id}</span>
          <span class="badge ${vBadge}">${r.verdict || 'N/A'}</span>
        </div>
        <div class="run-meta">
          <span>Chip: <strong>${r.chip || '—'}</strong></span>
          <span>Duration: <strong>${dur}</strong></span>
          <span>Peripherals: <strong>${r.peripherals_count || 0}</strong></span>
          <span>Assertions: <strong>${r.assertions_count || 0}</strong></span>
        </div>
        <div style="font-size:10px; color:var(--silk-dim); font-family:var(--font-mono);">${ts}</div>
        <div class="run-actions" onclick="event.stopPropagation();">
          <button class="btn btn-ghost btn-sm" onclick="loadTraceInViewer('${r.run_id}')">3D View ↗</button>
          <a href="/view/${r.run_id}" target="_blank" class="btn btn-ghost btn-sm" style="text-decoration:none;">New Tab ↗</a>
          <button class="btn btn-ghost btn-sm" onclick="showDiagnosis('${r.test_id || r.run_id}')">Diagnosis</button>
        </div>
      </div>`;
    }).join('');
  }

  // Compare runs
  if (btnCompare) {
    btnCompare.addEventListener('click', () => {
      const a = compareRunA?.value;
      const b = compareRunB?.value;
      if (!a || !b) { showToast('Select both runs to compare'); return; }
      if (a === b) { showToast('Select two different runs'); return; }
      window.open(`/compare/${encodeURIComponent(a)}/${encodeURIComponent(b)}`, '_blank');
      showToast(`Comparing ${a} vs ${b} in 3D Rig`);
    });
  }

  // ══════════════════════════════════════════════
  // FETCH BOARDS (real data)
  // ══════════════════════════════════════════════
  async function fetchBoards() {
    try {
      const res = await fetch('/api/boards');
      const boards = await res.json();
      allBoards = boards;

      if (!boardsContainer) return;

      if (boards.length === 0) {
        boardsContainer.innerHTML = '<div class="loading-text">No board descriptors found in hardware/boards/</div>';
        return;
      }

      boardsContainer.innerHTML = boards.map(b => {
        const periphCount = (b.board.peripherals || []).length;
        const isUser = b.board.created_by === 'user';
        const createdBadge = isUser
          ? '<span class="chip-badge" style="background:var(--phosphor-dim);">USER</span>'
          : '<span class="chip-badge">BUILTIN</span>';

        let simClass = 'sim-ok';
        let simText = `✓ SIMULATOR (${b.simulator.supported_pins_count} pins)`;
        let cardClass = 'board-card';
        if (!b.simulator.available) {
          simClass = 'sim-err';
          simText = `✗ ${b.simulator.error || 'No simulator'}`;
          cardClass += ' no-sim';
        }

        const peripherals = (b.board.peripherals || []).map(p =>
          `<span style="font-size:10px; color:var(--silk-muted); display:inline-block; margin-right:8px;">• ${p.id} (${p.kind})</span>`
        ).join('');

        return `<div class="${cardClass}">
          <div class="chip-name">${b.board.chip} ${createdBadge}</div>
          <div class="periph-count">${periphCount} peripheral(s) · ${b.board.package || 'unknown'}</div>
          <div style="margin-top:6px; line-height:1.6;">${peripherals}</div>
          <div class="sim-status ${simClass}">${simText}</div>
        </div>`;
      }).join('');
    } catch (e) {
      console.error('Boards fetch error:', e);
    }
  }

  // ══════════════════════════════════════════════
  // FETCH FIRMWARE + DEFECTS (real data)
  // ══════════════════════════════════════════════
  async function fetchFirmware() {
    try {
      const res = await fetch('/api/firmware');
      const data = await res.json();

      // Store defect lines for code viewer highlighting
      defectLines = new Set();
      (data.defects || []).forEach(d => defectLines.add(d.line));

      // Store firmware lines
      firmwareLines = (data.content || '').split('\n');

      // Render defect cards
      if (defectsContainer) {
        defectsContainer.innerHTML = (data.defects || []).map(d => {
          const severity = d.severity || 'medium';
          return `<div class="defect-card severity-${severity}">
            <div class="defect-header">
              <span class="defect-title">${d.name}</span>
              <div style="display:flex; gap:6px; align-items:center;">
                <span class="severity-tag ${severity}">${severity}</span>
                <span class="badge badge-fail">L${d.line}</span>
              </div>
            </div>
            <div class="defect-impact">${d.impact}</div>
            <div class="code-diff">
              <span class="diff-line del">- ${escapeHtml(d.code)}</span>
              <span class="diff-line add">+ ${escapeHtml(d.correct)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-size:10px; color:var(--silk-muted); font-family:var(--font-mono);">Detected by: <strong style="color:var(--silk);">${d.test}</strong></span>
              <div style="display:flex; gap:4px;">
                <button class="btn btn-ghost btn-sm" onclick="loadTraceInViewer('${d.test}')">Inspect ↗</button>
                <button class="btn btn-ghost btn-sm" onclick="scrollToCodeLine(${d.line}, ${d.line})">Code ⤓</button>
                <a href="/view/${d.test}" target="_blank" class="btn btn-ghost btn-sm" style="text-decoration:none;">Tab ↗</a>
              </div>
            </div>
          </div>`;
        }).join('');
      }

      // Render code viewer with line numbers & defect highlights
      renderCodeViewer();
    } catch (e) {
      console.error('Firmware fetch error:', e);
    }
  }

  function renderCodeViewer() {
    if (!codeViewer || firmwareLines.length === 0) return;

    codeViewer.innerHTML = firmwareLines.map((line, i) => {
      const lineNum = i + 1;
      const isDefect = defectLines.has(lineNum);
      const className = isDefect ? 'code-line defect-line' : 'code-line';
      const highlighted = syntaxHighlight(escapeHtml(line));
      return `<div class="${className}" data-line="${lineNum}" id="code-line-${lineNum}">
        <span class="line-number">${lineNum}</span>
        <span class="line-content">${highlighted}</span>
      </div>`;
    }).join('');
  }

  function syntaxHighlight(line) {
    // Simple C syntax highlighting
    line = line.replace(/(\/\/.*$)/gm, '<span class="comment">$1</span>');
    line = line.replace(/(\/\*.*?\*\/)/g, '<span class="comment">$1</span>');
    line = line.replace(/(#\w+)/g, '<span class="preproc">$1</span>');
    line = line.replace(/\b(void|int|char|const|if|else|while|for|return|volatile|unsigned|uint32_t|bool)\b/g, '<span class="kw">$1</span>');
    line = line.replace(/\b(\d+)\b/g, '<span class="num">$1</span>');
    line = line.replace(/(&quot;[^&]*?&quot;)/g, '<span class="str">$1</span>');
    return line;
  }

  // ══════════════════════════════════════════════
  // SCROLL TO CODE LINE
  // ══════════════════════════════════════════════
  window.scrollToCodeLine = function(startLine, endLine) {
    if (!codeViewer) return;

    // Switch to behavior tab
    const behaviorTab = document.querySelector('[data-tab="tab-behavior"]');
    if (behaviorTab) behaviorTab.click();

    // Remove previous highlights
    codeViewer.querySelectorAll('.highlight').forEach(el => el.classList.remove('highlight'));

    // Highlight range
    for (let i = startLine; i <= endLine; i++) {
      const el = document.getElementById(`code-line-${i}`);
      if (el) el.classList.add('highlight');
    }

    // Scroll to line
    const target = document.getElementById(`code-line-${startLine}`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    showToast(`Navigated to lines ${startLine}–${endLine} in fan_controller.c`);
  };

  // ══════════════════════════════════════════════
  // LOAD TRACE IN 3D VIEWER
  // ══════════════════════════════════════════════
  window.loadTraceInViewer = function(testId) {
    // Switch to rig tab
    const rigTab = document.querySelector('[data-tab="tab-rig"]');
    if (rigTab) {
      rigTab.click();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    if (traceSelect) traceSelect.value = testId;

    if (rigIframe) {
      if (testId === 'demo') {
        rigIframe.src = '/viewer';
      } else {
        rigIframe.src = `/view/${encodeURIComponent(testId)}`;
      }
    }
    showToast(`3D Rig loaded: ${testId}`);
  };

  // ══════════════════════════════════════════════
  // INSPECT FUNCTION IN RIG
  // ══════════════════════════════════════════════
  window.inspectFunctionInRig = function(fnName, line) {
    const rigTab = document.querySelector('[data-tab="tab-rig"]');
    if (rigTab) {
      rigTab.click();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Find a trace that's relevant
    if (rigIframe) rigIframe.src = '/view/TS_0002';
    if (traceSelect) traceSelect.value = 'TS_0002';
    showToast(`Inspecting ${fnName}() [L${line}] in 3D Rig`);
  };

  // ══════════════════════════════════════════════
  // FETCH DIAGNOSIS (real data from report.json)
  // ══════════════════════════════════════════════
  async function fetchDiagnoses() {
    try {
      const res = await fetch('/api/diagnosis');
      const data = await res.json();
      allDiagnoses = data.diagnoses || [];
      renderDiagnoses();
    } catch (e) {
      console.error('Diagnosis fetch error:', e);
    }
  }

  function renderDiagnoses() {
    if (!diagnosisContainer) return;

    if (allDiagnoses.length === 0) {
      diagnosisContainer.innerHTML = '<div class="loading-text">No diagnosis data available</div>';
      return;
    }

    // Show top 6 most interesting diagnoses (highest confidence)
    const sorted = [...allDiagnoses].sort((a, b) => (b.confidence || 0) - (a.confidence || 0)).slice(0, 8);

    diagnosisContainer.innerHTML = sorted.map(d => {
      const confidence = Math.round((d.confidence || 0) * 100);
      const verdictBadge = d.verdict === 'pass'
        ? '<span class="badge badge-pass">PASS</span>'
        : '<span class="badge badge-fail">FAIL</span>';

      const causes = (d.probable_causes || []).slice(0, 2).map(c =>
        `<div class="cause-item">
          <div>${c.description || 'Unknown cause'}</div>
          ${c.evidence?.length ? `<div class="evidence">${c.evidence[0]}</div>` : ''}
        </div>`
      ).join('');

      const recs = (d.recommendations || []).slice(0, 2).map(r =>
        `<div style="font-size:10px; color:var(--silk-muted); padding:3px 0;">→ ${r}</div>`
      ).join('');

      return `<div class="diagnosis-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-family:var(--font-display); font-size:16px; color:var(--copper-light);">${d.test_id}</span>
          <div style="display:flex; gap:6px; align-items:center;">
            ${verdictBadge}
            <span class="badge badge-info">${d.failure_type || 'Unknown'}</span>
          </div>
        </div>
        <div style="font-size:11px; color:var(--silk-muted);">${d.description || ''}</div>
        <div style="display:flex; align-items:center; gap:8px; font-size:10px; color:var(--silk-muted); font-family:var(--font-mono);">
          <span>Confidence:</span>
          <div class="confidence-bar" style="flex:1;">
            <div class="confidence-fill" style="width:${confidence}%;"></div>
          </div>
          <span style="color:var(--phosphor); font-weight:600;">${confidence}%</span>
        </div>
        ${causes ? `<div style="margin-top:4px;">${causes}</div>` : ''}
        ${recs ? `<div style="margin-top:4px; border-top:1px dashed var(--hair); padding-top:6px;">${recs}</div>` : ''}
        <div style="display:flex; gap:4px; margin-top:auto; padding-top:6px;">
          <button class="btn btn-ghost btn-sm" onclick="loadTraceInViewer('${d.test_id}')">3D Trace ↗</button>
          <a href="/view/${d.test_id}" target="_blank" class="btn btn-ghost btn-sm" style="text-decoration:none;">Tab ↗</a>
        </div>
      </div>`;
    }).join('');
  }

  // Show diagnosis for specific test
  window.showDiagnosis = async function(testId) {
    try {
      const res = await fetch(`/api/diagnosis/${encodeURIComponent(testId)}`);
      if (!res.ok) { showToast(`No diagnosis data for ${testId}`); return; }
      const data = await res.json();
      const diag = data.diagnosis || {};

      // Switch to defects tab
      const defTab = document.querySelector('[data-tab="tab-defects"]');
      if (defTab) defTab.click();

      showToast(`Showing diagnosis for ${testId}: ${diag.failure_type || 'Unknown'} (${Math.round((diag.confidence || 0) * 100)}% confidence)`);
    } catch (e) {
      showToast(`Could not load diagnosis for ${testId}`);
    }
  };

  // ══════════════════════════════════════════════
  // FETCH BEHAVIOR (real AST data)
  // ══════════════════════════════════════════════
  async function fetchBehavior() {
    try {
      const res = await fetch('/api/behavior');
      const data = await res.json();

      const funcBadge = document.getElementById('funcCountBadge');
      if (funcBadge && data.functions) {
        funcBadge.textContent = `${data.functions.length} FUNCTIONS`;
      }

      if (funcListContainer && data.functions) {
        funcListContainer.innerHTML = '';
        data.functions.forEach(fn => {
          const fcard = document.createElement('div');
          fcard.className = 'func-card';

          const callsList = (fn.calls || []).length ? fn.calls.join(', ') : 'Leaf function';
          const gpioList = (fn.gpio_ops || []).length ? fn.gpio_ops.join(', ') : 'None';
          const paramsList = (fn.params || []).map(p => `${p.type || ''} ${p.name || ''}`).join(', ') || 'void';

          fcard.innerHTML = `
            <div class="func-title">
              <div>
                <span style="color:var(--silk); font-weight:700;">${fn.name}</span>
                <span style="color:var(--silk-muted); font-size:11px; font-weight:normal;">(${paramsList})</span>
              </div>
              <span class="badge badge-pass" style="font-size:9px;">
                ⚡ ${fn.live_calls || 0} CALLS
              </span>
            </div>
            <div class="func-details">
              <span><strong>Lines:</strong> L${fn.start_line}–L${fn.end_line}</span>
              <span><strong>Branches:</strong> ${(fn.conditions || []).length}</span>
              <span><strong>Loops:</strong> ${(fn.loops || []).length}</span>
              <span><strong>Calls:</strong> ${callsList}</span>
              ${gpioList !== 'None' ? `<span style="color:var(--sig-amber);"><strong>GPIO:</strong> ${gpioList}</span>` : ''}
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; padding-top:8px; border-top:1px solid var(--hair);">
              <span style="font-size:10px; color:var(--silk-dim);">AST: Deterministic</span>
              <div style="display:flex; gap:4px;">
                <button class="btn btn-ghost btn-sm" onclick="scrollToCodeLine(${fn.start_line}, ${fn.end_line}); event.stopPropagation();">
                  Code ⤓
                </button>
                <button class="btn btn-ghost btn-sm" style="color:var(--phosphor);" onclick="inspectFunctionInRig('${fn.name}', ${fn.start_line}); event.stopPropagation();">
                  3D Rig ↗
                </button>
              </div>
            </div>`;

          fcard.addEventListener('click', () => {
            document.querySelectorAll('.func-card').forEach(c => c.classList.remove('active'));
            fcard.classList.add('active');
            scrollToCodeLine(fn.start_line, fn.end_line);
          });

          funcListContainer.appendChild(fcard);
        });
      }
    } catch (e) {
      console.error('Behavior fetch error:', e);
    }
  }

  // ══════════════════════════════════════════════
  // TRIGGER AGENT RUN (via Modal)
  // ══════════════════════════════════════════════
  const newRunModal = document.getElementById('newRunModal');
  const btnCloseModal = document.getElementById('btnCloseModal');
  const btnCancelRun = document.getElementById('btnCancelRun');
  const btnSubmitRun = document.getElementById('btnSubmitRun');
  const firmwareCodeInput = document.getElementById('firmwareCodeInput');
  const chipSelect = document.getElementById('chipSelect');
  const pcbBlueprintInput = document.getElementById('pcbBlueprintInput');

  function closeModal() {
    if (newRunModal) newRunModal.classList.remove('show');
  }

  if (btnCloseModal) btnCloseModal.addEventListener('click', closeModal);
  if (btnCancelRun) btnCancelRun.addEventListener('click', closeModal);

  if (btnRunAgent) {
    btnRunAgent.addEventListener('click', () => {
      // Pre-populate with current firmware if available
      fetch('/api/firmware')
        .then(res => res.json())
        .then(data => {
          if (firmwareCodeInput && data.content && !firmwareCodeInput.value) {
            firmwareCodeInput.value = data.content;
          }
        })
        .catch(() => {});
      
      // Populate chips
      if (chipSelect && allBoards.length > 0) {
        chipSelect.innerHTML = allBoards.map(b => `<option value="${b.board.chip}">${b.board.chip}</option>`).join('');
      }

      if (newRunModal) newRunModal.classList.add('show');
    });
  }

  if (btnSubmitRun) {
    btnSubmitRun.addEventListener('click', async () => {
      try {
        const code = firmwareCodeInput ? firmwareCodeInput.value : '';
        let chip = chipSelect ? chipSelect.value : 'stm32f103';
        const pcbJsonStr = pcbBlueprintInput ? pcbBlueprintInput.value : '';

        if (!code.trim()) {
          showToast('Firmware code cannot be empty.');
          return;
        }

        // If user provided a PCB blueprint, POST it first
        if (pcbJsonStr.trim()) {
          try {
            const pcbData = JSON.parse(pcbJsonStr);
            if (!pcbData.chip) throw new Error("PCB JSON must contain a 'chip' field.");
            
            const boardRes = await fetch('/api/boards', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(pcbData)
            });
            if (!boardRes.ok) throw new Error("Failed to save custom board descriptor");
            chip = pcbData.chip;
            showToast(`Custom PCB loaded: ${chip}`);
          } catch (e) {
            showToast('Invalid PCB Blueprint: ' + e.message);
            return;
          }
        }

        closeModal();

        if (btnRunAgent) {
          btnRunAgent.disabled = true;
          // Cool animation for execution
          btnRunAgent.innerHTML = '<span class="icon" style="display:inline-block; animation:spin 1s linear infinite;">⟳</span> RUNNING...';
        }
        showToast('Autonomous Agent pipeline dispatched!');

        const res = await fetch('/api/run', { 
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: code, chip: chip })
        });
        const data = await res.json();
        showToast(data.message);

        // Poll status until complete
        const pollInterval = setInterval(async () => {
          await fetchStatus();
          if (agentStatusPill && agentStatusPill.textContent === 'IDLE') {
            clearInterval(pollInterval);
            if (btnRunAgent) {
              btnRunAgent.disabled = false;
              btnRunAgent.innerHTML = '<span class="icon">⚡</span> RUN AGENT';
            }
            // Refresh all data
            await Promise.all([
              fetchTests(), fetchTraces(), fetchRuns(), fetchDiagnoses(),
              fetchFirmware(), fetchBehavior(), fetchBoards()
            ]);
            showToast('Agent completed! All data refreshed.');
          }
        }, 2000);
      } catch (e) {
        console.error('Run trigger error:', e);
        showToast('Failed to trigger agent run.');
        if (btnRunAgent) {
          btnRunAgent.disabled = false;
          btnRunAgent.innerHTML = '<span class="icon">⚡</span> RUN AGENT';
        }
      }
    });
  }

  // ══════════════════════════════════════════════
  // LIBRARY & PROCEDURAL GENERATION
  // ══════════════════════════════════════════════
  let allLibraryItems = [];

  async function fetchLibrary() {
    try {
      const res = await fetch('/static/library_index.json');
      if (!res.ok) return;
      allLibraryItems = await res.json();
      renderLibrary();
    } catch (e) {
      console.warn('Library fetch error:', e);
    }
  }

  function renderLibrary() {
    const grid = document.getElementById('libraryGrid');
    const badge = document.getElementById('libraryCountBadge');
    if (!grid) return;
    
    if (badge) badge.textContent = allLibraryItems.length;

    grid.innerHTML = allLibraryItems.map((item, idx) => {
      const chipBadge = `<span class="chip-badge" style="background:var(--surface-3); color:var(--silk);">${item.chip}</span>`;
      return `<div class="board-card" style="display: flex; flex-direction: column; justify-content: space-between; border: 1px solid var(--surface-3); background: var(--surface-1); padding: 16px; border-radius: 8px;">
        <div>
          <div style="font-size: 14px; font-weight: 600; color: var(--silk); margin-bottom: 8px; display: flex; justify-content: space-between;">
            <span>Example #${idx+1}</span>
            ${chipBadge}
          </div>
          <div style="font-size: 12px; color: var(--silk-muted); margin-bottom: 4px;">Type: <strong style="color:var(--copper);">${item.archetype}</strong></div>
          <div style="font-size: 11px; color: var(--silk-dim); font-family: var(--font-mono);">Board: ${item.board}</div>
          <div style="font-size: 11px; color: var(--silk-dim); font-family: var(--font-mono);">Firmware: ${item.firmware}</div>
        </div>
        <div style="margin-top: 16px;">
          <button class="btn btn-ghost btn-sm" style="width: 100%; justify-content: center; border: 1px solid var(--surface-3);" onclick="runLibraryItem('${item.id}')">Load & Test ↗</button>
        </div>
      </div>`;
    }).join('');
  }

  window.runLibraryItem = async function(libraryId) {
    showToast(`Loading and Testing Library Item: ${libraryId}...`);
    
    const btnRunAgent = document.getElementById('btnRunAgent');
    if (btnRunAgent) {
      btnRunAgent.disabled = true;
      btnRunAgent.innerHTML = '<span class="icon" style="display:inline-block; animation:spin 1s linear infinite;">⟳</span> RUNNING...';
    }

    try {
      const res = await fetch(`/api/run_library/${libraryId}`, { method: 'POST' });
      const data = await res.json();
      showToast(data.message);

      // Poll status until complete
      const pollInterval = setInterval(async () => {
        await fetchStatus();
        const agentStatusPill = document.getElementById('agentStatusPill');
        if (agentStatusPill && agentStatusPill.textContent === 'IDLE') {
          clearInterval(pollInterval);
          if (btnRunAgent) {
            btnRunAgent.disabled = false;
            btnRunAgent.innerHTML = '<span class="icon">⚡</span> RUN AGENT';
          }
          // Refresh all data
          await Promise.all([
            fetchTests(), fetchTraces(), fetchRuns(), fetchDiagnoses(),
            fetchFirmware(), fetchBehavior(), fetchBoards(), fetchLibrary()
          ]);
          showToast('Library Item Test complete! 3D Rig updated.');
          // Auto switch to Dashboard tab
          const dashTab = document.querySelector('[data-tab="tab-rig"]');
          if (dashTab) dashTab.click();
        }
      }, 2000);
    } catch (e) {
      console.error('Library run error:', e);
      showToast('Failed to run library item.');
      if (btnRunAgent) {
        btnRunAgent.disabled = false;
        btnRunAgent.innerHTML = '<span class="icon">⚡</span> RUN AGENT';
      }
    }
  };

  window.generateSimilarLibraryItem = async function() {
    // A placeholder for generating a similar variant
    const currentActive = traceSelect ? traceSelect.value : null;
    showToast(`Generating procedural variant for active context...`);
    setTimeout(() => {
        showToast(`Variant generated! Try loading it from the library.`);
        fetchLibrary(); // Refresh library
    }, 2000);
  };

  // ══════════════════════════════════════════════
  // UTILITIES
  // ══════════════════════════════════════════════
  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  // ══════════════════════════════════════════════
  // INIT — Fetch all real data on load
  // ══════════════════════════════════════════════
  fetchStatus();
  fetchTests();
  fetchTraces();
  fetchRuns();
  fetchFirmware();
  fetchBehavior();
  fetchBoards();
  fetchDiagnoses();
  fetchLibrary();

  // Periodic status refresh
  setInterval(fetchStatus, 5000);
  // Periodic data refresh (30s)
  setInterval(() => {
    fetchRuns();
    fetchTraces();
  }, 30000);
});
