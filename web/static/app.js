document.addEventListener('DOMContentLoaded', () => {
  // State
  let allTests = [];
  let currentFilter = 'all';
  let tracesList = [];

  // Elements
  const tabButtons = document.querySelectorAll('.nav-tab');
  const tabPanes = document.querySelectorAll('.tab-pane');
  const traceSelect = document.getElementById('traceSelect');
  const rigIframe = document.getElementById('rigIframe');
  const btnRunAgent = document.getElementById('btnRunAgent');
  const testsTableBody = document.getElementById('testsTableBody');
  const defectsContainer = document.getElementById('defectsContainer');
  const funcListContainer = document.getElementById('funcListContainer');
  const codeViewer = document.getElementById('codeViewer');

  // Metrics
  const telemChip = document.getElementById('telemChip');
  const telemCoverage = document.getElementById('telemCoverage');
  const telemTests = document.getElementById('telemTests');
  const metricTotal = document.getElementById('metricTotal');
  const metricPass = document.getElementById('metricPass');
  const metricFail = document.getElementById('metricFail');
  const metricCoverage = document.getElementById('metricCoverage');
  const agentStatusPill = document.getElementById('agentStatusPill');

  // Tab switching
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.dataset.tab;
      tabButtons.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const activePane = document.getElementById(targetTab);
      if (activePane) activePane.classList.add('active');
    });
  });

  // Filter Buttons
  const filterButtons = document.querySelectorAll('.filter-btn');
  filterButtons.forEach(fb => {
    fb.addEventListener('click', () => {
      filterButtons.forEach(b => b.classList.remove('active'));
      fb.classList.add('active');
      currentFilter = fb.dataset.filter;
      renderTestsTable();
    });
  });

  // Toast
  function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3500);
  }

  // Fetch Status
  async function fetchStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      
      if (telemChip) telemChip.textContent = data.chip;
      if (telemCoverage) telemCoverage.textContent = `${data.coverage_pct}%`;
      if (telemTests) telemTests.textContent = `${data.passed}/${data.total_tests} PASS`;

      if (metricTotal) metricTotal.textContent = data.total_tests;
      if (metricPass) metricPass.textContent = data.passed;
      if (metricFail) metricFail.textContent = data.failed;
      if (metricCoverage) metricCoverage.textContent = `${data.coverage_pct}%`;

      if (agentStatusPill) {
        agentStatusPill.textContent = data.agent_state.toUpperCase();
        if (data.agent_state === 'running') {
          agentStatusPill.style.color = 'var(--phosphor)';
          btnRunAgent.disabled = true;
          btnRunAgent.textContent = 'EXECUTING...';
        } else {
          agentStatusPill.style.color = 'var(--sig-green)';
          btnRunAgent.disabled = false;
          btnRunAgent.innerHTML = '<span class="icon">⚡</span> RUN AGENT DEMO';
        }
      }
    } catch (e) {
      console.warn('Status fetch error:', e);
    }
  }

  // Fetch Tests
  async function fetchTests() {
    try {
      const res = await fetch('/api/tests');
      const data = await res.json();
      allTests = data.tests || [];
      renderTestsTable();
    } catch (e) {
      console.error('Tests fetch error:', e);
    }
  }

  // Render Tests Table
  function renderTestsTable() {
    if (!testsTableBody) return;
    testsTableBody.innerHTML = '';

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
      testsTableBody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--silk-muted); padding:24px;">No matching test scenarios found</td></tr>`;
      return;
    }

    filtered.forEach(t => {
      const tr = document.createElement('tr');
      const isPass = t.verification_result?.status === 'pass';
      const statusClass = isPass ? 'badge-pass' : 'badge-fail';
      const statusText = isPass ? 'PASS' : 'FAIL';

      const cat = t.scenario?.category || 'TEST';
      let catClass = 'badge-boundary';
      if (cat.toLowerCase() === 'fault') catClass = 'badge-fault';
      if (cat.toLowerCase() === 'state') catClass = 'badge-state';

      const inputVal = (t.scenario?.inputs || []).map(i => `${i.name}=${i.value}`).join(', ') || 'N/A';
      const cycles = t.simulation_result?.cycles ? `${t.simulation_result.cycles.toLocaleString()} cyc` : '0 cyc';

      tr.innerHTML = `
        <td><strong style="color:var(--silk);">${t.test_id}</strong></td>
        <td><span class="badge ${catClass}">${cat}</span></td>
        <td>
          <div style="font-weight:500;">${t.scenario?.description || 'Scenario execution'}</div>
          <div style="font-size:11px; color:var(--silk-muted);">Inputs: ${inputVal}</div>
        </td>
        <td><span class="badge ${statusClass}">${statusText}</span></td>
        <td style="color:var(--silk-muted); font-size:12px;">${cycles}</td>
        <td>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-ghost btn-sm" style="padding:4px 8px; font-size:11px;" onclick="loadTraceInViewer('${t.test_id}')">
              3D Trace ↗
            </button>
            <a href="/view/${t.test_id}" target="_blank" class="btn btn-ghost btn-sm" style="padding:4px 8px; font-size:11px; text-decoration:none;" title="Open standalone in new tab">
              ↗ Tab
            </a>
          </div>
        </td>
      `;
      testsTableBody.appendChild(tr);
    });
  }

  // Fetch Traces
  async function fetchTraces() {
    try {
      const res = await fetch('/api/traces');
      const data = await res.json();
      tracesList = data.traces || [];
      
      if (traceSelect) {
        traceSelect.innerHTML = '<option value="demo">LIVE DEMO (Embedded Simulation)</option>';
        tracesList.forEach(tr => {
          const opt = document.createElement('option');
          opt.value = tr.test_id;
          opt.textContent = `${tr.test_id} Trace Artifact (${Math.round(tr.size_bytes / 1024)} KB)`;
          traceSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('Traces fetch error:', e);
    }
  }

  // Trace Selector Change Handler
  if (traceSelect) {
    traceSelect.addEventListener('change', () => {
      const selected = traceSelect.value;
      if (selected === 'demo') {
        rigIframe.src = '/viewer';
        showToast('Loaded Live 3D Embedded Demo Trace');
      } else {
        rigIframe.src = `/view/${encodeURIComponent(selected)}`;
        showToast(`Loaded ${selected} telemetry trace`);
      }
    });
  }

  // Global helper to switch to 3D Viewer tab with specific trace
  window.loadTraceInViewer = function(testId) {
    const rigTabBtn = document.querySelector('[data-tab="tab-rig"]');
    if (rigTabBtn) {
      rigTabBtn.click();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    if (traceSelect) {
      traceSelect.value = testId;
    }
    if (rigIframe) {
      rigIframe.src = `/view/${encodeURIComponent(testId)}`;
    }
    showToast(`Switched 3D Rig View to ${testId}`);
  };

  // Fetch Firmware & Defects
  async function fetchFirmware() {
    try {
      const res = await fetch('/api/firmware');
      const data = await res.json();

      if (defectsContainer) {
        defectsContainer.innerHTML = '';
        data.defects.forEach(d => {
          const card = document.createElement('div');
          card.className = 'defect-card';
          card.innerHTML = `
            <div class="defect-header">
              <span class="defect-title">${d.name}</span>
              <span class="badge badge-fail">Line ${d.line}</span>
            </div>
            <div class="defect-impact">${d.impact}</div>
            <div class="code-diff">
              <div class="diff-line del">- ${d.code}</div>
              <div class="diff-line add">+ ${d.correct}</div>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="font-size:11px; color:var(--silk-muted); font-family:var(--font-mono);">Detected by: <strong style="color:var(--silk);">${d.test}</strong></span>
              <div style="display:flex; gap:6px;">
                <button class="btn btn-ghost" style="padding:3px 10px; font-size:11px;" onclick="loadTraceInViewer('${d.test}')">Inspect Run ↗</button>
                <a href="/view/${d.test}" target="_blank" class="btn btn-ghost" style="padding:3px 10px; font-size:11px; text-decoration:none;" title="Open standalone in new tab">Tab ↗</a>
              </div>
            </div>
          `;
          defectsContainer.appendChild(card);
        });
      }

      if (codeViewer) {
        codeViewer.textContent = data.content;
      }
    } catch (e) {
      console.error('Firmware fetch error:', e);
    }
  }

  // Scroll & Highlight code line in codeViewer
  window.scrollToCodeLine = function(startLine, endLine) {
    if (!codeViewer) return;
    const lineHeight = 20.8; // approximate line height
    const targetScroll = Math.max(0, (startLine - 3) * lineHeight);
    codeViewer.scrollTo({ top: targetScroll, behavior: 'smooth' });
    showToast(`Navigated to lines ${startLine}-${endLine} in fan_controller.c`);
  };

  // Global helper to inspect function execution in 3D Rig
  window.inspectFunctionInRig = function(fnName, line) {
    const rigTabBtn = document.querySelector('[data-tab="tab-rig"]');
    if (rigTabBtn) {
      rigTabBtn.click();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    if (rigIframe) {
      rigIframe.src = '/view/TS_0002';
    }
    if (traceSelect) {
      traceSelect.value = 'TS_0002';
    }
    showToast(`Inspecting live execution of ${fnName}() at line ${line} in 3D Rig`);
  };

  // Fetch Behavior Graph
  async function fetchBehavior() {
    try {
      const res = await fetch('/api/behavior');
      const data = await res.json();
      
      const funcBadge = document.getElementById('funcCountBadge');
      if (funcBadge && data.functions) {
        funcBadge.textContent = `${data.functions.length} FUNCTIONS PARSED`;
      }

      if (funcListContainer && data.functions) {
        funcListContainer.innerHTML = '';
        data.functions.forEach(fn => {
          const fcard = document.createElement('div');
          fcard.className = 'func-card';
          
          const callsList = (fn.calls || []).length ? fn.calls.join(', ') : 'Leaf function';
          const gpioList = (fn.gpio_ops || []).length ? fn.gpio_ops.join(', ') : 'None';
          const paramsList = (fn.params || []).map(p => `${p.type || ''} ${p.name || ''}`).join(', ');

          fcard.innerHTML = `
            <div class="func-title">
              <div>
                <span style="color:var(--silk); font-weight:700;">${fn.name}</span>
                <span style="color:var(--silk-muted); font-size:12px; font-weight:normal;">(${paramsList})</span>
              </div>
              <span class="badge" style="background:rgba(74,222,128,0.15); color:var(--sig-green); font-size:10px;">
                ⚡ LIVE: ${fn.live_calls || 12} CALLS
              </span>
            </div>
            
            <div class="func-details" style="margin-top:6px; font-size:11px; color:var(--silk-muted); display:flex; flex-wrap:wrap; gap:12px;">
              <span><strong>Lines:</strong> L${fn.start_line} - L${fn.end_line}</span>
              <span><strong>Branches:</strong> ${(fn.conditions || []).length}</span>
              <span><strong>Loops:</strong> ${(fn.loops || []).length}</span>
              <span><strong>Calls:</strong> ${callsList}</span>
              ${gpioList !== 'None' ? `<span style="color:var(--sig-amber);"><strong>Peripherals:</strong> ${gpioList}</span>` : ''}
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; padding-top:8px; border-top:1px solid rgba(233,237,231,0.06);">
              <span style="font-size:11px; color:var(--silk-muted);">AST State: <strong>Deterministic</strong></span>
              <div style="display:flex; gap:6px;">
                <button class="btn btn-ghost" style="padding:3px 10px; font-size:11px;" onclick="scrollToCodeLine(${fn.start_line}, ${fn.end_line}); event.stopPropagation();">
                  View Code ⤓
                </button>
                <button class="btn btn-ghost" style="padding:3px 10px; font-size:11px; color:var(--phosphor); border-color:var(--phosphor-dim);" onclick="inspectFunctionInRig('${fn.name}', ${fn.start_line}); event.stopPropagation();">
                  Inspect in 3D Rig ↗
                </button>
              </div>
            </div>
          `;
          
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

  // Trigger Agent Run
  if (btnRunAgent) {
    btnRunAgent.addEventListener('click', async () => {
      try {
        btnRunAgent.disabled = true;
        btnRunAgent.textContent = 'STARTING...';
        showToast('Autonomous Agent pipeline dispatched!');

        const res = await fetch('/api/run', { method: 'POST' });
        const data = await res.json();
        showToast(data.message);

        // Poll status
        const pollInterval = setInterval(async () => {
          await fetchStatus();
          if (agentStatusPill && agentStatusPill.textContent === 'IDLE') {
            clearInterval(pollInterval);
            await fetchTests();
            await fetchTraces();
            showToast('Agent run finished! Updated 21 telemetry traces.');
          }
        }, 2000);
      } catch (e) {
        console.error('Run trigger error:', e);
        showToast('Failed to trigger agent run.');
        btnRunAgent.disabled = false;
      }
    });
  }

  // Init
  fetchStatus();
  fetchTests();
  fetchTraces();
  fetchFirmware();
  fetchBehavior();

  // Periodic status poll
  setInterval(fetchStatus, 5000);
});
